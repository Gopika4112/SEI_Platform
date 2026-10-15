import os
from unittest.mock import patch

from api.routes import ingest as ingest_route
from ingestion.cloner import walk_files
from ingestion.extractor import EntityRelationshipExtractor
from ingestion.parser import CodeParser
from ingestion.chunker import SemanticChunker
from storage.graph_store import GraphStoreManager
from storage.vector_store import VectorStoreManager


JAVASCRIPT_SOURCE = """import { helper } from "./helpers.js";
const LIMIT = 5;

class Parent {
    base() {}
}

class Service extends Parent {
    run(value) {
        return helper(value);
    }
}

function greet(name) {
    return helper(name);
}

const normalize = (value) => helper(value);
const formatter = function (value) { return helper(value); };
"""


def test_javascript_parser_chunker_and_relationships(tmp_path):
    file_path = tmp_path / "service.js"
    file_path.write_text(JAVASCRIPT_SOURCE, encoding="utf-8")

    parsed = CodeParser("javascript").parse_file(str(file_path))
    classes = {item["name"]: item for item in parsed["classes"]}
    functions = {item["name"]: item for item in parsed["functions"]}

    assert parsed["language"] == "javascript"
    assert parsed["imports"][0]["text"].startswith("import")
    assert classes["Service"]["bases"] == ["Parent"]
    assert [method["name"] for method in classes["Service"]["methods"]] == ["run"]
    assert {"greet", "normalize", "formatter"} <= functions.keys()

    chunks = SemanticChunker().chunk_file(str(file_path), parsed)
    chunk_by_name = {chunk.metadata["name"]: chunk for chunk in chunks}
    assert chunk_by_name["Service"].metadata["language"] == "javascript"
    assert chunk_by_name["run"].metadata["entity_type"] == "method"
    assert chunk_by_name["normalize"].metadata["entity_type"] == "function"
    module_chunk = next(
        chunk for chunk in chunks if chunk.metadata["entity_type"] == "module"
    )
    assert 'from "./helpers.js"' in module_chunk.content
    assert "const LIMIT = 5" in module_chunk.content

    relationships = EntityRelationshipExtractor().extract_relationships(
        str(file_path),
        parsed,
    )
    rel_types = [relationship[1] for relationship in relationships]
    assert {"IMPORTS", "DEFINED_IN", "HAS_METHOD", "CALLS", "INHERITS"} <= set(
        rel_types
    )
    assert any(
        rel[1] == "IMPORTS" and rel[2]["name"] == "./helpers.js"
        for rel in relationships
    )
    assert any(
        rel[1] == "INHERITS"
        and rel[0]["name"] == "Service"
        and rel[2]["name"] == "Parent"
        for rel in relationships
    )
    assert any(
        rel[1] == "CALLS" and rel[0]["name"] == "normalize"
        and rel[2]["name"] == "helper"
        for rel in relationships
    )


def test_javascript_syntax_errors_are_reported_without_raising(tmp_path):
    file_path = tmp_path / "malformed.js"
    file_path.write_text("function unfinished( {", encoding="utf-8")

    parsed = CodeParser("javascript").parse_file(str(file_path))

    assert parsed["has_syntax_errors"] is True
    assert parsed["language"] == "javascript"


def test_walk_files_discovers_supported_sources_and_docs_but_skips_generated_dirs(
    tmp_path,
):
    repo = tmp_path / "repo"
    repo.mkdir()
    expected_extensions = (".py", ".js", ".jsx", ".mjs", ".cjs", ".md", ".txt", ".rst")

    for extension in expected_extensions:
        (repo / f"sample{extension}").write_text("", encoding="utf-8")

    ignored = repo / "node_modules"
    ignored.mkdir()
    (ignored / "dependency.js").write_text("", encoding="utf-8")
    generated = repo / "dist"
    generated.mkdir()
    (generated / "bundle.js").write_text("", encoding="utf-8")

    discovered = set(walk_files(str(repo)))

    assert discovered == {
        str(repo / f"sample{extension}") for extension in expected_extensions
    }


def test_ingestion_pipeline_handles_python_javascript_docs_and_malformed_file(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    repo_files = {
        "sample.py": "def python_function():\n    return 1\n",
        "app.js": JAVASCRIPT_SOURCE,
        "malformed.js": "function unfinished( {",
        "README.md": "# Example\n\nRepository documentation.",
    }

    def clone_repository(_url, destination, _branch):
        os.makedirs(destination, exist_ok=True)
        for relative_path, source in repo_files.items():
            full_path = os.path.join(destination, relative_path)
            with open(full_path, "w", encoding="utf-8") as file:
                file.write(source)

    class MockEmbedder:
        def embed_texts(self, texts):
            return [[0.25] * 2048 for _ in texts]

    class MockVectorStore:
        vector_size = 2048

        def __init__(self):
            self.chunks = []

        def ensure_collection_exists(self):
            return None

        def upsert_chunks(self, chunks):
            self.chunks.extend(chunks)

    class MockGraphStore:
        instances = []

        def __init__(self):
            self.nodes = []
            self.relationships = []
            self.closed = False
            self.instances.append(self)

        def create_nodes_and_edges(self, nodes, relationships):
            self.nodes.extend(nodes)
            self.relationships.extend(relationships)

        def close(self):
            self.closed = True

    vector_store = MockVectorStore()
    completed = []
    monkeypatch.setattr(ingest_route, "clone_repository", clone_repository)
    monkeypatch.setattr(ingest_route, "VectorStoreManager", lambda: vector_store)
    monkeypatch.setattr(ingest_route, "GraphStoreManager", MockGraphStore)
    monkeypatch.setattr(ingest_route, "get_repo_checkpoint", lambda _url: {"files": {}})
    monkeypatch.setattr(
        ingest_route,
        "calculate_file_hash",
        lambda _path: "test-hash",
    )
    monkeypatch.setattr(
        ingest_route,
        "mark_file_completed",
        lambda _url, path, file_hash: completed.append((path, file_hash)),
    )

    ingest_route.run_ingestion_pipeline(
        "javascript-integration-test",
        "https://github.com/example/repository",
        embedder=MockEmbedder(),
    )

    job = ingest_route.jobs_progress["javascript-integration-test"]
    assert job["status"] == "completed"
    assert job["stats"]["files"] == len(repo_files)
    assert len(completed) == len(repo_files)
    assert any(
        chunk.metadata.get("language") == "python"
        and chunk.metadata.get("name") == "python_function"
        for chunk in vector_store.chunks
    )
    assert any(
        chunk.metadata.get("language") == "javascript"
        and chunk.metadata.get("name") == "normalize"
        for chunk in vector_store.chunks
    )
    assert any(
        chunk.metadata.get("entity_type") == "documentation"
        for chunk in vector_store.chunks
    )
    assert all(len(chunk.embedding) == 2048 for chunk in vector_store.chunks)
    assert MockGraphStore.instances
    graph = MockGraphStore.instances[-1]
    assert graph.closed is True
    assert any(rel[1] == "IMPORTS" for rel in graph.relationships)
    assert any(rel[1] == "INHERITS" for rel in graph.relationships)


def test_qdrant_upsert_keeps_javascript_metadata_and_dimension():
    with patch("storage.vector_store.QdrantClient") as qdrant_client:
        manager = VectorStoreManager()
        manager.setup_collection()
        parsed = {
            "language": "javascript",
            "classes": [],
            "functions": [{
                "name": "run",
                "parameters": [],
                "start_line": 1,
                "end_line": 1,
                "text": "function run() {}",
            }],
            "imports": [],
            "variables": [],
        }
        chunk = SemanticChunker().chunk_file("app.js", parsed)[0]
        chunk.embedding = [0.1] * 2048

        manager.upsert_chunks([chunk])

        point = qdrant_client.return_value.upsert.call_args.kwargs["points"][0]
        assert len(point.vector) == 2048
        assert point.payload["file_path"] == "app.js"
        assert point.payload["language"] == "javascript"


def test_graph_store_merges_relationships_for_idempotent_ingestion():
    with patch("storage.graph_store.GraphDatabase.driver") as driver:
        manager = GraphStoreManager()
        session = driver.return_value.session.return_value.__enter__.return_value
        manager.create_nodes_and_edges(
            [
                {
                    "name": "app.js",
                    "label": "File",
                    "metadata": {"absolute_path": "app.js", "file_path": "app.js"},
                },
                {
                    "name": "./helpers.js",
                    "label": "Module",
                    "metadata": {"file_path": "app.js"},
                },
            ],
            [
                (
                    {
                        "name": "app.js",
                        "label": "File",
                        "metadata": {"file_path": "app.js"},
                    },
                    "IMPORTS",
                    {
                        "name": "./helpers.js",
                        "label": "Module",
                        "metadata": {"file_path": "app.js"},
                    },
                )
            ],
        )

        queries = [call.args[0] for call in session.run.call_args_list]
        assert any("MERGE (src)-[:IMPORTS]->(dst)" in query for query in queries)

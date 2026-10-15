import os
import pytest
from unittest.mock import MagicMock, patch
from ingestion.chunker import CodeChunk
from storage.vector_store import VectorStoreManager
from storage.graph_store import GraphStoreManager
from retrieval.semantic import SemanticRetriever
from retrieval.graph import GraphRetriever
from retrieval.hybrid import HybridRetriever

def test_vector_store_manager_mock():
    with patch("storage.vector_store.QdrantClient") as MockClient:
        mock_instance = MockClient.return_value
        manager = VectorStoreManager(host="localhost", port=6333)
        manager.setup_collection(vector_size=768)
        mock_instance.recreate_collection.assert_called_once()
        
        chunks = [
            CodeChunk(
                id="test_file.py::function::test_func",
                content="def test_func(): pass",
                metadata={"file_path": "test_file.py", "name": "test_func", "entity_type": "function"},
                embedding=[0.1] * 768
            )
        ]
        manager.upsert_chunks(chunks)
        mock_instance.upsert.assert_called_once()
        
        # Mock query response with a points list attribute
        mock_response = MagicMock()
        mock_response.points = []
        mock_instance.query_points.return_value = mock_response
        
        results = manager.search_similar(query_vector=[0.1] * 768)
        assert len(results) == 0

def test_graph_store_manager_mock():
    with patch("storage.graph_store.GraphDatabase.driver") as MockDriver:
        mock_driver_instance = MockDriver.return_value
        mock_session = mock_driver_instance.session.return_value.__enter__.return_value
        manager = GraphStoreManager(uri="bolt://localhost:7687")
        assert mock_session.run.call_count >= 5
        
        mock_session.reset_mock()
        nodes = [
            {"name": "test_file.py", "label": "File", "metadata": {"absolute_path": "test_file.py"}},
            {"name": "test_func", "label": "Function", "metadata": {"file_path": "test_file.py"}}
        ]
        relationships = [
            (
                {"name": "test_func", "label": "Function", "metadata": {"file_path": "test_file.py"}},
                "DEFINED_IN",
                {"name": "test_file.py", "label": "File", "metadata": {"absolute_path": "test_file.py"}}
            )
        ]
        manager.create_nodes_and_edges(nodes, relationships)
        assert mock_session.run.call_count >= 2

def test_semantic_retriever_mock():
    mock_vs = MagicMock()
    mock_emb = MagicMock()
    mock_emb.embed_texts.return_value = [[0.1] * 768]
    mock_vs.search_similar.return_value = [{"id": "chunk_1", "content": "mock content", "score": 0.85, "metadata": {}}]
    
    retriever = SemanticRetriever(mock_vs, mock_emb)
    results = retriever.retrieve("What is this?", top_k=5, filters={"entity_type": "function"})
    
    assert len(results) == 1
    assert results[0]["id"] == "chunk_1"
    mock_emb.embed_texts.assert_called_once_with(["What is this?"], input_type="query")
    # Verify filter conversion was triggered
    mock_vs.search_similar.assert_called_once()

def test_graph_retriever_mock():
    mock_gs = MagicMock()
    # Mock Cypher caller return results
    mock_gs.run_query.return_value = [{"file_path": "auth.py", "name": "login_user", "entity_type": "Function"}]
    
    with patch("retrieval.graph.Groq") as MockGroq:
        mock_client = MockGroq.return_value
        mock_message = MagicMock()
        # Mock LLM JSON output response
        mock_message.content = '{"entities": ["AuthService"]}'
        mock_client.chat.completions.create.return_value.choices[0].message = mock_message
        
        # Override environment variable to enable mock Groq client
        with patch.dict(os.environ, {"GROQ_API_KEY": "mock_key"}):
            retriever = GraphRetriever(mock_gs)
            entities = retriever.extract_entity_names("Find calls to AuthService")
            assert entities == ["AuthService"]
            
            callers = retriever.find_callers("AuthService")
            assert len(callers) == 1
            assert callers[0]["name"] == "login_user"

def test_hybrid_retriever_mock():
    mock_semantic = MagicMock()
    mock_graph = MagicMock()
    
    # 1. Mock Semantic returns
    mock_semantic.retrieve.return_value = [
        {"id": "chunk_1", "content": "def login(): pass", "score": 0.8, "metadata": {"name": "login", "entity_type": "function", "file_path": "auth.py"}}
    ]
    # Allow mock vector store lookup for Graph node chunk content
    mock_vs = MagicMock()
    mock_vs.search_similar.return_value = [
        {"id": "chunk_2", "content": "class AuthService: pass", "score": 0.9, "metadata": {"name": "AuthService", "entity_type": "class", "file_path": "auth.py"}}
    ]
    mock_semantic.vector_store = mock_vs
    
    # 2. Mock Graph returns
    mock_graph.find_callers.return_value = [
        {"file_path": "auth.py", "name": "AuthService", "entity_type": "Class"}
    ]
    mock_graph.find_inheritance.return_value = []
    
    retriever = HybridRetriever(mock_semantic, mock_graph)
    results = retriever.retrieve_and_rerank("What calls AuthService?", intent="impact", entities=["AuthService"], top_k=5)
    
    # Assert merged counts and deduplication
    assert len(results) == 2
    sources = [r["source"] for r in results]
    assert "vector" in sources
    assert "graph" in sources
    
    # 3. Verify Context formatting
    context = retriever.format_context(results)
    assert "[File: auth.py | Entity: AuthService" in context
    assert "[File: auth.py | Entity: login" in context

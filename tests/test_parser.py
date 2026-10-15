import os
import pytest
from ingestion.parser import CodeParser
from ingestion.chunker import SemanticChunker
from ingestion.extractor import EntityRelationshipExtractor

MOCK_CODE = """import os
from math import sqrt as square_root

GLOBAL_VAR = 42

class BaseHandler:
    \"\"\"This is the BaseHandler docstring.\"\"\"
    def __init__(self, name):
        self.name = name
        
    def perform_action(self):
        print("action performed")

class DBHandler(BaseHandler):
    \"\"\"This is the DBHandler docstring.\"\"\"
    def connect_db(self):
        # Call a function
        connection = establish_connection()
        return connection

def calculate_value(x):
    # Call another function and use global var
    val = square_root(x) + GLOBAL_VAR
    return val
"""

def test_pipeline_integration(tmp_path):
    # Write mock code to a temporary file in temp directory
    file_path = os.path.join(tmp_path, "mock_code.py")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(MOCK_CODE)
        
    # 1. Verify Parser
    parser = CodeParser(language="python")
    ast_nodes = parser.parse_file(file_path)
    
    assert ast_nodes["file_path"] == file_path
    assert len(ast_nodes["imports"]) == 2
    assert len(ast_nodes["variables"]) == 1
    assert len(ast_nodes["classes"]) == 2
    assert len(ast_nodes["functions"]) == 1
    
    classes = {cls["name"]: cls for cls in ast_nodes["classes"]}
    assert "BaseHandler" in classes
    assert "DBHandler" in classes
    assert classes["DBHandler"]["bases"] == ["BaseHandler"]
    assert classes["BaseHandler"]["docstring"] == "This is the BaseHandler docstring."
    
    # Verify class method separation
    assert len(classes["BaseHandler"]["methods"]) == 2  # __init__ and perform_action
    assert len(classes["DBHandler"]["methods"]) == 1    # connect_db
    
    # Verify standalone function definitions
    assert ast_nodes["functions"][0]["name"] == "calculate_value"
    
    # 2. Verify Chunker
    chunker = SemanticChunker()
    chunks = chunker.chunk_file(file_path, ast_nodes)
    
    # Expecting chunks for:
    # - Class BaseHandler (1)
    # - Method BaseHandler.__init__ (2)
    # - Method BaseHandler.perform_action (3)
    # - Class DBHandler (4)
    # - Method DBHandler.connect_db (5)
    # - Function calculate_value (6)
    # - Module mock_code.py overview (7)
    assert len(chunks) == 7
    
    chunk_types = [c.metadata["entity_type"] for c in chunks]
    assert "class" in chunk_types
    assert "method" in chunk_types
    assert "function" in chunk_types
    assert "module" in chunk_types
    
    # 3. Verify Extractor
    extractor = EntityRelationshipExtractor()
    relationships = extractor.extract_relationships(file_path, ast_nodes)
    
    rel_types = [r[1] for r in relationships]
    assert "IMPORTS" in rel_types
    assert "INHERITS" in rel_types
    assert "DEFINED_IN" in rel_types
    assert "CALLS" in rel_types
    
    # Verify INHERITS relationship
    inherits_rels = [r for r in relationships if r[1] == "INHERITS"]
    assert len(inherits_rels) == 1
    assert inherits_rels[0][0]["name"] == "DBHandler"
    assert inherits_rels[0][0]["label"] == "Class"
    assert inherits_rels[0][2]["name"] == "BaseHandler"
    assert inherits_rels[0][2]["label"] == "Class"
    
    # Verify CALLS relationships
    calls_rels = [r for r in relationships if r[1] == "CALLS"]
    assert len(calls_rels) > 0
    
    # connect_db calls establish_connection
    db_calls = [r for r in calls_rels if r[0]["name"] == "connect_db"]
    assert len(db_calls) == 1
    assert db_calls[0][2]["name"] == "establish_connection"
    
    # calculate_value calls square_root
    calc_calls = [r for r in calls_rels if r[0]["name"] == "calculate_value"]
    assert len(calc_calls) == 1
    assert calc_calls[0][2]["name"] == "square_root"


def test_text_chunking(tmp_path):
    doc_path = os.path.join(tmp_path, "README.md")
    doc_content = (
        "# CodeAtlas\n\n"
        "This is the first paragraph of the documentation describing the project.\n\n"
        "This is the second paragraph which gives deployment instructions.\n\n"
        "### Section 2\n\n"
        "This is a longer paragraph in Section 2 containing setup details."
    )
    with open(doc_path, "w", encoding="utf-8") as f:
        f.write(doc_content)
        
    chunker = SemanticChunker()
    chunks = chunker.chunk_text_file(doc_path, doc_content, chunk_size=100)
    
    # Since chunk_size is 100, each paragraph will be split into separate chunks
    assert len(chunks) >= 3
    
    # Verify metadata
    for chunk in chunks:
        assert chunk.metadata["file_path"] == doc_path
        assert chunk.metadata["entity_type"] == "documentation"
        assert "README.md" in chunk.metadata["name"]
        assert chunk.content.strip() != ""

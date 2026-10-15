import os
import re
import logging
from fastapi import APIRouter, HTTPException
from api.models import QueryRequest, QueryResponse
from storage.graph_store import GraphStoreManager
from qdrant_client import QdrantClient
from neo4j import GraphDatabase
from agents.graph_flow import build_workflow

logger = logging.getLogger(__name__)

router = APIRouter()

def clean_file_path(path: str) -> str:
    if not path:
        return ""
    norm_path = path.replace("\\", "/")
    # Match temp_repos/UUID/relative_path
    match = re.search(r"temp_repos/[^/]+/(.+)$", norm_path)
    if match:
        return match.group(1)
    # Match Code-Atlas/relative_path
    if "Code-Atlas/" in norm_path:
        return norm_path.split("Code-Atlas/")[-1]
    return os.path.basename(norm_path)

# Compile the LangGraph state machine workflow on startup
# This provides a singletonCompiledStateGraph instance for all API calls
try:
    workflow_app = build_workflow().compile()
except Exception as e:
    # Fallback to None if databases/env are not fully loaded during static import
    workflow_app = None

@router.post("/query", response_model=QueryResponse)
def execute_query(request: QueryRequest):
    """
    Executes the query by feeding the question to the live LangGraph
    multi-agent workflow pipeline, returning the final cited answer.
    """
    global workflow_app
    if workflow_app is None:
        try:
            workflow_app = build_workflow().compile()
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to compile LangGraph state machine workflow: {str(e)}"
            )

    # Initialize the starting state of the graph
    initial_state = {
        "query": request.question,
        "intent": "explain",  # Will be classified by the Planner Agent
        "entities": [],       # Will be extracted by the Planner Agent
        "vector_results": [],
        "graph_results": [],
        "answer": "",
        "sources": [],
        "eval_score": 0.0,
        "eval_feedback": "",
        "retry_count": 0
    }

    try:
        # Invoke the compiled state machine graph
        # This will execute: Planner -> Retriever/GraphAgent -> Answer -> Evaluator
        # and self-correct if score is below threshold
        final_state = workflow_app.invoke(initial_state)
        
        return QueryResponse(
            answer=final_state.get("answer", "No answer generated."),
            sources=[clean_file_path(s) for s in final_state.get("sources", [])],
            eval_score=final_state.get("eval_score", 0.0),
            eval_feedback=final_state.get("eval_feedback", ""),
            intent=final_state.get("intent", "explain")
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error running LangGraph query pipeline: {str(e)}"
        )

@router.get("/repos")
def list_repositories():
    """
    Retrieves indexed codebase repositories and statistics directly from Neo4j and Qdrant.
    """
    try:
        neo4j_uri = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
        neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        neo4j_password = os.getenv("NEO4J_PASSWORD", "password123")
        g_store = GraphStoreManager(uri=neo4j_uri, user=neo4j_user, password=neo4j_password)
        
        # Query total files, nodes, and relationships in the database
        res_files = g_store.run_query("MATCH (f:File) RETURN count(f) as file_count")
        res_nodes = g_store.run_query("MATCH (n) RETURN count(n) as node_count")
        res_edges = g_store.run_query("MATCH ()-[r]->() RETURN count(r) as edge_count")
        g_store.close()
        
        file_count = res_files[0]["file_count"] if res_files else 0
        node_count = res_nodes[0]["node_count"] if res_nodes else 0
        edge_count = res_edges[0]["edge_count"] if res_edges else 0
        
        # Connect to Qdrant to get collection count
        qdrant_host = os.getenv("QDRANT_HOST", "127.0.0.1")
        qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
        client = QdrantClient(host=qdrant_host, port=qdrant_port)
        collections = client.get_collections().collections
        has_collection = any(c.name == "codeatlas_code" for c in collections)
        
        chunk_count = 0
        if has_collection:
            coll_info = client.get_collection("codeatlas_code")
            chunk_count = coll_info.points_count
            
        if node_count == 0:
            return {"repos": []}
            
        return {
            "repos": [
                {
                    "id": "active_repo",
                    "name": "Indexed Workspace",
                    "url": "Local Databases",
                    "stats": {
                        "files": file_count,
                        "chunks": chunk_count,
                        "nodes": node_count,
                        "edges": edge_count
                    }
                }
            ]
        }
    except Exception as e:
        logger.error(f"Error listing workspace repositories: {e}", exc_info=True)
        # Return empty list if databases are currently empty or connecting fails
        return {"repos": []}

@router.delete("/repo/{repo_id}")
def delete_repository(repo_id: str):
    """
    Deletes the indexed codebase from both Qdrant and Neo4j, and clears local checkpoints.
    """
    try:
        # Clear Neo4j graph nodes and edges
        g_store = GraphStoreManager()
        g_store.run_query("MATCH (n) DETACH DELETE n")
        g_store.close()
        
        # Reset Qdrant Collection
        client = QdrantClient(host="127.0.0.1", port=6333)
        client.recreate_collection(
            collection_name="codeatlas_code",
            vectors_config={"size": 2048, "distance": "Cosine"}
        )
        
        # Clear local ingestion checkpoints
        checkpoint_file = os.path.abspath("./data/ingestion_checkpoints.json")
        if os.path.exists(checkpoint_file):
            try:
                os.remove(checkpoint_file)
                logger.info("Cleared local ingestion checkpoints file.")
            except Exception as ce:
                logger.warning(f"Failed to delete checkpoint file: {ce}")
                
        return {"deleted": True}
    except Exception as e:
        logger.error(f"Clear databases failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Clear failed: {str(e)}")

@router.get("/health")
def health_check():
    """
    Pings local Qdrant and Neo4j instances to check health, and verifies
    if the GROQ_API_KEY and NVIDIA_API_KEY are configured.
    """
    qdrant_status = "fail"
    neo4j_status = "fail"
    groq_status = "ok" if os.getenv("GROQ_API_KEY") else "fail"
    
    # Check if NVIDIA API key is configured
    nvidia_key = os.getenv("NVIDIA_API_KEY")
    nvidia_status = "ok" if (nvidia_key and nvidia_key != "your_nvidia_api_key_here") else "fail"
    
    try:
        q_client = QdrantClient(host="127.0.0.1", port=6333, timeout=1.0)
        q_client.get_collections()
        qdrant_status = "ok"
    except Exception:
        pass
        
    try:
        driver = GraphDatabase.driver("bolt://127.0.0.1:7687", auth=("neo4j", "password123"), connection_timeout=1.0)
        driver.verify_connectivity()
        driver.close()
        neo4j_status = "ok"
    except Exception:
        pass
        
    return {
        "qdrant": qdrant_status,
        "neo4j": neo4j_status,
        "groq": groq_status,
        "nvidia_api": nvidia_status,
        "status": "ok" if (qdrant_status == "ok" and neo4j_status == "ok" and nvidia_status == "ok") else "degraded"
    }

@router.get("/graph/{repo_id}")
def get_repository_graph(repo_id: str):
    """
    Queries Neo4j database to return structural nodes and edges formatted
    for interactive D3.js force-directed dependency graph.
    """
    g_store = GraphStoreManager()
    try:
        # 1. Query nodes (using elementId to prevent deprecation warning)
        node_query = """
        MATCH (n)
        RETURN 
            elementId(n) as node_id,
            labels(n)[0] as type,
            n.name as name,
            coalesce(n.file_path, n.absolute_path) as file_path,
            n.start_line as start_line,
            n.end_line as end_line
        """
        nodes_res = g_store.run_query(node_query)
        
        # 2. Query edges (using elementId to prevent deprecation warning)
        edge_query = """
        MATCH (src)-[r]->(dst)
        RETURN 
            elementId(src) as source_id, 
            elementId(dst) as target_id, 
            type(r) as type
        """
        edges_res = g_store.run_query(edge_query)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to query Neo4j graph database: {str(e)}"
        )
    finally:
        g_store.close()
        
    # 3. Format nodes for UI D3.js visualization
    nodes = []
    for row in nodes_res:
        node_id = str(row["node_id"])
        ntype = row["type"] or "Unknown"
        name = row["name"] or "Unnamed"
        file_path = row["file_path"]
        start_line = row["start_line"]
        end_line = row["end_line"]
        
        label = name
        if ntype == "File" and file_path:
            label = clean_file_path(file_path)
                
        node_data = {
            "id": node_id,
            "label": label,
            "type": ntype
        }
        if file_path:
            node_data["file"] = clean_file_path(file_path)
        if start_line is not None and end_line is not None:
            node_data["lines"] = f"{int(start_line)}-{int(end_line)}"
            
        nodes.append(node_data)
        
    # 4. Format edges/links for UI D3.js visualization
    edges = []
    for row in edges_res:
        edges.append({
            "source": str(row["source_id"]),
            "target": str(row["target_id"]),
            "type": row["type"]
        })
        
    return {"nodes": nodes, "edges": edges}

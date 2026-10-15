import os
import uuid
import shutil
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException
from api.models import IngestRequest, IngestResponse

# Core pipeline imports
from ingestion.cloner import clone_repository, walk_files
from ingestion.parser import CodeParser
from ingestion.chunker import SemanticChunker, CodeChunk
from ingestion.extractor import EntityRelationshipExtractor
from storage.embedder import CodeEmbedder
from storage.vector_store import VectorStoreManager
from storage.graph_store import GraphStoreManager
from ingestion.checkpoint import get_repo_checkpoint, mark_file_completed, calculate_file_hash

router = APIRouter()
logger = logging.getLogger(__name__)

JAVASCRIPT_EXTENSIONS = (".js", ".jsx", ".mjs", ".cjs")
DOCUMENTATION_EXTENSIONS = (".md", ".txt", ".rst")

# Global in-memory ingestion job progress registry
jobs_progress: Dict[str, Dict[str, Any]] = {}

def run_ingestion_pipeline(job_id: str, github_url: str, branch: Optional[str] = None, embedder: Optional[CodeEmbedder] = None):
    """
    Executes the ingestion pipeline in the background:
    Cloning -> Walking -> Parsing -> Chunking -> Embedding -> Database Storage.
    """
    jobs_progress[job_id] = {
        "status": "running",
        "progress_pct": 10,
        "message": "Cloning repository...",
        "stats": {"files": 0, "chunks": 0, "nodes": 0, "edges": 0}
    }
    
    # Store cloned repos in temporary data folder
    temp_dir = os.path.abspath(f"./data/temp_repos/{job_id}")
    
    try:
        # 1. Programmatically clone repository
        clone_repository(github_url, temp_dir, branch)
        
        # 2. Check checkpoints
        jobs_progress[job_id]["progress_pct"] = 20
        jobs_progress[job_id]["message"] = "Checking database status and checkpoints..."
        all_files = walk_files(temp_dir)
        
        if not all_files:
            raise ValueError("No code or documentation files found in the target repository branch.")
            
        checkpoint = get_repo_checkpoint(github_url)
        completed_files = checkpoint.get("files", {})
        
        files_to_process = []
        total_skipped = 0
        
        for fp in all_files:
            rel_path = os.path.relpath(fp, temp_dir).replace("\\", "/")
            f_hash = calculate_file_hash(fp)
            
            if rel_path in completed_files and completed_files[rel_path].get("hash") == f_hash and completed_files[rel_path].get("status") == "completed":
                total_skipped += 1
            else:
                files_to_process.append((fp, rel_path, f_hash))
                
        jobs_progress[job_id]["stats"]["files"] = len(all_files)
        logger.info(f"Checkpoint summary for {github_url}: {len(files_to_process)} to process, {total_skipped} skipped.")
        
        # Ensure collection exists in Qdrant (do not overwrite/recreate if it exists!)
        v_store = VectorStoreManager()
        v_store.ensure_collection_exists()
        
        # Initialize pipeline utilities
        chunker = SemanticChunker()
        extractor = EntityRelationshipExtractor()
        
        if embedder is None:
            embedder = CodeEmbedder()
            
        total_files = len(files_to_process)
        processed_count = 0
        
        # Stats accumulators
        total_chunks = 0
        total_nodes = 0
        total_edges = 0
        failed_files = []
        
        # Batch configuration
        FILE_BATCH_SIZE = 5
        
        if total_files > 0:
            for i in range(0, total_files, FILE_BATCH_SIZE):
                batch_files = files_to_process[i:i + FILE_BATCH_SIZE]
                
                batch_chunks = []
                batch_nodes = []
                batch_relationships = []
                successfully_processed_files = []
                
                # Parse and chunk files in the current batch
                for fp, rel_path, f_hash in batch_files:
                    try:
                        extension = os.path.splitext(fp)[1].lower()

                        if extension == ".py" or extension in JAVASCRIPT_EXTENSIONS:
                            language = (
                                "javascript"
                                if extension in JAVASCRIPT_EXTENSIONS
                                else "python"
                            )
                            parser = CodeParser(language=language)
                            ast_nodes = parser.parse_file(fp)

                            if ast_nodes.get("has_syntax_errors"):
                                logger.warning(
                                    "Syntax errors found in %s; indexing structures recovered by Tree-sitter.",
                                    rel_path,
                                )
                            
                            # Syntax-aware code chunking
                            chunks = chunker.chunk_file(fp, ast_nodes)
                            # Filter out empty or whitespace-only chunks to prevent embedding API failures
                            valid_chunks = [c for c in chunks if c.content and c.content.strip()]
                            batch_chunks.extend(valid_chunks)
                            
                            # Syntactic edge relationship extraction
                            relationships = extractor.extract_relationships(fp, ast_nodes)
                            batch_relationships.extend(relationships)
                            
                            for src, _, dst in relationships:
                                batch_nodes.append(src)
                                batch_nodes.append(dst)
                        elif extension in DOCUMENTATION_EXTENSIONS:
                            with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                                content = f.read()
                            
                            chunks = chunker.chunk_text_file(fp, content)
                            valid_chunks = [c for c in chunks if c.content and c.content.strip()]
                            batch_chunks.extend(valid_chunks)
                            
                            # Represent documentation files as File nodes in Neo4j
                            file_name = os.path.basename(fp)
                            doc_node = {
                                "name": file_name,
                                "label": "File",
                                "metadata": {
                                    "absolute_path": os.path.abspath(fp),
                                    "file_path": fp,
                                    "type": "documentation"
                                }
                            }
                            batch_nodes.append(doc_node)
                        else:
                            logger.warning(
                                "Skipping unsupported file type: %s",
                                rel_path,
                            )
                            successfully_processed_files.append(
                                (fp, rel_path, f_hash)
                            )
                            continue

                        successfully_processed_files.append(
                            (fp, rel_path, f_hash)
                        )
                    except Exception as e:
                        failed_files.append(rel_path)
                        logger.exception("Failed processing file %s: %s", rel_path, e)
                        
                # Generate embeddings for batch chunks
                if batch_chunks:
                    chunk_contents = [c.content for c in batch_chunks]
                    embeddings = embedder.embed_texts(chunk_contents)

                    if len(embeddings) != len(batch_chunks):
                        raise RuntimeError(
                            "Embedding service returned "
                            f"{len(embeddings)} vectors for {len(batch_chunks)} chunks."
                        )
                    
                    for chunk, emb in zip(batch_chunks, embeddings):
                        if len(emb) != v_store.vector_size:
                            raise ValueError(
                                f"Embedding for chunk {chunk.id} has dimension "
                                f"{len(emb)}; expected {v_store.vector_size}."
                            )
                        chunk.embedding = emb
                        
                    # Index batch chunks to Qdrant
                    v_store.upsert_chunks(batch_chunks)
                    
                # Index batch to Neo4j
                if batch_nodes or batch_relationships:
                    unique_nodes = {}
                    for node in batch_nodes:
                        key = (node["label"], node["name"], node["metadata"].get("file_path"))
                        unique_nodes[key] = node
                    deduped_nodes = list(unique_nodes.values())
                    
                    g_store = GraphStoreManager()
                    g_store.create_nodes_and_edges(deduped_nodes, batch_relationships)
                    g_store.close()
                    
                    total_nodes += len(deduped_nodes)
                    total_edges += len(batch_relationships)
                    
                total_chunks += len(batch_chunks)
                
                # Mark batch files as completed
                for fp, rel_path, f_hash in successfully_processed_files:
                    mark_file_completed(github_url, rel_path, f_hash)
                    
                processed_count += len(batch_files)
                
                # Update progress (from 30% to 90%)
                pct = 30 + int((processed_count / total_files) * 60)
                jobs_progress[job_id]["progress_pct"] = pct
                jobs_progress[job_id]["message"] = f"Processed {processed_count}/{total_files} files..."
                jobs_progress[job_id]["stats"]["chunks"] = total_chunks
                jobs_progress[job_id]["stats"]["nodes"] = total_nodes
                jobs_progress[job_id]["stats"]["edges"] = total_edges
        
        # 6. Mark job complete
        jobs_progress[job_id]["progress_pct"] = 100
        jobs_progress[job_id]["status"] = "completed"
        if total_files == 0:
            jobs_progress[job_id]["message"] = "Ingestion completed: All files are already up-to-date!"
        else:
            jobs_progress[job_id]["message"] = "Ingestion completed successfully!"
        if failed_files:
            jobs_progress[job_id]["message"] = (
                f"Ingestion completed with {len(failed_files)} file(s) failing "
                "processing. See server logs for details."
            )
            
    except Exception as e:
        logger.error(f"Error ingesting repository: {e}", exc_info=True)
        jobs_progress[job_id]["status"] = "failed"
        jobs_progress[job_id]["message"] = f"Ingestion failed: {str(e)}"
    finally:
        # Clean up cloned files to conserve host disk space
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

from fastapi import Request

@router.post("/ingest", response_model=IngestResponse)
def start_ingestion(ingest_req: IngestRequest, background_tasks: BackgroundTasks, request: Request):
    """
    Triggers repository ingestion asynchronously in the background.
    """
    import re
    # Clean and validate GitHub URL format
    url_cleaned = ingest_req.github_url.strip().rstrip("/")
    github_regex = r"^https?:\/\/(?:www\.)?github\.com\/[\w\-]+\/[\w\.-]+(?:\.git)?$"
    if not re.match(github_regex, url_cleaned):
        raise HTTPException(
            status_code=400,
            detail="Invalid GitHub repository URL format. Please use format: https://github.com/owner/repository"
        )
        
    job_id = str(uuid.uuid4())
    
    # Initialize task state
    jobs_progress[job_id] = {
        "status": "pending",
        "progress_pct": 0,
        "message": "Starting job...",
        "stats": {"files": 0, "chunks": 0, "nodes": 0, "edges": 0}
    }
    
    # Get the pre-loaded embedder from FastAPI app state
    shared_embedder = request.app.state.embedder
    
    # Run pipeline in background thread
    background_tasks.add_task(
        run_ingestion_pipeline,
        job_id,
        url_cleaned,
        ingest_req.branch,
        shared_embedder
    )
    
    return IngestResponse(
        job_id=job_id,
        status="pending"
    )

@router.get("/ingest/{job_id}")
def get_ingest_status(job_id: str):
    """
    Retrieves progress updates and stats for an ingestion job.
    """
    if job_id not in jobs_progress:
        raise HTTPException(status_code=404, detail="Ingestion job ID not found.")
        
    return jobs_progress[job_id]

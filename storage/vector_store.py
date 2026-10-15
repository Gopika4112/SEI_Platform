import uuid
import logging
import math
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter
from ingestion.chunker import CodeChunk

logger = logging.getLogger(__name__)

DEFAULT_VECTOR_SIZE = 2048

class VectorStoreManager:
    """
    Manages connections and operations on the Qdrant Vector Database,
    including collection setups, batch upserting, and filtered similarity searches.
    """
    def __init__(self, host: str = "127.0.0.1", port: int = 6333, collection_name: str = "codeatlas_code"):
        self.client = QdrantClient(host=host, port=port)
        self.collection_name = collection_name
        self.vector_size = DEFAULT_VECTOR_SIZE

    def setup_collection(self, vector_size: int = DEFAULT_VECTOR_SIZE):
        """
        Creates or resets the Qdrant collection for code embeddings.
        If the collection already exists, it is recreated.
        
        Args:
            vector_size: Dimension of the vectors (default: 2048 for NVIDIA Nemotron-3-Embed-1B).
        """
        # Recreate collection to reset indexing
        self.client.recreate_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
        )
        self.vector_size = vector_size

    def ensure_collection_exists(self, vector_size: int = DEFAULT_VECTOR_SIZE):
        """
        Ensures the collection exists in Qdrant. If it does not exist,
        initializes it. If it already exists, does nothing.
        """
        self.vector_size = vector_size
        try:
            self.client.get_collection(self.collection_name)
        except Exception:
            # Collection does not exist, set it up
            self.setup_collection(vector_size)

    def upsert_chunks(self, chunks: List[CodeChunk], batch_size: int = 100):
        """
        Upserts code embeddings and metadata payloads into the Qdrant collection.
        Uses deterministic UUIDs derived from chunk IDs to prevent duplicates on re-indexing.
        
        Args:
            chunks: A list of populated CodeChunk objects (with embeddings).
            batch_size: The maximum number of points to upload in a single request.
        """
        if not chunks:
            return
            
        points = []
        for chunk in chunks:
            if chunk.embedding is None:
                continue
                
            # Validate embedding format
            if not isinstance(chunk.embedding, list):
                logger.error(f"Chunk {chunk.id} embedding is not a list. Type: {type(chunk.embedding)}")
                continue
            if not all(isinstance(x, (int, float)) for x in chunk.embedding):
                logger.error(f"Chunk {chunk.id} embedding contains non-numeric elements.")
                continue
            if len(chunk.embedding) != self.vector_size:
                raise ValueError(
                    f"Chunk {chunk.id} embedding has dimension "
                    f"{len(chunk.embedding)}; expected {self.vector_size}."
                )
            if any(math.isnan(x) or math.isinf(x) for x in chunk.embedding):
                logger.error(f"Chunk {chunk.id} embedding contains NaN or Infinity values.")
                continue
                
            # Create a deterministic UUID based on unique chunk ID
            point_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk.id))
            
            # Construct Qdrant point structure
            points.append(
                PointStruct(
                    id=point_uuid,
                    vector=chunk.embedding,
                    payload={
                        "id": chunk.id,
                        "content": chunk.content,
                        **chunk.metadata
                    }
                )
            )
            
        if points:
            for i in range(0, len(points), batch_size):
                batch = points[i:i + batch_size]
                try:
                    self.client.upsert(
                        collection_name=self.collection_name,
                        points=batch
                    )
                except Exception as e:
                    logger.error("Qdrant upsert failed. Inspecting batch details:")
                    for idx, pt in enumerate(batch):
                        vec = pt.vector
                        logger.error(f"  Point {idx}: id={pt.id}, vector_type={type(vec)}, vector_len={len(vec) if hasattr(vec, '__len__') else 'N/A'}")
                        if isinstance(vec, list) and len(vec) > 0:
                            logger.error(f"  First 3 elements: {vec[:3]}")
                    raise e

    def search_similar(self, query_vector: List[float], top_k: int = 10, payload_filter: Optional[Filter] = None) -> List[Dict[str, Any]]:
        """
        Searches the collection for vectors similar to the query vector,
        optionally applying Qdrant payload filters.
        
        Args:
            query_vector: The embedded query vector.
            top_k: Number of search results to return (default: 10).
            payload_filter: Optional Qdrant Filter object.
            
        Returns:
            A list of dictionary results containing the matched payloads and scores.
        """
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=top_k,
            query_filter=payload_filter
        )
        
        return [
            {
                "id": hit.payload.get("id"),
                "content": hit.payload.get("content"),
                "score": hit.score,
                "metadata": {k: v for k, v in hit.payload.items() if k not in ("id", "content")}
            }
            for hit in results.points
        ]

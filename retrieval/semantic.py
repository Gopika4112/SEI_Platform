from typing import List, Dict, Any, Optional
from qdrant_client.models import Filter, FieldCondition, MatchValue
from storage.vector_store import VectorStoreManager
from storage.embedder import CodeEmbedder

class SemanticRetriever:
    """
    Handles similarity search in the Qdrant vector store by embedding
    queries and converting filters to Qdrant condition formats.
    """
    def __init__(self, vector_store: VectorStoreManager, embedder: CodeEmbedder):
        self.vector_store = vector_store
        self.embedder = embedder

    def retrieve(self, query: str, top_k: int = 10, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Embeds the query and searches the vector store for matching code chunks.
        
        Args:
            query: User's natural language question.
            top_k: Number of search hits to retrieve (default: 10).
            filters: Optional dictionary of metadata filters (e.g. {"entity_type": "function"}).
            
        Returns:
            A list of dictionary search hits containing scores, contents, and metadata.
        """
        if not query.strip():
            return []
            
        # 1. Embed query
        query_vectors = self.embedder.embed_texts([query], input_type="query")
        if not query_vectors:
            return []
        query_vector = query_vectors[0]
        
        # 2. Build Qdrant conditions filter
        qdrant_filter = None
        if filters:
            conditions = []
            for key, val in filters.items():
                conditions.append(
                    FieldCondition(
                        key=key,
                        match=MatchValue(value=val)
                    )
                )
            qdrant_filter = Filter(must=conditions)
            
        # 3. Query vector store
        return self.vector_store.search_similar(
            query_vector=query_vector,
            top_k=top_k,
            payload_filter=qdrant_filter
        )

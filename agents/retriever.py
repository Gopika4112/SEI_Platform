from typing import Dict, Any
from retrieval.semantic import SemanticRetriever

class RetrieverAgent:
    """
    Retriever Agent: Performs semantic similarity search over Qdrant
    based on the state's query and updates the shared state.
    """
    def __init__(self, semantic_retriever: SemanticRetriever):
        self.semantic_retriever = semantic_retriever

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retrieves matching code chunks from the vector database.
        
        Args:
            state: The shared LangGraph state dictionary.
            
        Returns:
            The updated state dictionary with 'vector_results'.
        """
        query = state.get("query", "")
        intent = state.get("intent", "search")
        entities = state.get("entities", [])
        
        # Determine filters
        filters = None
        # If the query intent is specifically about impact/tracing,
        # we can restrict vector search to functions/classes to avoid noise
        if intent in ("impact", "trace") and entities:
            # We don't apply strict payload filtering here to keep retrieval open,
            # but we can filter by entity type if requested.
            pass
            
        # Retrieve vector chunks
        hits = self.semantic_retriever.retrieve(
            query=query,
            top_k=10,
            filters=filters
        )
        
        state["vector_results"] = hits
        return state

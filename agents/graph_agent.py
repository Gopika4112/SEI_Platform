from typing import Dict, Any, List
from retrieval.graph import GraphRetriever

class GraphAgent:
    """
    Graph Agent: Traverses Neo4j structural relations using Cypher
    based on query entities and intent, and updates the shared state.
    """
    def __init__(self, graph_retriever: GraphRetriever):
        self.graph_retriever = graph_retriever

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes Cypher traversals in Neo4j and updates 'graph_results'.
        
        Args:
            state: The shared LangGraph state dictionary.
            
        Returns:
            The updated state dictionary with 'graph_results'.
        """
        intent = state.get("intent", "explain")
        entities = state.get("entities", [])
        
        graph_results = []
        
        # Traverse relationships for each target entity extracted
        for entity in entities:
            if intent in ("impact", "trace"):
                # Impact analysis traces callers of function/method
                callers = self.graph_retriever.find_callers(entity)
                graph_results.extend(callers)
                
                # Traces base class structures
                inheritance = self.graph_retriever.find_inheritance(entity)
                graph_results.extend(inheritance)
            elif intent == "docs":
                # For docs, get inheritance structures
                inheritance = self.graph_retriever.find_inheritance(entity)
                graph_results.extend(inheritance)
            elif intent == "explain":
                # For code explanation, get callers
                callers = self.graph_retriever.find_callers(entity)
                graph_results.extend(callers)
                
        # Deduplicate results in state
        unique_results = {}
        for res in graph_results:
            key = (res.get("file_path"), res.get("name"))
            unique_results[key] = res
            
        state["graph_results"] = list(unique_results.values())
        return state

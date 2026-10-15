from typing import List, Dict, Any, Optional
from qdrant_client.models import Filter, FieldCondition, MatchValue
from retrieval.semantic import SemanticRetriever
from retrieval.graph import GraphRetriever

class HybridRetriever:
    """
    Combines Qdrant vector retrieval and Neo4j graph traversal results.
    Deduplicates nodes, fetches code content, reranks using intent-based weights,
    and formats the final LLM-ready context.
    """
    def __init__(self, semantic_retriever: SemanticRetriever, graph_retriever: GraphRetriever):
        self.semantic_retriever = semantic_retriever
        self.graph_retriever = graph_retriever

    def retrieve_and_rerank(self, query: str, intent: str, entities: List[str], top_k: int = 8) -> List[Dict[str, Any]]:
        """
        Executes hybrid retrieval by running semantic search and structural graph traversal
        concurrently, merging results, and reranking based on query intent.
        
        Args:
            query: User's query string.
            intent: Query intent classification (search, impact, trace, docs, explain).
            entities: Extracted code entity names from the query.
            top_k: Number of final chunks to return (default: 8).
            
        Returns:
            A list of reranked code chunk dicts with metadata and content.
        """
        # 1. Fetch semantic chunks from Qdrant
        semantic_hits = self.semantic_retriever.retrieve(query, top_k=top_k * 2)
        
        # 2. Fetch structural nodes from Neo4j
        graph_nodes = []
        for entity in entities:
            # Query callers/callees
            callers = self.graph_retriever.find_callers(entity)
            graph_nodes.extend(callers)
            
            # Query inheritance relationships
            inheritance = self.graph_retriever.find_inheritance(entity)
            graph_nodes.extend(inheritance)
            
        # Deduplicate graph nodes by file_path and name
        unique_nodes = {}
        for node in graph_nodes:
            key = (node["file_path"], node["name"])
            unique_nodes[key] = node
        deduped_nodes = list(unique_nodes.values())

        # 3. Fetch raw code contents for Neo4j nodes from Qdrant using payload filtering
        graph_chunks = []
        for node in deduped_nodes:
            # Search Qdrant for a chunk matching the exact name and file path
            conditions = [
                FieldCondition(key="name", match=MatchValue(value=node["name"])),
                FieldCondition(key="file_path", match=MatchValue(value=node["file_path"]))
            ]
            payload_filter = Filter(must=conditions)
            
            # Dummy vector lookup to trigger payload filtering on Qdrant
            dummy_vector = [0.0] * 768
            hits = self.semantic_retriever.vector_store.search_similar(
                query_vector=dummy_vector,
                top_k=1,
                payload_filter=payload_filter
            )
            if hits:
                graph_chunks.append({
                    "id": hits[0]["id"],
                    "content": hits[0]["content"],
                    "score": 0.9,  # Base structural match relevance score
                    "metadata": hits[0]["metadata"]
                })

        # 4. Merge and Deduplicate Results
        merged_chunks = {}
        
        # Add semantic hits
        for hit in semantic_hits:
            chunk_id = hit["id"]
            merged_chunks[chunk_id] = {
                "id": chunk_id,
                "content": hit["content"],
                "vector_score": hit["score"],
                "graph_score": 0.0,
                "metadata": hit["metadata"],
                "source": "vector"
            }
            
        # Add graph hits
        for g_hit in graph_chunks:
            chunk_id = g_hit["id"]
            if chunk_id in merged_chunks:
                # Node was found in both vector and graph searches
                merged_chunks[chunk_id]["graph_score"] = g_hit["score"]
                merged_chunks[chunk_id]["source"] = "hybrid"
            else:
                merged_chunks[chunk_id] = {
                    "id": chunk_id,
                    "content": g_hit["content"],
                    "vector_score": 0.0,
                    "graph_score": g_hit["score"],
                    "metadata": g_hit["metadata"],
                    "source": "graph"
                }

        # 5. Rerank Chunks using Intent-based Weights
        # Establish retrieval weights based on intent classification
        intent_lower = intent.lower()
        if intent_lower in ("impact", "trace", "dependency"):
            w_vector = 0.3
            w_graph = 0.7
        elif intent_lower in ("search", "docs", "explain"):
            w_vector = 0.8
            w_graph = 0.2
        else:
            w_vector = 0.6
            w_graph = 0.4
            
        reranked_list = []
        for chunk in merged_chunks.values():
            final_score = (chunk["vector_score"] * w_vector) + (chunk["graph_score"] * w_graph)
            chunk["final_score"] = final_score
            reranked_list.append(chunk)
            
        # Sort by final score descending
        reranked_list.sort(key=lambda x: x["final_score"], reverse=True)
        return reranked_list[:top_k]

    def format_context(self, chunks: List[Dict[str, Any]]) -> str:
        """
        Formats list of reranked chunks into structured LLM prompt context blocks.
        """
        formatted_blocks = []
        for chunk in chunks:
            meta = chunk["metadata"]
            entity_name = meta.get("name", "Module")
            entity_type = meta.get("entity_type", "unknown")
            file_path = meta.get("file_path", "unknown_file.py")
            source = chunk["source"]
            
            block = (
                f"[File: {file_path} | Entity: {entity_name} | Type: {entity_type} | Source: {source}]\n"
                f"{chunk['content']}\n"
                f"{'-'*40}"
            )
            formatted_blocks.append(block)
            
        return "\n\n".join(formatted_blocks)

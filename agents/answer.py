import os
import re
import logging
from typing import Dict, Any, List, Optional
from groq import Groq
from retrieval.hybrid import HybridRetriever

logger = logging.getLogger(__name__)

class AnswerAgent:
    """
    Answer Agent: Combines retrieval results, builds the prompt context,
    and calls Groq to generate a markdown answer with cited source files.
    """
    def __init__(self, hybrid_retriever: HybridRetriever, api_key: Optional[str] = None):
        self.hybrid_retriever = hybrid_retriever
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.groq_client = Groq(api_key=self.api_key) if self.api_key else None

    def synthesize(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merges vector and graph results, formats LLM prompt, pings Groq,
        and parses cited source file paths.
        
        Args:
            state: The shared LangGraph state dictionary.
            
        Returns:
            The updated state dictionary with 'answer' and 'sources'.
        """
        query = state.get("query", "")
        intent = state.get("intent", "explain")
        entities = state.get("entities", [])
        vector_hits = state.get("vector_results", [])
        graph_hits = state.get("graph_results", [])
        corrector_feedback = state.get("eval_feedback", "")
        
        # 1. Merge and Rerank results via HybridRetriever logic
        # Construct merged structure to pass to the hybrid context formatter
        merged_chunks = {}
        for hit in vector_hits:
            chunk_id = hit["id"]
            merged_chunks[chunk_id] = {
                "id": chunk_id,
                "content": hit["content"],
                "metadata": hit["metadata"],
                "source": "vector"
            }
            
        for g_hit in graph_hits:
            # Graph hits are nodes. Check if they have chunk content
            # (Note: In the agent flow, the nodes were already fetched)
            chunk_id = g_hit.get("id") or f"{g_hit.get('file_path')}::generic::{g_hit.get('name')}"
            if chunk_id in merged_chunks:
                merged_chunks[chunk_id]["source"] = "hybrid"
            else:
                merged_chunks[chunk_id] = {
                    "id": chunk_id,
                    "content": g_hit.get("content", f"# Node: {g_hit.get('name')}\n# (No code content loaded)"),
                    "metadata": {
                        "name": g_hit.get("name"),
                        "file_path": g_hit.get("file_path"),
                        "entity_type": g_hit.get("entity_type", "unknown")
                    },
                    "source": "graph"
                }
                
        # Format the context blocks for the LLM
        formatted_context = self.hybrid_retriever.format_context(list(merged_chunks.values()))
        
        if not self.groq_client:
            logger.warning("Groq API key not set. Using mock response for Answer Agent.")
            state["answer"] = f"Mock answer for: '{query}'. Enable API keys to get LLM answers."
            state["sources"] = ["mock_file.py"]
            return state

        # 2. Build system and user prompts
        system_prompt = (
            "You are the Answer Agent for CodeAtlas, an advanced codebase analysis platform.\n"
            "Your job is to answer the user's natural language query using the provided code context.\n\n"
            "Instructions:\n"
            "- Rely ONLY on the code snippets provided in the context.\n"
            "- You MUST cite the source file path for every code detail or explanation you give.\n"
            "- Use standard brackets for citations, e.g. [path/to/file.py].\n"
            "- At the end of your response, add a section '### Cited Source Files:' listing all files.\n"
            "- Write in clean, structured markdown format."
        )
        
        user_content = f"Query: {query}\n\nCode Context:\n{formatted_context}"
        
        # Include corrective feedback if we are in a loop retry
        if corrector_feedback and state.get("eval_score", 1.0) < 0.6:
            user_content += (
                f"\n\n--- WARNING: Previous Answer attempt failed evaluation: ---\n"
                f"Feedback: {corrector_feedback}\n"
                f"Please rewrite the answer, correcting these issues and ensuring complete grounding."
            )
            
        try:
            chat_completion = self.groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                model="qwen/qwen3.8-27b",  # Large model for reasoning
                temperature=0.5
            )
            
            answer = chat_completion.choices[0].message.content
            
            # 3. Parse cited source files using regex
            # Find any [filename.py] citations
            citations = re.findall(r"\[([\w\/\.-]+\.py)\]", answer)
            
            # Find citations in the final section
            cited_files = list(set(citations))
            
            state["answer"] = answer
            state["sources"] = cited_files
            
        except Exception as e:
            logger.error(f"Answer Agent LLM call failed: {e}")
            state["answer"] = f"Failed to synthesize answer due to LLM error: {str(e)}"
            state["sources"] = []
            
        return state

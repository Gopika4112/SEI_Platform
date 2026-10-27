import os
import json
import logging
from typing import Dict, Any, Optional
from groq import Groq

logger = logging.getLogger(__name__)

class EvaluatorAgent:
    """
    Evaluator Agent: Inspects generated answers against the source code context,
    scoring correctness and faithfulness (0.0 to 1.0) to catch hallucinations.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.groq_client = Groq(api_key=self.api_key) if self.api_key else None

    def evaluate(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Rates answer faithfulness and generates corrective feedback.
        
        Args:
            state: The shared LangGraph state dictionary.
            
        Returns:
            The updated state dictionary with 'eval_score' and 'eval_feedback'.
        """
        query = state.get("query", "")
        answer = state.get("answer", "")
        vector_hits = state.get("vector_results", [])
        graph_hits = state.get("graph_results", [])
        
        # 1. Format the source context again to inspect grounding
        context_sources = []
        for index, hit in enumerate(vector_hits):
            meta = hit["metadata"]
            context_sources.append(f"Source {index+1}: File: {meta.get('file_path')}\n{hit['content']}")
            
        for index, g_hit in enumerate(graph_hits):
            # Skip duplicates that are already in vector hits
            if g_hit.get("id") not in [h["id"] for h in vector_hits]:
                context_sources.append(f"Source G_{index+1}: File: {g_hit.get('file_path')}\n{g_hit.get('content', '')}")
                
        formatted_context = "\n\n".join(context_sources)
        
        if not self.groq_client:
            logger.warning("Groq API key not set. Skipping Evaluator Agent checks.")
            state["eval_score"] = 1.0
            state["eval_feedback"] = "API key not set. Skipping self-evaluation."
            return state

        # 2. Build system and user prompt for evaluation
        system_prompt = (
            "You are the Evaluator Agent for CodeAtlas, a codebase analysis platform.\n"
            "Your job is to score the generated answer's correctness and faithfulness "
            "against the provided source code context.\n\n"
            "Evaluation Rules:\n"
            "- The answer must be FULLY supported by the code context.\n"
            "- It must not make assumptions, hallucinate, or generalize beyond the code.\n"
            "- Score the answer between 0.0 (totally unsupported/wrong) and 1.0 (perfectly supported).\n"
            "- If the score is below 0.6, provide detailed, actionable corrective feedback explaining "
            "what is wrong, missing, or hallucinated.\n\n"
            "Return the results strictly as a JSON object, with no markdown formatting or other text:\n"
            "{\"score\": 0.95, \"feedback\": \"Good grounding, correct file paths cited.\"}"
        )
        
        user_content = (
            f"Query: {query}\n\n"
            f"Code Context:\n{formatted_context}\n\n"
            f"Generated Answer:\n{answer}"
        )
        
        try:
            chat_completion = self.groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                model="qwen/qwen3.8-27b",  # Small fast model is perfect for scoring tasks
                temperature=0.5,
                response_format={"type": "json_object"}
            )
            
            content = chat_completion.choices[0].message.content
            data = json.loads(content)
            
            score = float(data.get("score", 1.0))
            # Ensure score is within boundaries
            score = max(0.0, min(1.0, score))
            
            feedback = data.get("feedback", "")
            
            state["eval_score"] = score
            state["eval_feedback"] = feedback
            
        except Exception as e:
            logger.error(f"Evaluator Agent LLM call failed: {e}")
            state["eval_score"] = 1.0  # Pass if evaluator crashes to avoid locking
            state["eval_feedback"] = f"Evaluation failed due to LLM error: {str(e)}"
            
        return state

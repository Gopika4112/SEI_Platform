import os
import re
import json
import logging
from typing import Dict, Any, List, Optional
from groq import Groq

logger = logging.getLogger(__name__)

class PlannerAgent:
    """
    Planner Agent: Analyzes the user's query, classifies the intent,
    and extracts mentioned code entity names (functions, classes, methods).
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.groq_client = Groq(api_key=self.api_key) if self.api_key else None

    def plan(self, query: str) -> Dict[str, Any]:
        """
        Classifies intent and extracts entities.
        
        Intents:
        - search: Semantic searching for concepts.
        - impact: Tracing fallout of changing a class/function.
        - trace: Call chain tracing.
        - docs: Generating documentation.
        - explain: Explaining code behavior.
        
        Returns:
            A dictionary with keys 'intent' (str) and 'entities' (list of strings).
        """
        if not self.groq_client:
            logger.warning("Groq API key not set. Using fallback values for Planner Agent.")
            return {
                "intent": "explain",
                "entities": self._regex_extract_entities(query)
            }
            
        system_prompt = (
            "You are the Planner Agent for CodeAtlas, a codebase analysis platform.\n"
            "Analyze the user's natural language query and do two things:\n"
            "1. Classify the query's intent into exactly one of these categories:\n"
            "   - 'search': Conceptual questions (e.g. 'how does authentication work?').\n"
            "   - 'impact': Questions about changes/impacts (e.g. 'what breaks if I change login?').\n"
            "   - 'trace': Call chain tracing (e.g. 'trace the login call path').\n"
            "   - 'docs': Documentation requests (e.g. 'generate docs for UserService').\n"
            "   - 'explain': Code logic explanations (e.g. 'explain how this hashing function works').\n"
            "2. Extract any specific Python class, function, or method names mentioned in the query.\n\n"
            "Return the results strictly as a JSON object, with no markdown formatting or other text:\n"
            "{\"intent\": \"explain\", \"entities\": [\"UserService\"]}"
        )
        
        try:
            chat_completion = self.groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                model="qwen/qwen3.8-27b",
                temperature=0.5,
                response_format={"type": "json_object"}
            )
            
            content = chat_completion.choices[0].message.content
            data = json.loads(content)
            
            # Sanity checks
            intent = data.get("intent", "explain")
            if intent not in ("search", "impact", "trace", "docs", "explain"):
                intent = "explain"
                
            entities = data.get("entities", [])
            return {
                "intent": intent,
                "entities": [str(e) for e in entities]
            }
        except Exception as e:
            logger.error(f"Planner Agent LLM call failed: {e}. Falling back to default.")
            return {
                "intent": "explain",
                "entities": self._regex_extract_entities(query)
            }

    def _regex_extract_entities(self, query: str) -> List[str]:
        """
        Regex fallback to extract potential CamelCase (Classes) or snake_case (Functions) names.
        """
        words = re.findall(r"\b[a-zA-Z_]\w*\b", query)
        stopwords = {
            "class", "def", "function", "method", "import", "from", "calls", "who", "what",
            "where", "how", "trace", "find", "show", "dependency", "inherits", "app", "code", "file"
        }
        
        entities = []
        for word in words:
            if word.lower() in stopwords:
                continue
            if word[0].isupper() or "_" in word:
                entities.append(word)
        return list(set(entities))

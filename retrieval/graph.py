import os
import re
import json
import logging
from typing import List, Dict, Any
from groq import Groq
from storage.graph_store import GraphStoreManager

logger = logging.getLogger(__name__)

class GraphRetriever:
    """
    Handles graph queries in Neo4j (callers, inheritance, dependencies)
    and utilizes Groq to extract entity names from natural language queries.
    """
    def __init__(self, graph_store: GraphStoreManager):
        self.graph_store = graph_store
        api_key = os.getenv("GROQ_API_KEY")
        self.groq_client = Groq(api_key=api_key) if api_key else None

    def extract_entity_names(self, query: str) -> List[str]:
        """
        Uses Groq LLM to parse the query and extract mentioned Python classes or functions.
        Falls back to a regular expression parser if Groq API key is missing or fails.
        """
        if not self.groq_client:
            logger.warning("Groq API key not set. Using regex fallback for entity extraction.")
            return self._regex_extract_entities(query)
            
        system_prompt = (
            "You are a code syntax analyzer. Extract only specific Python class, function, or "
            "method names mentioned in the user's query. Return the results strictly as a JSON "
            "list of strings (e.g. [\"AuthService\", \"login_user\"]). Do not return any markdown "
            "formatting, introductory text, explanations, or comments. If no entities are found, return []."
        )
        
        try:
            chat_completion = self.groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                model="openai/gpt-oss-20b",
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            
            content = chat_completion.choices[0].message.content
            data = json.loads(content)
            # Find any list in the JSON object
            for val in data.values():
                if isinstance(val, list):
                    return [str(item) for item in val]
            return []
        except Exception as e:
            logger.error(f"Groq entity extraction failed: {e}. Falling back to regex.")
            return self._regex_extract_entities(query)

    def _regex_extract_entities(self, query: str) -> List[str]:
        """
        Regex fallback to extract potential CamelCase (Classes) or snake_case (Functions) names.
        """
        # Find alphanumeric words starting with letters
        words = re.findall(r"\b[a-zA-Z_]\w*\b", query)
        stopwords = {
            "class", "def", "function", "method", "import", "from", "calls", "who", "what",
            "where", "how", "trace", "find", "show", "dependency", "inherits", "app", "code", "file"
        }
        
        entities = []
        for word in words:
            if word.lower() in stopwords:
                continue
            # Accept CamelCase (Class names) or snake_case/words with underscores (Function names)
            if word[0].isupper() or "_" in word:
                entities.append(word)
        return list(set(entities))

    def find_callers(self, function_name: str) -> List[Dict[str, Any]]:
        """
        Queries Neo4j to find functions or methods that call the target function.
        
        Args:
            function_name: Name of the called function.
            
        Returns:
            A list of dictionary node descriptions (name, file_path, entity_type).
        """
        cypher = """
        MATCH (caller)-[:CALLS]->(func)
        WHERE func.name = $name
        RETURN caller.file_path as file_path, caller.name as name, labels(caller)[0] as entity_type
        """
        return self.graph_store.run_query(cypher, {"name": function_name})

    def find_inheritance(self, class_name: str) -> List[Dict[str, Any]]:
        """
        Queries Neo4j to trace inheritance structures (bases and subclasses) up to depth 2.
        
        Args:
            class_name: Name of the class node.
            
        Returns:
            A list of related Class nodes.
        """
        cypher = """
        MATCH (c:Class {name: $name})-[r:INHERITS*1..2]-(other:Class)
        RETURN other.file_path as file_path, other.name as name, labels(other)[0] as entity_type
        """
        return self.graph_store.run_query(cypher, {"name": class_name})

    def find_dependencies(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Queries Neo4j to retrieve the import modules of a file.
        
        Args:
            file_path: The absolute path of the file.
            
        Returns:
            A list of Module nodes imported.
        """
        cypher = """
        MATCH (f:File {file_path: $path})-[:IMPORTS]->(mod:Module)
        RETURN mod.name as name, labels(mod)[0] as entity_type
        """
        return self.graph_store.run_query(cypher, {"path": file_path})

import os
import time
import logging
import math
from typing import List
from openai import OpenAI
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load env variables (useful when run standalone)
load_dotenv()

class CodeEmbedder:
    """
    Wraps the NVIDIA embedding API to generate embeddings
    using the OpenAI-compatible Python client.
    """
    def __init__(self, model_name: str = None):
        self.api_key = os.getenv("NVIDIA_API_KEY")
        self.model = model_name or os.getenv("NVIDIA_EMBED_MODEL", "nvidia/nemotron-3-embed-1b")
        self.base_url = "https://integrate.api.nvidia.com/v1"
        self.client = None
        
        if self.api_key and self.api_key != "your_nvidia_api_key_here":
            self.client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key
            )

    def embed_texts(self, texts: List[str], input_type: str = "passage", batch_size: int = 96) -> List[List[float]]:
        """
        Embeds a list of strings in batches using the NVIDIA API.
        
        Args:
            texts: List of raw strings/code to embed.
            input_type: "passage" for indexing, "query" for retrieval.
            batch_size: Processing batch size (default: 96, NVIDIA API max limit).
            
        Returns:
            A list of 2048-dimensional float vectors for the configured model.
        """
        if not texts:
            return []
            
        if not self.client:
            # Re-attempt client initialization in case env was updated dynamically
            self.api_key = os.getenv("NVIDIA_API_KEY")
            if not self.api_key or self.api_key == "your_nvidia_api_key_here":
                raise ValueError("NVIDIA_API_KEY is not set or is still the placeholder. Please set it in your .env file.")
            self.client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key
            )

        embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = self._embed_batch_with_retry(batch, input_type)
            embeddings.extend(batch_embeddings)
            
        return embeddings

    def _embed_batch_with_retry(self, batch: List[str], input_type: str, max_retries: int = 5) -> List[List[float]]:
        delay = 1.0  # initial delay in seconds
        for attempt in range(max_retries):
            try:
                response = self.client.embeddings.create(
                    input=batch,
                    model=self.model,
                    extra_body={
                        "input_type": input_type,
                        "truncate": "END"
                    }
                )
                embeddings = []
                for data in response.data:
                    emb = data.embedding
                    if any(math.isnan(x) or math.isinf(x) for x in emb):
                        logger.warning("NVIDIA Embedding API returned NaN or Infinity values. Cleaning them to 0.0.")
                        emb = [0.0 if (math.isnan(x) or math.isinf(x)) else x for x in emb]
                    embeddings.append(emb)
                return embeddings
            except Exception as e:
                # If we've exhausted retries, raise the exception
                if attempt == max_retries - 1:
                    raise RuntimeError(f"Failed to generate embeddings after {max_retries} attempts: {e}") from e
                
                # Exponential backoff with jitter
                time.sleep(delay)
                delay *= 2.0

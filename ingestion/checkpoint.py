import os
import json
import hashlib
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

CHECKPOINT_FILE = os.path.abspath("./data/ingestion_checkpoints.json")

def load_checkpoints() -> Dict[str, Any]:
    """Loads completed file checkpoints from a local JSON file."""
    if not os.path.exists(CHECKPOINT_FILE):
        return {}
    try:
        with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load checkpoints: {e}")
        return {}

def save_checkpoints(checkpoints: Dict[str, Any]):
    """Saves checkpoints dictionary to the local JSON file."""
    try:
        os.makedirs(os.path.dirname(CHECKPOINT_FILE), exist_ok=True)
        with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
            json.dump(checkpoints, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save checkpoints: {e}")

def get_repo_checkpoint(repo_url: str) -> Dict[str, Any]:
    """Returns the checkpoint dictionary for a specific repository URL."""
    checkpoints = load_checkpoints()
    normalized_url = repo_url.strip().lower()
    return checkpoints.get(normalized_url, {"files": {}})

def mark_file_completed(repo_url: str, file_path: str, file_hash: str):
    """Marks a single file as completed under the repo URL in the checkpoints."""
    checkpoints = load_checkpoints()
    normalized_url = repo_url.strip().lower()
    
    if normalized_url not in checkpoints:
        checkpoints[normalized_url] = {"files": {}}
        
    checkpoints[normalized_url]["files"][file_path] = {
        "hash": file_hash,
        "status": "completed"
    }
    save_checkpoints(checkpoints)

def calculate_file_hash(absolute_path: str) -> str:
    """Calculates the MD5 hash of a file's content to check for changes."""
    hasher = hashlib.md5()
    try:
        with open(absolute_path, "rb") as f:
            buf = f.read()
            hasher.update(buf)
        return hasher.hexdigest()
    except Exception as e:
        logger.error(f"Failed to calculate hash for file {absolute_path}: {e}")
        return ""

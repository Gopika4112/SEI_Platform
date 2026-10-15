import os
import git
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)

def clone_repository(repo_url: str, dest_dir: str, branch: Optional[str] = None) -> str:
    """
    Clones a GitHub repository to a local destination directory.
    
    Args:
        repo_url: The full HTTPS URL of the GitHub repository.
        dest_dir: The directory where the repository should be cloned.
        branch: Optional branch name to clone.
        
    Returns:
        The absolute path to the cloned repository.
    """
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)
        
    # Support private repository token injection if present
    token = os.getenv("GITHUB_TOKEN")
    if token and "github.com" in repo_url and not repo_url.startswith("git@"):
        if repo_url.startswith("https://"):
            repo_url = repo_url.replace("https://", f"https://{token}@")
            
    logger.info(f"Cloning {repo_url} into {dest_dir} (branch: {branch or 'default'})")
    
    clone_kwargs = {}
    if branch:
        clone_kwargs["branch"] = branch
        
    # Check if directory already contains a git repository
    git_dir = os.path.join(dest_dir, ".git")
    if os.path.exists(git_dir):
        logger.info("Repository already exists. Opening existing instance.")
        # Make sure it's valid, otherwise clone new
        try:
            repo = git.Repo(dest_dir)
            # Fetch and pull latest changes
            repo.remotes.origin.pull()
        except Exception as e:
            logger.warning(f"Failed to pull existing repo: {e}. Re-cloning.")
            import shutil
            shutil.rmtree(dest_dir)
            os.makedirs(dest_dir)
            git.Repo.clone_from(repo_url, dest_dir, **clone_kwargs)
    else:
        git.Repo.clone_from(repo_url, dest_dir, **clone_kwargs)
        
    return os.path.abspath(dest_dir)

def walk_files(repo_path: str) -> List[str]:
    """
    Recursively walks a repository directory path, returning a list of paths
    to supported Python/JavaScript source and documentation files while ignoring
    standard virtual environments, dependency folders, and system directories.
    
    Args:
        repo_path: The directory path to search.
        
    Returns:
        A list of absolute paths to all discovered code and documentation files.
    """
    ignored_dirs = {
        ".git", "__pycache__", "node_modules", "venv", "atlas_venv",
        ".pytest_cache", ".qdrant", ".neo4j", "data", "build", "dist",
        "coverage", "vendor", "target"
    }
    supported_extensions = (
    ".py",
    ".js", ".jsx", ".mjs", ".cjs",
    ".md", ".txt", ".rst",
)
    discovered_files = []
    
    for root, dirs, files in os.walk(repo_path):
        # Exclude directories starting with '.' and ignored names
        dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith(".")]
        
        for file in files:
            if file.lower().endswith(supported_extensions):
                discovered_files.append(os.path.abspath(os.path.join(root, file)))
                
    return discovered_files

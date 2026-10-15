import os
import shutil
import pytest
from ingestion.checkpoint import (
    CHECKPOINT_FILE,
    load_checkpoints,
    save_checkpoints,
    get_repo_checkpoint,
    mark_file_completed,
    calculate_file_hash
)

@pytest.fixture(autouse=True)
def clean_checkpoints():
    """Fixture to backup and restore the checkpoints JSON file before and after tests."""
    backup_path = CHECKPOINT_FILE + ".bak"
    has_backup = False
    
    if os.path.exists(CHECKPOINT_FILE):
        shutil.copy2(CHECKPOINT_FILE, backup_path)
        os.remove(CHECKPOINT_FILE)
        has_backup = True
        
    yield
    
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)
        
    if has_backup:
        shutil.move(backup_path, CHECKPOINT_FILE)

def test_file_hashing(tmp_path):
    # Create a dummy file
    dummy_file = tmp_path / "dummy.txt"
    dummy_file.write_text("Hello, CodeAtlas!", encoding="utf-8")
    
    hash1 = calculate_file_hash(str(dummy_file))
    assert len(hash1) == 32
    
    # Change content
    dummy_file.write_text("Hello, CodeAtlas! modified.", encoding="utf-8")
    hash2 = calculate_file_hash(str(dummy_file))
    assert hash1 != hash2

def test_load_save_checkpoints():
    # Verify initial is empty dict
    assert load_checkpoints() == {}
    
    # Save dummy checkpoints
    data = {"test-repo": {"files": {"file1.py": {"hash": "abc", "status": "completed"}}}}
    save_checkpoints(data)
    
    loaded = load_checkpoints()
    assert loaded == data

def test_mark_file_completed_and_get():
    repo = "https://github.com/mock/repo"
    file_path = "src/utils.py"
    file_hash = "f123456789abcdef"
    
    mark_file_completed(repo, file_path, file_hash)
    
    # Get and verify
    repo_state = get_repo_checkpoint(repo)
    assert file_path in repo_state["files"]
    assert repo_state["files"][file_path]["hash"] == file_hash
    assert repo_state["files"][file_path]["status"] == "completed"
    
    # Test case insensitivity/stripping on repo URL lookup
    repo_space_upper = "  HTTPS://github.com/mock/repo  "
    repo_state_alt = get_repo_checkpoint(repo_space_upper)
    assert file_path in repo_state_alt["files"]

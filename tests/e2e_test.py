import os
import subprocess
import sqlite3
import tempfile
import shutil
from unittest.mock import patch
from click.testing import CliRunner
from relocase import cli

def create_file(path, content):
    """Create a file with the given content."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)

@patch("relocase.get_fs_root")
def test_end_to_end_scenario(mock_get_fs_root):
    """
    Test a complete end-to-end scenario using a real filesystem,
    allowing calls to external commands like md5sum and rsync.
    """
    runner = CliRunner()
    test_dir = tempfile.mkdtemp()
    # Mock the get_fs_root function to return our temporary directory.
    # This ensures the database is created inside the test directory
    # instead of the real filesystem root or home directory.
    mock_get_fs_root.return_value = test_dir

    try:
        source_dir = os.path.join(test_dir, "source")
        target_dir = os.path.join(test_dir, "target")

        # Setup source and target directories
        os.makedirs(os.path.join(source_dir, "dir1/subdir1"))
        os.makedirs(os.path.join(source_dir, "dir2"))
        create_file(os.path.join(source_dir, "file1.txt"), "content1")
        create_file(os.path.join(source_dir, "dir1/file2.txt"), "content2")
        create_file(os.path.join(source_dir, "dir1/subdir1/file3.txt"), "content3")
        create_file(os.path.join(source_dir, "dir2/file4.txt"), "content1")  # Duplicate content

        os.makedirs(os.path.join(target_dir, "existing_dir"))
        create_file(os.path.join(target_dir, "existing_dir/file5.txt"), "content2") # This file should be moved

        # First run: Transfer all files
        result = runner.invoke(cli, [source_dir, target_dir], catch_exceptions=False)
        assert result.exit_code == 0, result.output

        # Verify files are transferred or moved
        assert os.path.exists(os.path.join(target_dir, "file1.txt"))
        assert os.path.exists(os.path.join(target_dir, "dir1/subdir1/file3.txt"))
        assert os.path.exists(os.path.join(target_dir, "dir2/file4.txt"))
        assert os.path.exists(os.path.join(target_dir, "dir1/file2.txt")) # This was a move
        assert not os.path.exists(os.path.join(target_dir, "existing_dir/file5.txt"))

        # Check database entries
        db_path = os.path.join(test_dir, ".relocase.db")
        assert os.path.exists(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM md5_cache")
        assert cursor.fetchone()[0] == 4
        conn.close()

        # Second run: No changes should occur
        result = runner.invoke(cli, [source_dir, target_dir], catch_exceptions=False)
        assert result.exit_code == 0, result.output
        assert "Would transfer" not in result.output
        assert "Would move" not in result.output
    finally:
        # Clean up the temporary directory
        shutil.rmtree(test_dir)

import os
import subprocess
import sqlite3
from click.testing import CliRunner
from relocase import cli

def create_file(path, content):
    """Create a file with the given content."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)

def test_end_to_end_scenario():
    """Test a complete end-to-end scenario with real rsync and md5sum."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Setup source and target directories
        os.makedirs("source/dir1/subdir1")
        os.makedirs("source/dir2")
        create_file("source/file1.txt", "content1")
        create_file("source/dir1/file2.txt", "content2")
        create_file("source/dir1/subdir1/file3.txt", "content3")
        create_file("source/dir2/file4.txt", "content1")  # Duplicate content

        os.makedirs("target/existing_dir")
        create_file("target/existing_dir/file5.txt", "content2") # This file should be moved

        # First run: Transfer all files
        result = runner.invoke(cli, ["source", "target"])
        assert result.exit_code == 0

        # Verify files are transferred or moved
        assert os.path.exists("target/file1.txt")
        assert os.path.exists("target/dir1/subdir1/file3.txt")
        assert os.path.exists("target/dir2/file4.txt")
        assert os.path.exists("target/dir1/file2.txt") # This was a move
        assert not os.path.exists("target/existing_dir/file5.txt")


        # Check database entries
        db_path = os.path.join("target", ".relocase.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM md5_cache")
        assert cursor.fetchone()[0] == 4
        conn.close()

        # Second run: No changes
        result = runner.invoke(cli, ["source", "target"])
        assert result.exit_code == 0
        assert "Would transfer" not in result.output
        assert "Would move" not in result.output

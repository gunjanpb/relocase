import os
import hashlib
import sqlite3
from click.testing import CliRunner
from src.main import cli
from unittest.mock import patch, MagicMock

def create_file(path, content):
    """Create a file with the given content."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)

def get_md5_from_content(content):
    """Get the MD5 checksum of a string."""
    return hashlib.md5(content.encode()).hexdigest()

def test_cli_help():
    """Test the CLI help message."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Usage: relocase [OPTIONS] SOURCE TARGET" in result.output

@patch("src.main.get_fs_root", return_value=".")
@patch("src.main.get_md5")
def test_dry_run(mock_get_md5, mock_get_fs_root):
    """Test the dry-run functionality."""
    mock_get_md5.side_effect = lambda path: get_md5_from_content(open(path).read())
    runner = CliRunner()
    with runner.isolated_filesystem():
        os.makedirs("source/subdir")
        os.makedirs("target")

        create_file("source/file1.txt", "This is file 1.")
        create_file("source/subdir/file2.txt", "This is file 2.")

        result = runner.invoke(cli, ["source", "target", "--dry-run"])
        assert result.exit_code == 0
        assert "Would transfer: source/file1.txt -> target/file1.txt" in result.output
        assert "Would transfer: source/subdir/file2.txt -> target/subdir/file2.txt" in result.output
        assert not os.path.exists("target/file1.txt")

@patch("src.main.get_fs_root", return_value=".")
@patch("src.main.get_md5")
@patch("subprocess.run")
def test_file_transfer(mock_subprocess_run, mock_get_md5, mock_get_fs_root):
    """Test the file transfer functionality."""
    mock_get_md5.side_effect = lambda path: get_md5_from_content(open(path).read())
    runner = CliRunner()
    with runner.isolated_filesystem():
        os.makedirs("source/subdir")
        os.makedirs("target")

        create_file("source/file1.txt", "This is file 1.")
        create_file("source/subdir/file2.txt", "This is file 2.")

        result = runner.invoke(cli, ["source", "target"])
        assert result.exit_code == 0
        mock_subprocess_run.assert_any_call(["rsync", "-a", "source/file1.txt", "target/file1.txt"])
        mock_subprocess_run.assert_any_call(["rsync", "-a", "source/subdir/file2.txt", "target/subdir/file2.txt"])


@patch("src.main.get_fs_root", return_value=".")
@patch("src.main.get_md5")
@patch("shutil.move")
def test_file_move(mock_shutil_move, mock_get_md5, mock_get_fs_root):
    """Test the file move functionality."""
    mock_get_md5.side_effect = lambda path: get_md5_from_content(open(path).read())
    runner = CliRunner()
    with runner.isolated_filesystem():
        os.makedirs("source")
        os.makedirs("target/existing_dir")

        create_file("source/file1.txt", "This is file 1.")
        create_file("target/existing_dir/file1.txt", "This is file 1.")

        result = runner.invoke(cli, ["source", "target"])
        assert result.exit_code == 0
        mock_shutil_move.assert_called_once_with("target/existing_dir/file1.txt", "target/file1.txt")


@patch("src.main.get_fs_root", return_value=".")
@patch("src.main.get_md5")
def test_overwrite_protection(mock_get_md5, mock_get_fs_root):
    """Test that the program does not overwrite existing files."""
    mock_get_md5.side_effect = lambda path: get_md5_from_content(open(path).read())
    runner = CliRunner()
    with runner.isolated_filesystem():
        os.makedirs("source")
        os.makedirs("target/existing_dir")

        create_file("source/file1.txt", "This is file 1.")
        create_file("target/file1.txt", "This is a different file.")
        create_file("target/existing_dir/file1.txt", "This is file 1.")

        result = runner.invoke(cli, ["source", "target"])
        assert result.exit_code == 0
        assert "Warning: Destination target/file1.txt already exists. Skipping move." in result.output

@patch("src.main.get_fs_root", return_value=".")
@patch("src.main.get_md5")
def test_database_logic(mock_get_md5, mock_get_fs_root):
    """Test database creation, update, and pruning."""
    mock_get_md5.side_effect = lambda path: get_md5_from_content(open(path).read())
    runner = CliRunner()
    with runner.isolated_filesystem():
        db_path = "test.db"
        # Setup
        os.makedirs("source")
        os.makedirs("target")
        create_file("source/file1.txt", "content1")
        create_file("target/stale.txt", "stale_content")

        # Initial run to populate db
        runner.invoke(cli, ["source", "target", "--db-name", db_path])

        # Test Pruning
        os.remove("target/stale.txt")
        runner.invoke(cli, ["source", "target", "--db-name", db_path])

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM md5_cache WHERE path=?", ("stale.txt",))
        assert cursor.fetchone() is None

        # Test Duplicate file handling
        create_file("target/dup1.txt", "content1")
        create_file("target/dup2.txt", "content1")
        runner.invoke(cli, ["source", "target", "--db-name", db_path])

        cursor.execute("SELECT * FROM md5_cache WHERE md5=?", (get_md5_from_content("content1"),))
        rows = cursor.fetchall()
        assert len(rows) >= 2 # Should have at least two entries for the same md5
        conn.close()

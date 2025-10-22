import os
import hashlib
import sqlite3
from click.testing import CliRunner
from src.main import cli, db_connect

def create_file(path, content):
    """Create a file with the given content."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)

def get_md5(path):
    """Get the MD5 checksum of a file."""
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def test_cli_help():
    """Test the CLI help message."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Usage: cli [OPTIONS] SOURCE TARGET" in result.output

def test_dry_run():
    """Test the dry-run functionality."""
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

def test_file_transfer():
    """Test the file transfer functionality."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        os.makedirs("source/subdir")
        os.makedirs("target")

        create_file("source/file1.txt", "This is file 1.")
        create_file("source/subdir/file2.txt", "This is file 2.")

        result = runner.invoke(cli, ["source", "target"])
        assert result.exit_code == 0
        assert os.path.exists("target/file1.txt")
        assert os.path.exists("target/subdir/file2.txt")
        assert get_md5("source/file1.txt") == get_md5("target/file1.txt")

def test_file_move():
    """Test the file move functionality."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        os.makedirs("source")
        os.makedirs("target/existing_dir")

        create_file("source/file1.txt", "This is file 1.")
        create_file("target/existing_dir/file1.txt", "This is file 1.")

        result = runner.invoke(cli, ["source", "target"])
        assert result.exit_code == 0
        assert os.path.exists("target/file1.txt")
        assert not os.path.exists("target/existing_dir/file1.txt")
        assert get_md5("source/file1.txt") == get_md5("target/file1.txt")

def test_file_modification():
    """Test that modified files are transferred."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        os.makedirs("source")
        os.makedirs("target")

        create_file("source/file1.txt", "This is the original file.")
        create_file("target/file1.txt", "This is the modified file.")

        result = runner.invoke(cli, ["source", "target"])
        assert result.exit_code == 0
        assert os.path.exists("target/file1.txt")
        assert get_md5("source/file1.txt") == get_md5("target/file1.txt")

def test_overwrite_protection():
    """Test that the program does not overwrite existing files."""
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
        assert get_md5("target/file1.txt") != get_md5("source/file1.txt")

def test_database_creation_and_update():
    """Test that the database is created and updated correctly."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        os.makedirs("source")
        os.makedirs("target")
        create_file("source/file1.txt", "content1")

        # First run
        result = runner.invoke(cli, ["source", "target"])
        assert result.exit_code == 0
        db_path = "target/.smart-sync.db"
        assert os.path.exists(db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT path, md5 FROM md5_cache WHERE path=?", ("file1.txt",))
        row = cursor.fetchone()
        assert row is not None
        assert row[1] == get_md5("source/file1.txt")
        conn.close()

        # Modify the file and re-run
        create_file("source/file1.txt", "content2")
        result = runner.invoke(cli, ["source", "target"])
        assert result.exit_code == 0

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT path, md5 FROM md5_cache WHERE path=?", ("file1.txt",))
        row = cursor.fetchone()
        assert row is not None
        assert row[1] == get_md5("source/file1.txt")
        conn.close()

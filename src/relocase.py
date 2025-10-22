import os
import hashlib
import shutil
import click
import sqlite3
import time
import subprocess

def get_fs_root(path):
    """Find the filesystem root for a given path."""
    path = os.path.abspath(path)
    while not os.path.ismount(path):
        path = os.path.dirname(path)
    return path

def get_md5(path):
    """Get the MD5 checksum of a file using the md5sum command."""
    result = subprocess.run(["md5sum", path], capture_output=True, text=True)
    return result.stdout.split()[0]

def create_table(conn):
    """Create the md5_cache table if it doesn't exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS md5_cache (
            md5 TEXT,
            path TEXT,
            PRIMARY KEY (md5, path)
        )
        """
    )

def db_connect(target_path, db_name):
    """Connect to the SQLite database in the target directory's filesystem root."""
    fs_root = get_fs_root(target_path)
    db_path = os.path.join(fs_root, db_name)
    conn = sqlite3.connect(db_path)
    create_table(conn)
    return conn

def build_md5_db(target_path, conn):
    """Build a database of MD5 checksums for all files in a directory."""
    md5_db = {}
    cursor = conn.cursor()

    # Prune stale entries
    all_db_paths = {row[0] for row in cursor.execute("SELECT path FROM md5_cache")}
    existing_paths = set()

    files_to_process = []
    for root, _, files in os.walk(target_path):
        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, target_path)
            existing_paths.add(rel_path)
            files_to_process.append(full_path)

    stale_paths = all_db_paths - existing_paths
    if stale_paths:
        cursor.executemany("DELETE FROM md5_cache WHERE path = ?", [(p,) for p in stale_paths])
        conn.commit()


    # Get existing cache
    cache = {}
    for row in cursor.execute("SELECT md5, path FROM md5_cache"):
        if row[0] not in cache:
            cache[row[0]] = []
        cache[row[0]].append(os.path.join(target_path, row[1]))


    for file_path in files_to_process:
        # Ignore the database file itself
        if hasattr(conn, 'database') and os.path.basename(file_path) == os.path.basename(conn.database):
            continue

        try:
            rel_path = os.path.relpath(file_path, target_path)
            md5 = get_md5(file_path)

            if md5 not in cache or file_path not in cache[md5]:
                 cursor.execute(
                    "REPLACE INTO md5_cache (md5, path) VALUES (?, ?)",
                    (md5, rel_path),
                )

            if md5 not in md5_db:
                md5_db[md5] = []
            md5_db[md5].append(file_path)

        except FileNotFoundError:
            continue

    conn.commit()
    return md5_db


@click.command(name="relocase")
@click.argument("source")
@click.argument("target")
@click.option("--dry-run", is_flag=True, help="Perform a dry run without actually modifying any files.")
@click.option("--db-name", default=".relocase.db", help="The name of the database file.")
def cli(source, target, dry_run, db_name):
    """A file syncing program that minimizes redundant file transfers by moving existing files."""
    conn = None
    if not dry_run:
        conn = db_connect(target, db_name)
    else:
        conn = sqlite3.connect(":memory:")
        create_table(conn)


    target_md5_db = build_md5_db(target, conn)
    cursor = conn.cursor()

    for src_root, _, files in os.walk(source):
        for file in files:
            src_path = os.path.join(src_root, file)
            rel_path = os.path.relpath(src_path, source)
            target_path = os.path.join(target, rel_path)

            src_md5 = get_md5(src_path)

            if src_md5 in target_md5_db and target_md5_db[src_md5]:
                existing_path = target_md5_db[src_md5][0]
                if existing_path != target_path:
                    if os.path.exists(target_path):
                        click.echo(f"Warning: Destination {target_path} already exists. Skipping move.")
                        continue

                    if dry_run:
                        click.echo(f"Would move: {existing_path} -> {target_path}")
                    else:
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        shutil.move(existing_path, target_path)
                        target_md5_db[src_md5].pop(0)

                        old_rel_path = os.path.relpath(existing_path, target)
                        new_rel_path = os.path.relpath(target_path, target)
                        cursor.execute(
                            "DELETE FROM md5_cache WHERE path = ?", (old_rel_path,)
                        )
                        cursor.execute(
                            "REPLACE INTO md5_cache (md5, path) VALUES (?, ?)",
                            (src_md5, new_rel_path)
                        )
                        conn.commit()

            else:
                if os.path.exists(target_path):
                    target_md5 = get_md5(target_path)
                    if src_md5 == target_md5:
                        continue

                if dry_run:
                    click.echo(f"Would transfer: {src_path} -> {target_path}")
                else:
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    subprocess.run(["rsync", "-a", src_path, target_path])
                    cursor.execute(
                        "REPLACE INTO md5_cache (md5, path) VALUES (?, ?)",
                        (src_md5, rel_path),
                    )
                    conn.commit()


    if conn:
        conn.close()

if __name__ == "__main__":
    cli()

import os
import hashlib
import shutil
import click
import sqlite3
import time

def get_md5(path):
    """Get the MD5 checksum of a file, reading it in chunks."""
    md5 = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            md5.update(chunk)
    return md5.hexdigest()

def create_table(conn):
    """Create the md5_cache table if it doesn't exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS md5_cache (
            path TEXT PRIMARY KEY,
            mtime REAL,
            md5 TEXT
        )
        """
    )

def db_connect(target_path):
    """Connect to the SQLite database in the target directory."""
    db_path = os.path.join(target_path, ".smart-sync.db")
    conn = sqlite3.connect(db_path)
    create_table(conn)
    return conn

def build_md5_db(target_path, conn):
    """Build a database of MD5 checksums for all files in a directory."""
    md5_db = {}
    cursor = conn.cursor()

    # Get existing cache
    cache = {}
    try:
        for row in cursor.execute("SELECT path, mtime, md5 FROM md5_cache"):
            cache[row[0]] = (row[1], row[2])
    except sqlite3.OperationalError:
        # Table might not exist in memory db for dry run, which is fine
        pass

    files_to_process = []
    for root, _, files in os.walk(target_path):
        for file in files:
            files_to_process.append(os.path.join(root, file))

    for file_path in files_to_process:
        # Ignore the database file
        if os.path.basename(file_path) == ".smart-sync.db":
            continue

        try:
            mtime = os.path.getmtime(file_path)
            rel_path = os.path.relpath(file_path, target_path)

            if rel_path in cache and cache[rel_path][0] == mtime:
                md5 = cache[rel_path][1]
            else:
                md5 = get_md5(file_path)
                cursor.execute(
                    "REPLACE INTO md5_cache (path, mtime, md5) VALUES (?, ?, ?)",
                    (rel_path, mtime, md5),
                )
            if md5 not in md5_db:
                md5_db[md5] = []
            md5_db[md5].append(file_path)
        except FileNotFoundError:
            # File might have been moved or deleted during processing
            continue

    conn.commit()
    return md5_db


@click.command()
@click.argument("source")
@click.argument("target")
@click.option("--dry-run", is_flag=True, help="Perform a dry run without actually modifying any files.")
def cli(source, target, dry_run):
    """A file syncing program that minimizes redundant file transfers."""
    conn = None
    if not dry_run:
        conn = db_connect(target)
    else:
        conn = sqlite3.connect(":memory:")
        create_table(conn)


    target_md5_db = build_md5_db(target, conn)

    for src_root, _, files in os.walk(source):
        for file in files:
            src_path = os.path.join(src_root, file)
            rel_path = os.path.relpath(src_path, source)
            target_path = os.path.join(target, rel_path)

            src_md5 = get_md5(src_path)

            if src_md5 in target_md5_db and target_md5_db[src_md5]:
                existing_path = target_md5_db[src_md5][0]
                if existing_path != target_path:
                    # Handle potential overwrite
                    if os.path.exists(target_path):
                        click.echo(f"Warning: Destination {target_path} already exists. Skipping move.")
                        continue

                    if dry_run:
                        click.echo(f"Would move: {existing_path} -> {target_path}")
                    else:
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        shutil.move(existing_path, target_path)
                        target_md5_db[src_md5].pop(0)
                        # Update database for the move
                        cursor = conn.cursor()
                        old_rel_path = os.path.relpath(existing_path, target)
                        new_rel_path = os.path.relpath(target_path, target)
                        mtime = os.path.getmtime(target_path)
                        cursor.execute(
                            "UPDATE md5_cache SET path = ?, mtime = ? WHERE path = ?",
                            (new_rel_path, mtime, old_rel_path)
                        )
                        conn.commit()

            else:
                # Handle potential overwrite
                if os.path.exists(target_path):
                    target_md5 = get_md5(target_path)
                    if src_md5 == target_md5:
                        # File is identical, do nothing
                        continue

                if dry_run:
                    click.echo(f"Would transfer: {src_path} -> {target_path}")
                else:
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    shutil.copy2(src_path, target_path)
                    # Update database for the new file
                    mtime = os.path.getmtime(target_path)
                    cursor = conn.cursor()
                    cursor.execute(
                        "REPLACE INTO md5_cache (path, mtime, md5) VALUES (?, ?, ?)",
                        (rel_path, mtime, src_md5),
                    )
                    conn.commit()


    if conn:
        conn.close()

if __name__ == "__main__":
    cli()

#!/usr/bin/env python3
"""
exfat_integrity_checker.py

A simple integrity checker for files on an exFAT (or any) filesystem.

Usage:
  # Initialize database with baseline hashes
  python exfat_integrity_checker.py init /Volumes/YourDrive --db-file integrity.db

  # Check for changes since last run and update database
  python exfat_integrity_checker.py check /Volumes/YourDrive --db-file integrity.db
"""
import os
import sys
import hashlib
import sqlite3
import argparse
import time
from tqdm import tqdm


def compute_hash(path, algo="sha256", chunk_size=8192):
    """Compute hash of a file using the given algorithm."""
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def should_ignore_file(filepath):
    """Check if a file should be ignored based on its name or path."""
    # Get just the filename without the path
    filename = os.path.basename(filepath)

    # Common macOS system files to ignore
    ignored_patterns = [
        ".DS_Store",
        "._",  # Resource fork files
        ".Spotlight-V100",
        ".Trashes",
        ".fseventsd",
        ".TemporaryItems",
        "Icon\r",
        ".AppleDouble",
        ".LSOverride",
        ".DocumentRevisions-V100",
        ".VolumeIcon.icns",
        ".com.apple.timemachine.",
    ]

    # Common macOS hidden directories to ignore - if ANY part of the path contains these, ignore the file
    ignored_dirs = [
        ".Spotlight-V100",
        ".Trashes",
        ".fseventsd",
        ".TemporaryItems",
        ".AppleDouble",
        ".DocumentRevisions-V100",
        "__MACOSX",
    ]

    # Check filename against patterns
    if any(filename.startswith(pattern) for pattern in ignored_patterns):
        return True

    # Check if file is in ANY directory that should be ignored
    # This ensures we ignore files under paths like /Volumes/Data/.Spotlight-V100/...
    filepath_normalized = os.path.normpath(filepath)
    path_parts = filepath_normalized.split(os.sep)

    # Check if any part of the path is a system directory to ignore
    for ignored_dir in ignored_dirs:
        if ignored_dir in path_parts:
            return True

    return False


def connect_db(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS files (
            path TEXT PRIMARY KEY,
            hash TEXT,
            mtime REAL,
            size INTEGER
        )
    """
    )
    conn.commit()
    return conn


def init_db(root, db_path):
    conn = connect_db(db_path)
    c = conn.cursor()
    print(f"Initializing database at '{db_path}' with files under '{root}'...")

    # First, count total files for progress bar
    total_files = 0
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            full = os.path.join(dirpath, fname)
            if not should_ignore_file(full):
                total_files += 1

    # Now process files with progress bar
    processed = 0
    with tqdm(total=total_files, desc="Hashing files") as pbar:
        for dirpath, _, filenames in os.walk(root):
            for fname in filenames:
                full = os.path.join(dirpath, fname)
                if should_ignore_file(full):
                    continue
                try:
                    stat = os.stat(full)
                    file_hash = compute_hash(full)
                    c.execute(
                        "REPLACE INTO files VALUES (?, ?, ?, ?)",
                        (full, file_hash, stat.st_mtime, stat.st_size),
                    )
                    pbar.update(1)
                    processed += 1
                    if processed % 10 == 0:  # Commit every 10 files
                        conn.commit()
                except Exception as e:
                    print(f"\nError hashing {full}: {e}")

    conn.commit()
    conn.close()
    print("Initialization complete.")


def check_db(root, db_path):
    conn = connect_db(db_path)
    c = conn.cursor()

    # Load existing entries
    c.execute("SELECT path, hash FROM files")
    existing = {row[0]: row[1] for row in c.fetchall()}

    found_paths = set()
    modified = []
    added = []

    print(f"Checking files under '{root}' against database '{db_path}'...")

    # First, count total files for progress bar
    total_files = 0
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            full = os.path.join(dirpath, fname)
            if not should_ignore_file(full):
                total_files += 1

    # Now process files with progress bar
    with tqdm(total=total_files, desc="Verifying files") as pbar:
        for dirpath, _, filenames in os.walk(root):
            for fname in filenames:
                full = os.path.join(dirpath, fname)
                if should_ignore_file(full):
                    continue
                found_paths.add(full)
                try:
                    new_hash = compute_hash(full)
                    if full not in existing:
                        added.append(full)
                        c.execute(
                            "REPLACE INTO files VALUES (?, ?, ?, ?)",
                            (
                                full,
                                new_hash,
                                os.stat(full).st_mtime,
                                os.stat(full).st_size,
                            ),
                        )
                    else:
                        if new_hash != existing[full]:
                            modified.append(full)
                            c.execute(
                                "REPLACE INTO files VALUES (?, ?, ?, ?)",
                                (
                                    full,
                                    new_hash,
                                    os.stat(full).st_mtime,
                                    os.stat(full).st_size,
                                ),
                            )
                    pbar.update(1)
                except Exception as e:
                    print(f"\nError hashing {full}: {e}")

    # Detect removed files
    removed = [path for path in existing if path not in found_paths]

    if removed:
        with tqdm(total=len(removed), desc="Removing obsolete entries") as pbar:
            for path in removed:
                c.execute("DELETE FROM files WHERE path = ?", (path,))
                pbar.update(1)

    conn.commit()
    conn.close()

    # Report
    if added:
        print("New files added:")
        for f in added:
            print(f"  + {f}")
    if modified:
        print("Modified/Corrupted files:")
        for f in modified:
            print(f"  * {f}")
    if removed:
        print("Removed files:")
        for f in removed:
            print(f"  - {f}")

    if not (added or modified or removed):
        print("No changes detected.")


def parse_args():
    p = argparse.ArgumentParser(description="Integrity checker for exFAT disks.")
    sub = p.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create or replace baseline DB")
    init.add_argument("root", help="Path to mounted drive")
    init.add_argument("--db-file", default="integrity.db", help="SQLite database file")

    chk = sub.add_parser("check", help="Check changes and update DB")
    chk.add_argument("root", help="Path to mounted drive")
    chk.add_argument("--db-file", default="integrity.db", help="SQLite database file")

    return p.parse_args()


def main():
    args = parse_args()
    if args.command == "init":
        init_db(args.root, args.db_file)
    elif args.command == "check":
        check_db(args.root, args.db_file)
    else:
        print("Unknown command")
        sys.exit(1)


if __name__ == "__main__":
    main()

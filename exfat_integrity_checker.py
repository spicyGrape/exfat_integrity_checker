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
import concurrent.futures  # P43d3


def compute_hash(path, algo="sha256", chunk_size=8192):
    """Compute hash of a file using the given algorithm."""
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


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


def process_file(full, c):  # P0be0
    try:
        stat = os.stat(full)
        file_hash = compute_hash(full)
        c.execute(
            "REPLACE INTO files VALUES (?, ?, ?, ?)",
            (full, file_hash, stat.st_mtime, stat.st_size),
        )
        print(f"Hashed: {full}")
    except Exception as e:
        print(f"Error hashing {full}: {e}")


def init_db(root, db_path):
    conn = connect_db(db_path)
    c = conn.cursor()
    print(f"Initializing database at '{db_path}' with files under '{root}'...")
    with concurrent.futures.ThreadPoolExecutor() as executor:  # P4183
        futures = []
        for dirpath, _, filenames in os.walk(root):
            for fname in filenames:
                full = os.path.join(dirpath, fname)
                futures.append(executor.submit(process_file, full, c))
        for future in concurrent.futures.as_completed(futures):
            future.result()
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
    with concurrent.futures.ThreadPoolExecutor() as executor:  # Pdf7b
        futures = []
        for dirpath, _, filenames in os.walk(root):
            for fname in filenames:
                full = os.path.join(dirpath, fname)
                found_paths.add(full)
                futures.append(executor.submit(process_file, full, c))
        for future in concurrent.futures.as_completed(futures):
            future.result()

    # Detect removed files
    removed = [path for path in existing if path not in found_paths]
    for path in removed:
        c.execute("DELETE FROM files WHERE path = ?", (path,))

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

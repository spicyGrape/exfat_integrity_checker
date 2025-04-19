# exfat_integrity_checker

A simple Python-based integrity checker for files on an exFAT (or any) filesystem. It builds and maintains a database of file hashes, and lets you detect new, modified (or corrupted), and removed files across successive runs.

---

## Features

- **Baseline Initialization**: Scan a mounted volume, compute SHA‑256 hashes for every file, and store metadata in a SQLite database.
- **Incremental Checking**: On subsequent runs, detect and report:
  - Newly added files
  - Modified or potentially corrupted files
  - Removed files
- **Configurable Database Location**: Use a default `integrity.db` or specify a custom path.
- **Cross-Platform**: Works wherever Python 3.6+ and SQLite are available (macOS, Linux, Windows).

---

## Prerequisites

- Python 3.6 or newer
- SQLite (bundled with Python’s standard library)
- A mounted drive or partition (exFAT or otherwise)

---

## Installation

1. Clone or download this repository.
2. Make the script executable (optional):
   ```bash
   chmod +x exfat_integrity_checker.py
   ```
3. (Optional) Install into a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

---

## Usage

### 1. Initialize Baseline

Scan all files under a root directory (e.g. `/Volumes/YourDrive`) and create the SQLite database.

```bash
# Using default database file (integrity.db)
./exfat_integrity_checker.py init /Volumes/YourDrive

# Specifying a custom database path
./exfat_integrity_checker.py init /Volumes/YourDrive --db-file ~/integrity_checks/exfat.db
```

You’ll see output for each hashed file and a final “Initialization complete.” message.

### 2. Check for Changes

Re-run the script in `check` mode to detect added, modified, and removed files:

```bash
# Default DB location
./exfat_integrity_checker.py check /Volumes/YourDrive

# Custom DB location
./exfat_integrity_checker.py check /Volumes/YourDrive --db-file ~/integrity_checks/exfat.db
```

Example output:
```
New files added:
  + /Volumes/YourDrive/photos/newpic.jpg
Modified/Corrupted files:
  * /Volumes/YourDrive/documents/report.pdf
Removed files:
  - /Volumes/YourDrive/old_archive.zip
No changes detected.
```

---

## Automating Periodic Checks

### Using `cron` (Linux/macOS)

1. Open your crontab:
   ```bash
   crontab -e
   ```
2. Add a line to run daily at 2 AM:
   ```cron
   0 2 * * * /usr/bin/python3 /path/to/exfat_integrity_checker.py check /Volumes/YourDrive --db-file /path/to/integrity.db >> ~/exfat_check.log 2>&1
   ```

### Using `launchd` (macOS)

Create `~/Library/LaunchAgents/com.user.exfatintegrity.plist` with contents:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.user.exfatintegrity</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/local/bin/python3</string>
    <string>/path/to/exfat_integrity_checker.py</string>
    <string>check</string>
    <string>/Volumes/YourDrive</string>
    <string>--db-file</string>
    <string>/path/to/integrity.db</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>2</integer>
    <key>Minute</key><integer>0</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>/Users/you/exfat_check.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/you/exfat_check.err</string>
</dict>
</plist>
```

Then load with:
```bash
launchctl load ~/Library/LaunchAgents/com.user.exfatintegrity.plist
```

---

## Configuration & Customization

- **Hash Algorithm**: Edit the `compute_hash()` function to use algorithms like `md5` or `sha1`.
- **Database Path**: Use the `--db-file` argument for a custom SQLite file location.
- **Email Alerts**: Wrap the `check` invocation in a shell script that sends notifications if any changes are detected.
- **Logging**: Integrate Python’s `logging` module for more granular control.

---

## Troubleshooting

- **Permission Errors**: Ensure you have read access to all files on the mounted volume.
- **Slow Performance**: Initial hashing can be I/O bound. Consider excluding large directories or increasing `chunk_size`.
- **Database Corruption**: If the SQLite file ever becomes corrupted, delete or rename it and rerun the `init` command.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

> _Maintained by [Your Name]._  Feel free to contribute or request features via issues or pull requests.

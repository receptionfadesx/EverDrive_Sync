"""Shared constants for the EverDrive sync tool."""
import os
import re

CONFIG_FILE = os.path.expanduser("~/.everdrive_sync_config.json")

SAVE_EXTS = {".sav", ".srm", ".rtc", ".fla", ".eep", ".sra", ".snap"}

BACKUP_SNAPSHOT_RE = re.compile(r'^\d{4}-\d{2}-\d{2}_\d{6}$')

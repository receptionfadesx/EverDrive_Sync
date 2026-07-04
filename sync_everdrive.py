"""Sync ROMs and save files to EverDrive SD cards (GB/GBC/GBA/N64).

This module is a thin entry-point shim. All logic lives in the ``everdrive``
package; names are re-exported here so existing ``from sync_everdrive import``
statements continue to work.
"""
import sys

from everdrive import (  # noqa: F401  # pylint: disable=unused-import
    CONFIG_FILE, SAVE_EXTS, BACKUP_SNAPSHOT_RE,
    SyncCancelled, check_cancel, mtimes_match,
    catalog_pop_match, catalog_discard_path, files_content_match,
    list_backup_snapshots, prune_backups,
    get_clean_rom_name, get_fuzzy_title,
    get_best_region_games, get_series_groups, KNOWN_SERIES, sanitize_fat32,
    VirtualNode, add_to_virtual_tree,
    load_dat_index, file_crc32, verify_files_against_dat,
    SyncApp, HeadlessApp, run_cli, build_arg_parser,
)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        sys.exit(run_cli())
    app = SyncApp()
    app.mainloop()

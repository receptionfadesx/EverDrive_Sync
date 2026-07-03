"""Headless (CLI) adapter — lets the sync engine run without a tkinter window."""
# pylint: disable=missing-function-docstring,too-many-positional-arguments
import argparse
import threading

from .sync_app import SyncApp


class _StaticVar:
    """Minimal stand-in for a tkinter StringVar/BooleanVar."""

    def __init__(self, value=None):
        self._value = value

    def get(self):
        return self._value

    def set(self, v):
        self._value = v


class _StaticEntry:
    """Minimal stand-in for a tkinter Entry widget."""

    def __init__(self, value=""):
        self._value = value

    def get(self):
        return self._value

    def insert(self, _index, value):
        self._value = value


class _NullProgress:
    """No-op progress bar stand-in."""

    def set(self, _value):
        pass

    def get(self):
        return 0.0

    def configure(self, **_kwargs):
        pass


class HeadlessApp(SyncApp):
    """CLI-friendly SyncApp that skips tkinter initialisation."""
    # pylint: disable=super-init-not-called

    def __init__(self, args: argparse.Namespace):
        self.cancel_event = threading.Event()
        self.session_log = []
        self.prog_max = 1
        self.dry_run = False
        self.had_error = False
        self._auto_yes = getattr(args, "yes", False)

        # Path entries
        self.txt_source = _StaticEntry(args.source or "")
        self.txt_hacks = _StaticEntry(args.hacks or "")
        self.txt_gbcsys = _StaticEntry(getattr(args, "gbcsys", "") or "")
        self.txt_dest = _StaticEntry(args.dest or "")

        # Reorganise / structure
        self.chk_reorganize_var = _StaticVar(not getattr(args, "no_reorg", False))
        self.chk_type_var = _StaticVar(not getattr(args, "no_type", False))
        self.chk_series_var = _StaticVar(not getattr(args, "no_series", False))
        self.chk_az_var = _StaticVar(not getattr(args, "no_az", False))

        # 1G1R filter
        self.chk_1g1r_var = _StaticVar(getattr(args, "one_game_one_rom", False))
        self.chk_usa_var = _StaticVar(not getattr(args, "no_usa", False))
        self.chk_world_var = _StaticVar(not getattr(args, "no_world", False))
        self.chk_eur_var = _StaticVar(not getattr(args, "no_europe", False))
        self.chk_jpn_var = _StaticVar(not getattr(args, "no_japan", False))

        # Misc options
        self.chk_zip_var = _StaticVar(getattr(args, "extract_zips", False))
        self.chk_tags_var = _StaticVar(not getattr(args, "no_tags", False))
        self.chk_backups_var = _StaticVar(not getattr(args, "no_backup", False))
        self.chk_restore_var = _StaticVar(getattr(args, "restore", False))
        self.chk_folders_last_var = _StaticVar(getattr(args, "folders_last", False))
        self.chk_recent_var = _StaticVar(getattr(args, "sort_recent", False))
        self.chk_fav_var = _StaticVar(getattr(args, "favorites", False))
        self.chk_eject_var = _StaticVar(getattr(args, "eject", False))
        self.chk_dryrun_var = _StaticVar(getattr(args, "dry_run", False))

        # No-op UI stand-ins
        self.progress_bar = _NullProgress()

        # Config (unused headlessly but avoids AttributeError on save_config)
        self.config_data = {
            "Source": args.source or "",
            "Hacks": args.hacks or "",
            "GbcSysPayload": getattr(args, "gbcsys", "") or "",
            "Dest": args.dest or "",
        }

    # No-op overrides for every tkinter/UI call in the parent class ----------

    def after(self, _ms, func=None, *_args):
        if func is not None:
            func(*_args)

    def update_idletasks(self):
        pass

    def log_msg(self, msg):
        print(msg)
        self.session_log.append(msg)

    def set_progress(self, value, maximum=100):
        pass

    def step_progress(self):
        pass

    def toggle_ui(self, _enabled):
        pass

    def show_error(self, _title, msg):
        print(f"ERROR: {msg}")
        self.had_error = True

    def show_info(self, _title, msg):
        print(f"INFO: {msg}")

    def ask_okcancel(self, _title, msg):
        if self._auto_yes:
            print(f"PROMPT (auto-yes): {msg}")
            return True
        answer = input(f"{msg} [y/N]: ").strip().lower()
        return answer in ("y", "yes")

    def cancel_sync(self):
        self.cancel_event.set()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="everdrive-sync",
        description="Sync ROM library to an EverDrive SD card.",
    )
    parser.add_argument("--source", help="Source ROM library folder")
    parser.add_argument("--hacks", help="ROM Hacks folder")
    parser.add_argument("--gbcsys", help="GBCSYS/GBOS payload folder")
    parser.add_argument("--dest", required=True, help="SD card destination path")
    parser.add_argument("--no-reorg", action="store_true", help="Disable auto-reorganise")
    parser.add_argument("--no-type", action="store_true",
                        help="Don't separate systems into GB/GBC/GBA/N64 folders")
    parser.add_argument("--no-series", action="store_true",
                        help="Disable automatic series folders")
    parser.add_argument("--1g1r", dest="one_game_one_rom", action="store_true",
                        help="Apply 1G1R region filter")
    parser.add_argument("--no-usa", action="store_true", help="1G1R: exclude USA region")
    parser.add_argument("--no-world", action="store_true", help="1G1R: exclude World region")
    parser.add_argument("--no-europe", action="store_true", help="1G1R: exclude Europe region")
    parser.add_argument("--no-japan", action="store_true", help="1G1R: exclude Japan region")
    parser.add_argument("--extract-zips", action="store_true", help="Extract zip archives")
    parser.add_argument("--no-tags", action="store_true",
                        help="Strip No-Intro tags like (USA) from ROM names")
    parser.add_argument("--no-backup", action="store_true", help="Skip save backup")
    parser.add_argument("--no-az", action="store_true", help="Disable A-Z sub-folders")
    parser.add_argument("--folders-last", action="store_true",
                        help="Sort folders after game files in each menu")
    parser.add_argument("--sort-recent", action="store_true",
                        help="Sort hack/recent folders by date added instead of name")
    parser.add_argument("--favorites", action="store_true",
                        help="Prefix games listed in favorites.txt with '!'")
    parser.add_argument("--restore", action="store_true", help="Restore saves from PC to SD")
    parser.add_argument("--eject", action="store_true", help="Eject SD card after sync")
    parser.add_argument("--dry-run", action="store_true", help="Preview only — no changes made")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-confirm prompts")
    return parser


def run_cli(argv=None) -> int:
    """Run the sync in CLI/headless mode. Returns 0 on success, 1 on error."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    headless_app = HeadlessApp(args)
    headless_app.run_sync(
        source=args.source,
        hacks=args.hacks,
        gbcsys=getattr(args, "gbcsys", None),
        dest=args.dest,
    )
    return 1 if getattr(headless_app, "had_error", False) else 0

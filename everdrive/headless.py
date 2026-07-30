"""Headless (CLI) adapter — lets the sync engine run without a tkinter window."""
# pylint: disable=missing-function-docstring,too-many-positional-arguments
import argparse
import threading

from .constants import CONFIG_FILE
from .profiles import blank_profile, get_profile, load_config_file, profile_names
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

    def delete(self, _first, _last=None):
        self._value = ""


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

    def __init__(self, args: argparse.Namespace, config: dict = None):
        self.cancel_event = threading.Event()
        self.session_log = []
        self.prog_max = 1
        self.dry_run = False
        self.had_error = False
        self._auto_yes = getattr(args, "yes", False)

        # Optionally seed paths/options from a saved GUI profile; explicit CLI
        # flags always win. --profile picks one by name, --use-saved-config
        # takes whichever profile the GUI last had active.
        cfg: dict = {}
        wanted = getattr(args, "profile", None)
        if wanted or getattr(args, "use_saved_config", False):
            if config is None:
                config = load_config_file(CONFIG_FILE)
            cfg = get_profile(config, wanted) or blank_profile()
            self.active_profile = (
                wanted or config.get("ActiveProfile") or self.active_profile)
        cfg_opts = cfg.get("Options") if isinstance(cfg.get("Options"), dict) else {}

        def opt(key, default):
            return bool(cfg_opts.get(key, default))

        source = args.source or cfg.get("Source") or ""
        hacks = args.hacks or cfg.get("Hacks") or ""
        gbcsys = (getattr(args, "gbcsys", "") or cfg.get("GbcSysPayload") or "")
        dest = args.dest or cfg.get("Dest") or ""
        dat = getattr(args, "dat", "") or cfg.get("DatFile") or ""

        # Path entries
        self.txt_source = _StaticEntry(source)
        self.txt_hacks = _StaticEntry(hacks)
        self.txt_gbcsys = _StaticEntry(gbcsys)
        self.txt_dest = _StaticEntry(dest)
        self.txt_dat = _StaticEntry(dat)

        # Reorganise / structure
        self.chk_reorganize_var = _StaticVar(
            opt("Reorganize", True) and not getattr(args, "no_reorg", False))
        self.chk_type_var = _StaticVar(
            opt("TypeFolders", True) and not getattr(args, "no_type", False))
        self.chk_series_var = _StaticVar(
            opt("SeriesFolders", True) and not getattr(args, "no_series", False))
        self.chk_az_var = _StaticVar(
            opt("AZFolders", True) and not getattr(args, "no_az", False))

        # 1G1R filter
        self.chk_1g1r_var = _StaticVar(
            getattr(args, "one_game_one_rom", False) or opt("OneGameOneRom", False))
        self.chk_usa_var = _StaticVar(
            opt("RegionUSA", True) and not getattr(args, "no_usa", False))
        self.chk_world_var = _StaticVar(
            opt("RegionWorld", True) and not getattr(args, "no_world", False))
        self.chk_eur_var = _StaticVar(
            opt("RegionEurope", True) and not getattr(args, "no_europe", False))
        self.chk_jpn_var = _StaticVar(
            opt("RegionJapan", True) and not getattr(args, "no_japan", False))

        # Misc options
        self.chk_zip_var = _StaticVar(
            getattr(args, "extract_zips", False) or opt("ExtractZips", False))
        self.chk_tags_var = _StaticVar(
            opt("KeepTags", True) and not getattr(args, "no_tags", False))
        self.chk_backups_var = _StaticVar(
            opt("Backups", True) and not getattr(args, "no_backup", False))
        self.chk_restore_var = _StaticVar(
            getattr(args, "restore", False) or opt("Restore", False))
        self.chk_folders_last_var = _StaticVar(
            getattr(args, "folders_last", False) or opt("FoldersLast", False))
        self.chk_recent_var = _StaticVar(
            getattr(args, "sort_recent", False) or opt("SortRecent", False))
        self.chk_fav_var = _StaticVar(
            getattr(args, "favorites", False) or opt("Favorites", False))
        self.chk_eject_var = _StaticVar(
            getattr(args, "eject", False) or opt("Eject", False))
        self.chk_verify_var = _StaticVar(
            getattr(args, "verify", False) or opt("VerifyWrites", False))
        self.chk_orphans_var = _StaticVar(
            getattr(args, "archive_orphans", False) or opt("ArchiveOrphans", False))
        # Deliberately NOT read from saved config: a leftover GUI dry-run
        # toggle silently turning every scripted sync into a no-op is worse
        # than requiring the explicit flag.
        self.chk_dryrun_var = _StaticVar(getattr(args, "dry_run", False))

        # No-op UI stand-ins
        self.progress_bar = _NullProgress()

        # Config (unused headlessly but avoids AttributeError on save_config)
        self.config_data = {
            "Source": source, "Hacks": hacks, "GbcSysPayload": gbcsys,
            "Dest": dest, "DatFile": dat, "Options": dict(cfg_opts),
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
    parser.add_argument("--dest",
                        help="SD card destination path (required unless a profile"
                             " supplies it, see --use-saved-config / --profile)")
    parser.add_argument("--dat", help="No-Intro DAT file to verify ROM checksums against")
    parser.add_argument("--use-saved-config", action="store_true",
                        help="Load paths and options from the profile the GUI last used;"
                             " explicit flags override (--dry-run is never loaded"
                             " from config)")
    parser.add_argument("--profile", metavar="NAME",
                        help="Load a saved profile by name (e.g. --profile N64);"
                             " explicit flags still override its values")
    parser.add_argument("--list-profiles", action="store_true",
                        help="List saved profiles and exit")
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
    parser.add_argument("--verify", action="store_true",
                        help="Verify every file written to the SD card (slower, safer)")
    parser.add_argument("--archive-orphans", action="store_true",
                        help="Move orphaned SD saves into the PC backup instead of warning")
    parser.add_argument("--restore", action="store_true", help="Restore saves from PC to SD")
    parser.add_argument("--eject", action="store_true", help="Eject SD card after sync")
    parser.add_argument("--dry-run", action="store_true", help="Preview only — no changes made")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-confirm prompts")
    return parser


def _print_profiles(config: dict) -> None:
    active = config.get("ActiveProfile")
    print("Saved profiles:")
    for name in profile_names(config):
        profile = config["Profiles"][name]
        marker = "*" if name == active else " "
        print(f" {marker} {name}")
        print(f"     source: {profile.get('Source') or '(unset)'}")
        print(f"     dest:   {profile.get('Dest') or '(unset)'}")
    print("\n(* = profile the GUI last used, i.e. what --use-saved-config picks)")


def run_cli(argv=None) -> int:
    """Run the sync in CLI/headless mode. Returns 0 on success, 1 on error."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    config = load_config_file(CONFIG_FILE)
    if args.list_profiles:
        _print_profiles(config)
        return 0
    if args.profile and args.profile not in config["Profiles"]:
        parser.error(
            f"unknown profile {args.profile!r}; saved profiles: "
            + ", ".join(profile_names(config)))
    headless_app = HeadlessApp(args, config)
    if args.profile or args.use_saved_config:
        print(f"Using profile: {headless_app.active_profile}")
    if not headless_app.txt_dest.get().strip():
        parser.error("--dest is required (or save a Dest in a GUI profile and pass"
                     " --use-saved-config / --profile NAME)")
    # No explicit args: HeadlessApp already merged CLI flags with any saved
    # config, and run_sync falls back to reading the entry stand-ins.
    headless_app.run_sync()
    return 1 if getattr(headless_app, "had_error", False) else 0

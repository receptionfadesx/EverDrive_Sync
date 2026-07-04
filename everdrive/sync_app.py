"""Main GUI window and sync engine."""
# pylint: disable=missing-function-docstring,too-many-positional-arguments
# pylint: disable=too-many-public-methods,too-many-instance-attributes
import os
import sys
import re
import json
import filecmp
import shutil
import zipfile
import platform
import threading
import tempfile
import subprocess
import itertools
import tkinter as tk
from pathlib import Path
from datetime import datetime
from tkinter import filedialog, messagebox
from typing import Dict, List, Optional, Tuple

try:
    import customtkinter as ctk  # type: ignore
except ImportError:
    print("Error: customtkinter is not installed. Please run `pip install customtkinter`")
    sys.exit(1)

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

from .constants import CONFIG_FILE, SAVE_EXTS
from .utils import (
    SyncCancelled, check_cancel, mtimes_match,
    catalog_pop_match, catalog_discard_path,
    list_backup_snapshots, prune_backups,
)
from .rom_utils import (
    get_clean_rom_name, get_fuzzy_title,
    get_best_region_games, get_series_groups, sanitize_fat32,
)
from .virtual_tree import VirtualNode, add_to_virtual_tree
from .dat_check import load_dat_index, verify_files_against_dat

# Folders on the SD card that must never be deleted or counted as reclaimable
SYSTEM_FOLDERS = {
    "edgb", "gbos", "gbcsys", "ed64", "gbasys", "edgba",
    "system volume information", ".sync_temp"
}


# Module-level (like check_cancel) so they also work when SyncApp methods are
# invoked unbound on minimal stand-in instances in tests/headless mode.
def _stat_bump(instance, key, n=1):
    stats = getattr(instance, "stats", None)
    if stats is not None:
        stats[key] = stats.get(key, 0) + n


def _copy_verified(instance, src, dst):
    """copy2 with optional read-back verification (SD cards corrupt silently)."""
    shutil.copy2(src, dst)
    if not getattr(instance, "verify_writes", False):
        return
    if filecmp.cmp(src, dst, shallow=False):
        return
    try:
        os.remove(dst)
    except OSError:
        pass
    shutil.copy2(src, dst)  # one retry before giving up
    if not filecmp.cmp(src, dst, shallow=False):
        raise OSError(
            f"Verification failed after copying '{os.path.basename(dst)}'"
            " — the SD card may be failing or counterfeit."
        )


# pylint: disable=attribute-defined-outside-init
class SyncApp(ctk.CTk):
    """Main GUI window and sync engine for EverDrive SD card synchronisation."""

    # Class-level defaults so attribute lookups never fall through to
    # tkinter's __getattr__ delegation on partially-initialized instances
    # (e.g. headless/test subclasses that skip CTk.__init__).
    dry_run = False
    verify_writes = False
    cancel_event = None
    session_log = None
    stats = None

    # (config key, BooleanVar attribute, default) for every persisted option
    OPTION_VARS = [
        ("Reorganize", "chk_reorganize_var", True),
        ("TypeFolders", "chk_type_var", True),
        ("SeriesFolders", "chk_series_var", True),
        ("AZFolders", "chk_az_var", True),
        ("OneGameOneRom", "chk_1g1r_var", False),
        ("RegionUSA", "chk_usa_var", True),
        ("RegionWorld", "chk_world_var", True),
        ("RegionEurope", "chk_eur_var", True),
        ("RegionJapan", "chk_jpn_var", True),
        ("ExtractZips", "chk_zip_var", False),
        ("KeepTags", "chk_tags_var", True),
        ("Backups", "chk_backups_var", True),
        ("Restore", "chk_restore_var", False),
        ("FoldersLast", "chk_folders_last_var", False),
        ("SortRecent", "chk_recent_var", False),
        ("Favorites", "chk_fav_var", False),
        ("Eject", "chk_eject_var", False),
        ("DryRun", "chk_dryrun_var", False),
        ("VerifyWrites", "chk_verify_var", False),
        ("ArchiveOrphans", "chk_orphans_var", False),
    ]

    def __init__(self):
        super().__init__()
        self.title("Sync Tool for EverDrive (GB/GBA/64)")
        self.geometry("600x1010")
        # Allow vertical resizing so the window still fits on 768p screens
        self.resizable(False, True)
        self.minsize(600, 600)

        self.config_data = {
            "Source": "", "Hacks": "", "GbcSysPayload": "", "Dest": "",
            "DatFile": "", "Options": {},
        }
        self.cancel_event = threading.Event()
        self.session_log: List[str] = []
        self.prog_max = 1
        self.load_config()
        self.set_app_icon()
        self.create_widgets()
        self._apply_saved_options()

    def get_asset_path(self, relative_path):
        # getattr is used to satisfy static analysis as _MEIPASS is injected at runtime by PyInstaller
        base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
        return os.path.join(base_path, relative_path)

    def set_app_icon(self):
        # Use .ico for Windows title bar, .png for others
        ext = ".ico" if platform.system() == "Windows" else ".png"
        icon_path = self.get_asset_path(os.path.join("assets", f"icon{ext}"))
        if os.path.exists(icon_path):
            try:
                if platform.system() == "Windows":
                    self.iconbitmap(icon_path)
                else:
                    img = tk.PhotoImage(file=icon_path)
                    self.iconphoto(True, img)
            except Exception:  # pylint: disable=broad-exception-caught
                pass

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for k in self.config_data:
                    if k in data:
                        self.config_data[k] = data[k]
            except (json.JSONDecodeError, OSError):
                pass

    def save_config(self):
        self.config_data["Source"] = self.txt_source.get()
        self.config_data["Hacks"] = self.txt_hacks.get()
        self.config_data["GbcSysPayload"] = self.txt_gbcsys.get()
        self.config_data["Dest"] = self.txt_dest.get()
        dat_widget = getattr(self, "txt_dat", None)
        if dat_widget is not None:
            self.config_data["DatFile"] = dat_widget.get()
        self.config_data["Options"] = {
            key: bool(getattr(self, attr).get())
            for key, attr, _default in self.OPTION_VARS
            if getattr(self, attr, None) is not None
        }
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f)
        except OSError:
            pass

    # ------------------------------------------------------------------ #
    # Widget construction                                                   #
    # ------------------------------------------------------------------ #

    def create_widgets(self):
        self._build_path_frame()
        self._build_options_frame()
        self._build_log_controls()

    def _add_path_row(self, parent, row, label, key, file_picker=False):
        """Add one Source/Dest browse row; return the CTkEntry widget."""
        ctk.CTkLabel(parent, text=label).grid(row=row, column=0, padx=5, pady=5, sticky="w")
        entry = ctk.CTkEntry(parent, width=350)
        entry.insert(0, self.config_data[key])
        entry.grid(row=row, column=1, padx=5, pady=5)
        browse = self.browse_file if file_picker else self.browse_folder
        ctk.CTkButton(
            parent, text="Browse...", width=80,
            command=lambda e=entry: browse(e)
        ).grid(row=row, column=2, padx=5, pady=5)
        return entry

    def _build_path_frame(self):
        frame = ctk.CTkFrame(self)
        frame.pack(pady=10, padx=20, fill="x")
        self.txt_source = self._add_path_row(frame, 0, "Source:", "Source")
        self.txt_hacks = self._add_path_row(frame, 1, "ROM Hacks:", "Hacks")
        self.txt_gbcsys = self._add_path_row(frame, 2, "GBCSYS:", "GbcSysPayload")
        self.txt_dest = self._add_path_row(frame, 3, "SD Card:", "Dest")
        self.txt_dat = self._add_path_row(frame, 4, "DAT File:", "DatFile", file_picker=True)

    def _build_reorg_group(self, parent):
        self.chk_reorganize_var = tk.BooleanVar(value=True)
        self.chk_reorganize = ctk.CTkCheckBox(
            parent, text="Auto-Reorganize (Alphabetical)",
            variable=self.chk_reorganize_var, command=self.toggle_reorg
        )
        self.chk_reorganize.pack(anchor="w", padx=10, pady=5)

        self.chk_type_var = tk.BooleanVar(value=True)
        self.chk_type = ctk.CTkCheckBox(
            parent, text="Separate Systems/Types (GB/GBC/GBA/N64)",
            variable=self.chk_type_var
        )
        self.chk_type.pack(anchor="w", padx=30, pady=2)

        self.chk_series_var = tk.BooleanVar(value=True)
        self.chk_series = ctk.CTkCheckBox(
            parent, text="Auto-Create Series Folders", variable=self.chk_series_var
        )
        self.chk_series.pack(anchor="w", padx=30, pady=2)

        self.chk_az_var = tk.BooleanVar(value=True)
        self.chk_az = ctk.CTkCheckBox(parent, text="A-Z Folders", variable=self.chk_az_var)
        self.chk_az.pack(anchor="w", padx=30, pady=2)

    def _build_filter_group(self, parent):
        self.chk_1g1r_var = tk.BooleanVar(value=False)
        self.chk_1g1r = ctk.CTkCheckBox(
            parent, text="1G1R Filter",
            variable=self.chk_1g1r_var, command=self.toggle_1g1r
        )
        self.chk_1g1r.pack(anchor="w", padx=10, pady=5)

        reg_frame = ctk.CTkFrame(parent, fg_color="transparent")
        reg_frame.pack(anchor="w", padx=30, pady=0)

        self.chk_usa_var = tk.BooleanVar(value=True)
        self.chk_usa = ctk.CTkCheckBox(
            reg_frame, text="USA (1)", variable=self.chk_usa_var, state="disabled"
        )
        self.chk_usa.pack(side="left", padx=5)

        self.chk_world_var = tk.BooleanVar(value=True)
        self.chk_world = ctk.CTkCheckBox(
            reg_frame, text="World (2)", variable=self.chk_world_var, state="disabled"
        )
        self.chk_world.pack(side="left", padx=5)

        self.chk_eur_var = tk.BooleanVar(value=True)
        self.chk_eur = ctk.CTkCheckBox(
            reg_frame, text="Europe (3)", variable=self.chk_eur_var, state="disabled"
        )
        self.chk_eur.pack(side="left", padx=5)

        self.chk_jpn_var = tk.BooleanVar(value=True)
        self.chk_jpn = ctk.CTkCheckBox(
            reg_frame, text="Japan (4)", variable=self.chk_jpn_var, state="disabled"
        )
        self.chk_jpn.pack(side="left", padx=5)

    def _build_misc_options(self, parent):
        options = [
            ("chk_zip", "Extract zip files", False),
            ("chk_tags", "Keep Tags", True),
            ("chk_backups", "Backup SD saves to PC", True),
            ("chk_restore", "Restore saves from PC to SD", False),
            ("chk_verify", "Verify writes (slower, safer)", False),
            ("chk_orphans", "Archive orphaned saves to PC", False),
            ("chk_folders_last", "Advanced: Folders AFTER games", False),
            ("chk_recent", "Advanced: Sort Hacks by Date", False),
            ("chk_fav", "Advanced: Push favorites to top", False),
            ("chk_eject", "Eject SD card after sync", False),
            ("chk_dryrun", "Dry Run (preview only — no changes)", False),
        ]
        for attr, label, default in options:
            var = tk.BooleanVar(value=default)
            setattr(self, f"{attr}_var", var)
            chk = ctk.CTkCheckBox(parent, text=label, variable=var)
            chk.pack(anchor="w", padx=10, pady=2)
            setattr(self, attr, chk)

    def _build_options_frame(self):
        frame = ctk.CTkFrame(self)
        frame.pack(pady=5, padx=20, fill="both", expand=True)
        self._build_reorg_group(frame)
        self._build_filter_group(frame)
        self._build_misc_options(frame)

    def _build_log_controls(self):
        self.txt_log = ctk.CTkTextbox(self, height=150, font=("Consolas", 12))
        self.txt_log.pack(pady=10, padx=20, fill="x")
        self.txt_log.insert("0.0", "Ready to sync.\n")
        self.txt_log.configure(state="disabled")

        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.pack(pady=5, padx=20, fill="x")
        self.progress_bar.set(0)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=10)
        self.btn_start = ctk.CTkButton(
            btn_frame, text="Start Sync", fg_color="green", hover_color="darkgreen",
            command=self.start_sync_thread
        )
        self.btn_start.pack(side="left", padx=5)
        self.btn_cancel = ctk.CTkButton(
            btn_frame, text="Cancel", fg_color="firebrick", hover_color="darkred",
            state="disabled", command=self.cancel_sync
        )
        self.btn_cancel.pack(side="left", padx=5)

    # ------------------------------------------------------------------ #
    # UI helpers                                                            #
    # ------------------------------------------------------------------ #

    def toggle_reorg(self):
        state = "normal" if self.chk_reorganize_var.get() else "disabled"
        self.chk_type.configure(state=state)
        self.chk_series.configure(state=state)
        self.chk_az.configure(state=state)

    def toggle_1g1r(self):
        state = "normal" if self.chk_1g1r_var.get() else "disabled"
        self.chk_usa.configure(state=state)
        self.chk_world.configure(state=state)
        self.chk_eur.configure(state=state)
        self.chk_jpn.configure(state=state)

    def _apply_saved_options(self):
        """Restore checkbox states persisted by a previous session."""
        opts = self.config_data.get("Options") or {}
        for key, attr, _default in self.OPTION_VARS:
            if key in opts:
                var = getattr(self, attr, None)
                if var is not None:
                    var.set(bool(opts[key]))
        self.toggle_reorg()
        self.toggle_1g1r()

    def browse_folder(self, entry_widget):
        folder = filedialog.askdirectory()
        if folder:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, folder)

    def browse_file(self, entry_widget):
        path = filedialog.askopenfilename(
            filetypes=[("DAT files", "*.dat *.xml"), ("All files", "*.*")]
        )
        if path:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, path)

    def log_msg(self, msg):
        print(msg)
        log = getattr(self, "session_log", None)
        if log is not None:
            log.append(msg)
        self.after(0, self._log_msg_ui, msg)

    def _log_msg_ui(self, msg):
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", msg + "\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")
        self.update_idletasks()

    def set_progress(self, value, maximum=100):
        if maximum > 0:
            self.after(0, lambda: self.progress_bar.set(value / maximum))
        self.after(0, self.update_idletasks)

    def step_progress(self):
        self.after(0, self._step_progress_ui)

    def _step_progress_ui(self):
        val = self.progress_bar.get() + (1 / max(1, self.prog_max))
        self.progress_bar.set(min(1.0, val))
        self.update_idletasks()

    def toggle_ui(self, enabled):
        state = "normal" if enabled else "disabled"
        for widget in (
            self.btn_start, self.txt_source, self.txt_dest,
            self.txt_hacks, self.txt_gbcsys, self.txt_dat,
        ):
            widget.configure(state=state)
        if enabled:
            self.toggle_reorg()
            self.toggle_1g1r()
        else:
            for w in (
                self.chk_type, self.chk_series, self.chk_az,
                self.chk_usa, self.chk_world, self.chk_eur, self.chk_jpn,
            ):
                w.configure(state="disabled")
        for w in (
            self.chk_reorganize, self.chk_1g1r, self.chk_zip, self.chk_tags,
            self.chk_backups, self.chk_restore, self.chk_verify, self.chk_orphans,
            self.chk_fav, self.chk_folders_last,
            self.chk_recent, self.chk_eject, self.chk_dryrun,
        ):
            w.configure(state=state)
        self.btn_cancel.configure(state="disabled" if enabled else "normal")

    def show_error(self, title, msg):
        self.after(0, lambda: messagebox.showerror(title, msg))

    def show_info(self, title, msg):
        self.after(0, lambda: messagebox.showinfo(title, msg))

    def ask_okcancel(self, title, msg):
        # Tk dialogs must run on the main thread; marshal and wait when called
        # from the sync worker.
        if threading.current_thread() is threading.main_thread():
            return bool(messagebox.askokcancel(title, msg))
        result = {}
        done = threading.Event()
        def _ask():
            try:
                result["value"] = messagebox.askokcancel(title, msg)
            finally:
                done.set()
        self.after(0, _ask)
        done.wait()
        return bool(result.get("value"))

    def cancel_sync(self):
        self.cancel_event.set()
        self.btn_cancel.configure(state="disabled")
        self.log_msg("Cancelling sync after the current file...")

    def start_sync_thread(self):
        # Disable the button synchronously — toggle_ui(False) is scheduled from
        # the worker, leaving a window where a double-click starts two syncs.
        self.btn_start.configure(state="disabled")
        self.save_config()
        self.txt_log.configure(state="normal")
        self.txt_log.delete("0.0", "end")
        self.txt_log.configure(state="disabled")
        self.session_log.clear()
        self.cancel_event.clear()
        # Widget reads must happen on the main thread; capture values here and
        # hand them to the worker.
        params = {
            "source": self.txt_source.get().strip(),
            "hacks": self.txt_hacks.get().strip(),
            "gbcsys": self.txt_gbcsys.get().strip(),
            "dest": self.txt_dest.get().strip(),
            "dat": self.txt_dat.get().strip(),
        }
        threading.Thread(target=lambda: self.run_sync(**params), daemon=True).start()

    # ------------------------------------------------------------------ #
    # Virtual tree copy                                                     #
    # ------------------------------------------------------------------ #

    def copy_virtual_tree(self, node, current_dest, sd_catalog, folders_last, recent_sort):
        if not node.children:
            return

        # folder_sort_desc=True means folders should sort FIRST (lower key value)
        # We use != so that when is_folder matches folder_sort_desc, the key is False (lower = earlier)
        folder_sort_desc = not folders_last

        if recent_sort and re.search(r'(?i)\[?(ROM Hacks|New Additions|Recent)\]?', node.name):
            sorted_child = sorted(
                node.children,
                key=lambda c: (c.is_folder != folder_sort_desc, -c.last_write_time)
            )
        else:
            sorted_child = sorted(
                node.children,
                key=lambda c: (c.is_folder != folder_sort_desc, c.name.lower())
            )

        seen_targets = set()
        for child in sorted_child:
            check_cancel(self)
            target_name = sanitize_fat32(child.name)

            # Path Length Guard: Windows MAX_PATH is 260.
            # We target 240 as a safe limit for the full path.
            projected_path = os.path.join(current_dest, target_name)
            if len(projected_path) > 240:
                allowed_chars = 240 - len(current_dest) - 1
                if not child.is_folder and "." in target_name:
                    base, ext = os.path.splitext(target_name)
                    if allowed_chars > len(ext):
                        target_name = base[:allowed_chars - len(ext)] + ext
                elif allowed_chars > 0:
                    target_name = target_name[:allowed_chars]

            # FAT32 is case-insensitive, and truncation above can collide two
            # siblings — uniquify files so one doesn't overwrite the other.
            if not child.is_folder and target_name.lower() in seen_targets:
                base, ext = os.path.splitext(target_name)
                n = 1
                while f"{base}~{n}{ext}".lower() in seen_targets:
                    n += 1
                target_name = f"{base}~{n}{ext}"
            seen_targets.add(target_name.lower())

            target_path = os.path.join(current_dest, target_name)

            if child.is_folder:
                self._copy_folder_node(child, current_dest, target_path, sd_catalog, folders_last, recent_sort)
            else:
                self._copy_file_node(child, current_dest, target_path, sd_catalog)

    def _assert_no_traversal(self, current_dest, target_path):
        dest_real = os.path.realpath(current_dest)
        target_real = os.path.realpath(target_path)
        try:
            is_safe = os.path.commonpath([dest_real, target_real]) == dest_real
        except ValueError:
            is_safe = False
        if not is_safe:
            raise ValueError(f"Path traversal detected: {target_path}")

    def _copy_folder_node(self, child, current_dest, target_path, sd_catalog, folders_last, recent_sort):
        self._assert_no_traversal(current_dest, target_path)
        if not os.path.exists(target_path):
            if getattr(self, "dry_run", False):
                self.log_msg(f"[DRY RUN] Would create folder: {child.name}")
            else:
                os.makedirs(target_path, exist_ok=True)
                self.log_msg(f"Created Folder: {child.name}")
        self.copy_virtual_tree(child, target_path, sd_catalog, folders_last, recent_sort)

    def _copy_file_node(self, child, current_dest, target_path, sd_catalog):
        if not child.source_path:
            self.step_progress()
            return

        self._assert_no_traversal(current_dest, target_path)

        source_stat = os.stat(child.source_path)
        dry_run = getattr(self, "dry_run", False)

        if os.path.exists(target_path):
            dst_stat = os.stat(target_path)
            if (dst_stat.st_size == source_stat.st_size
                    and mtimes_match(dst_stat.st_mtime, source_stat.st_mtime)):
                catalog_discard_path(sd_catalog, source_stat.st_size, target_path)
                self.step_progress()
                return
            if dry_run:
                self.log_msg(f" -> [DRY RUN] Would replace: {child.name}")
                _stat_bump(self, "copied")
                _stat_bump(self, "bytes", source_stat.st_size)
                self.step_progress()
                return
            os.remove(target_path)

        # Check if exists elsewhere on SD for a quick move (size+mtime plus a
        # content sample, so renamed files are found but two different ROMs
        # that share size+mtime are never swapped)
        existing_path = catalog_pop_match(
            sd_catalog, source_stat.st_size, source_stat.st_mtime, child.source_path
        )
        if existing_path:
            if dry_run:
                self.log_msg(f" -> [DRY RUN] Would move (local): {child.name}")
            else:
                self.log_msg(f" -> Moving (Local): {child.name}")
                shutil.move(existing_path, target_path)
            _stat_bump(self, "moved")
            self.step_progress()
            return

        if dry_run:
            self.log_msg(f" -> [DRY RUN] Would copy: {child.name}")
        else:
            self.log_msg(f" -> Copying: {child.name}")
            _copy_verified(self, child.source_path, target_path)
        _stat_bump(self, "copied")
        _stat_bump(self, "bytes", source_stat.st_size)
        self.step_progress()

    # ------------------------------------------------------------------ #
    # Save backup / restore                                                 #
    # ------------------------------------------------------------------ #

    def backup_saves(self, source: str, hacks: str, dest: str, os_folder: str) -> None:
        self.log_msg("Backing up save files to PC...")
        # Choose best backup location: prefer source, fallback to hacks, skip if neither valid
        if source and os.path.isdir(source):
            backup_root = os.path.join(source, "Saves_Backup")
        elif hacks and os.path.isdir(hacks):
            backup_root = os.path.join(hacks, "Saves_Backup")
        else:
            self.log_msg("Warning: Cannot back up saves — no valid source folder found.")
            return
        dry_run = getattr(self, "dry_run", False)
        # Timestamped snapshot so one bad sync can't clobber the only backup
        backup_dir = os.path.join(backup_root, datetime.now().strftime("%Y-%m-%d_%H%M%S"))

        saves_found: List[str] = []
        for root, _, filenames in os.walk(dest):
            check_cancel(self)
            if any(x in root.split(os.sep) for x in ["System Volume Information", "Saves_Backup"]):
                continue
            for f in filenames:
                if os.path.splitext(f.lower())[1] in SAVE_EXTS:
                    src_file = os.path.join(root, f)
                    rel_path = f
                    root_parts_lower = [p.lower() for p in Path(root).parts]
                    if os_folder.lower() in root_parts_lower:
                        idx = root_parts_lower.index(os_folder.lower())
                        actual_os_path = os.path.join(*Path(root).parts[:idx+1])
                        rel_path = os.path.relpath(src_file, actual_os_path)
                    if not dry_run:
                        save_dest = os.path.join(backup_dir, rel_path)
                        os.makedirs(os.path.dirname(save_dest), exist_ok=True)
                        shutil.copy2(src_file, save_dest)
                    saves_found.append(src_file)
        if dry_run:
            self.log_msg(f"[DRY RUN] Would back up {len(saves_found)} files to {backup_dir}.")
        else:
            self.log_msg(f"Backed up {len(saves_found)} files to {os.path.basename(backup_dir)}.")
            prune_backups(backup_root, keep=5, log=self.log_msg)

    def restore_saves(self, source: str, dest: str, os_folder: str) -> None:
        backup_root = os.path.join(source, "Saves_Backup")
        if not os.path.isdir(backup_root):
            return
        # Restore from the newest timestamped snapshot; fall back to the
        # legacy flat layout if no snapshots exist.
        snapshots = list_backup_snapshots(backup_root)
        backup_dir = os.path.join(backup_root, snapshots[-1]) if snapshots else backup_root
        dry_run = getattr(self, "dry_run", False)
        self.log_msg(f"Restoring saves from PC ({os.path.basename(backup_dir)}) to SD...")
        save_base = "SAVES" if os_folder.upper() == "GBOS" else "SAVE"
        rtc_base = "SAVES" if os_folder.upper() == "GBOS" else "RTC"
        restored_files: List[str] = []
        for root, _, filenames in os.walk(backup_dir):
            check_cancel(self)
            for f in filenames:
                if os.path.splitext(f.lower())[1] in SAVE_EXTS:
                    src_file = os.path.join(root, f)
                    rel_path = os.path.relpath(src_file, backup_dir)
                    target_path = SyncApp._restore_target_path(
                        f, rel_path, dest, os_folder, save_base, rtc_base
                    )
                    if dry_run:
                        self.log_msg(f" -> [DRY RUN] Would restore: {f}")
                    else:
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        _copy_verified(self, src_file, target_path)
                    restored_files.append(target_path)
        if dry_run:
            self.log_msg(f"[DRY RUN] Would restore {len(restored_files)} files.")
        else:
            self.log_msg(f"Restored {len(restored_files)} files.")

    @staticmethod
    def _restore_target_path(f, rel_path, dest, os_folder, save_base, rtc_base):
        path_parts = Path(rel_path).parts
        if len(path_parts) == 1:
            if os_folder.lower() == "edgba":
                stem = os.path.splitext(f)[0]
                save_sub = os.path.join("gamedata", f"{stem}.gba")
                return os.path.join(dest, os_folder, save_sub, f)
            save_sub = rtc_base if f.lower().endswith('.rtc') else save_base
            return os.path.join(dest, os_folder, save_sub, f)
        return os.path.join(dest, os_folder, rel_path)

    # ------------------------------------------------------------------ #
    # SD card catalogue & housekeeping                                      #
    # ------------------------------------------------------------------ #

    def catalog_sd(self, dest: str, rom_exts: set) -> Dict[int, List[Tuple[int, str]]]:
        """Catalog existing ROMs on the SD by size so identical files can be
        moved locally instead of re-copied, even after a rename."""
        catalog: Dict[int, List[Tuple[int, str]]] = {}
        if os.path.isdir(dest):
            self.log_msg("Cataloging SD card for quick moves...")
            for root, _, filenames in os.walk(dest):
                if any(x in root.split(os.sep) for x in ["System Volume Information"]):
                    continue
                for f in filenames:
                    if os.path.splitext(f.lower())[1] in rom_exts:
                        f_path = os.path.join(root, f)
                        try:
                            f_stat = os.stat(f_path)
                            catalog.setdefault(int(f_stat.st_size), []).append(
                                (int(f_stat.st_mtime), f_path)
                            )
                        except OSError:
                            continue
        return catalog

    def clean_sd(self, dest: str, _os_folder: str = "") -> None:
        """Remove all non-system files/folders from the SD card root (Soft Format).
        This ensures the FAT32 filesystem creates entries in alphabetical order."""
        self.log_msg("Cleaning SD card (preserving EverDrive OS folders)...")
        for item in os.listdir(dest):
            if item.lower() in SYSTEM_FOLDERS:
                continue
            full = os.path.join(dest, item)
            try:
                if getattr(self, "dry_run", False):
                    self.log_msg(f"[DRY RUN] Would remove: {item}")
                elif os.path.isdir(full):
                    shutil.rmtree(full)
                else:
                    os.remove(full)
                _stat_bump(self, "removed")
            except OSError as e:
                self.log_msg(f"Warning: Could not remove '{item}': {e}")

    # ------------------------------------------------------------------ #
    # Save rename helpers                                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _fav_prefixed(name: str, favs) -> str:
        """Return name with the favorites '! ' prefix when its title is a favorite.

        Keeps save filenames in lockstep with the prefixed ROM filename so the
        EverDrive OS still pairs them."""
        if favs and get_fuzzy_title(os.path.splitext(name)[0]) in favs:
            return "! " + name
        return name

    def rename_sd_saves(
        self, dest: str, os_folder: str, save_base: str, rtc_base: str,
        rom_name_map: dict, favs=None
    ) -> None:
        """Rename existing saves on the SD card to match current ROM naming settings."""
        if os_folder.lower() == "edgba":
            SyncApp._rename_gba_pro_saves(self, dest, os_folder, rom_name_map, favs)
        else:
            SyncApp._rename_standard_saves(
                self, dest, os_folder, save_base, rtc_base, rom_name_map, favs
            )

    def _rename_gba_pro_saves(
        self, dest: str, os_folder: str, rom_name_map: dict, favs=None
    ) -> None:
        gamedata_path = os.path.join(dest, os_folder, "gamedata")
        if not os.path.isdir(gamedata_path):
            return
        self.log_msg("Checking GBA PRO gamedata folders for renames...")
        for item in os.listdir(gamedata_path):
            item_path = os.path.join(gamedata_path, item)
            if not (os.path.isdir(item_path) and item.lower().endswith(".gba")):
                continue
            stem = os.path.splitext(item)[0]
            clean_stem = str(re.sub(
                r'(?i)^(GBC|GB|GBA|EDGB|GBCSYS|GBOS|SAVE|RTC|SAVES)_+', '', stem
            ))
            if not clean_stem:
                continue
            matched = SyncApp._fuzzy_match_rom(clean_stem, rom_name_map)
            if not matched:
                continue
            new_folder_name = SyncApp._fav_prefixed(matched + ".gba", favs)
            for f in os.listdir(item_path):
                f_path = os.path.join(item_path, f)
                if os.path.isfile(f_path):
                    f_stem, f_ext = os.path.splitext(f)
                    if f_stem.lower() == stem.lower():
                        new_f_name = SyncApp._fav_prefixed(matched + f_ext, favs)
                        new_f_path = os.path.join(item_path, new_f_name)
                        if not os.path.exists(new_f_path):
                            if getattr(self, "dry_run", False):
                                self.log_msg(f" -> [DRY RUN] Would rename: {f} -> {new_f_name}")
                            else:
                                os.rename(f_path, new_f_path)
                            _stat_bump(self, "renamed")
            if item != new_folder_name:
                new_folder_path = os.path.join(gamedata_path, new_folder_name)
                if not os.path.exists(new_folder_path):
                    if getattr(self, "dry_run", False):
                        self.log_msg(
                            f" -> [DRY RUN] Would rename GBA PRO folder: {item} -> {new_folder_name}"
                        )
                    else:
                        self.log_msg(f" -> Renaming GBA PRO folder: {item} -> {new_folder_name}")
                        os.rename(item_path, new_folder_path)
                    _stat_bump(self, "renamed")

    def _rename_standard_saves(
        self, dest: str, os_folder: str, save_base: str, rtc_base: str,
        rom_name_map: dict, favs=None
    ) -> None:
        sys_paths = [
            os.path.join(dest, os_folder, save_base),
            os.path.join(dest, os_folder, rtc_base),
        ]
        for sp in sys_paths:
            if not os.path.isdir(sp):
                continue
            self.log_msg(f"Checking SD saves folder '{os.path.basename(sp)}' for renames...")
            for f in os.listdir(sp):
                full = os.path.join(sp, f)
                if not os.path.isfile(full):
                    continue
                stem, ext = os.path.splitext(f)
                clean_stem: str = str(re.sub(
                    r'(?i)^(GBC|GB|GBA|EDGB|GBCSYS|GBOS|SAVE|RTC|SAVES)_+', '', stem
                ))
                if not clean_stem:
                    continue
                matched = SyncApp._fuzzy_match_rom(clean_stem, rom_name_map)
                new_name = SyncApp._fav_prefixed(
                    (matched if matched else get_clean_rom_name(clean_stem)) + ext, favs
                )
                if f != new_name:
                    new_full = os.path.join(sp, new_name)
                    if not os.path.exists(new_full):
                        if getattr(self, "dry_run", False):
                            self.log_msg(f" -> [DRY RUN] Would rename SD save: {f} -> {new_name}")
                        else:
                            self.log_msg(f" -> Renaming SD save: {f} -> {new_name}")
                            os.rename(full, new_full)
                        _stat_bump(self, "renamed")
                    else:
                        self.log_msg(
                            f"Warning: Could not rename '{f}' to '{new_name}'"
                            " because destination already exists."
                        )

    @staticmethod
    def _fuzzy_match_rom(clean_stem: str, rom_name_map: dict) -> Optional[str]:
        """Fuzzy-match a save-file stem against the ROM name map."""
        matched = rom_name_map.get(get_fuzzy_title(clean_stem))
        if matched is not None:
            return matched
        # Smart fallback: strip leading chars iteratively.
        # Note: using itertools.islice to avoid Pyre2 slice type issue on Python 3.14
        chars = list(clean_stem)
        for j in range(1, min(21, len(chars) - 2)):
            sub_str: str = "".join(itertools.islice(iter(chars), j, None))
            matched_candidate = rom_name_map.get(get_fuzzy_title(sub_str))
            if matched_candidate is not None:
                return matched_candidate
        return None

    def _mirror_copy(self, src: str, dest: str) -> None:
        """Recursively mirror-copy src to dest, skipping files that match by size+mtime."""
        dry_run = getattr(self, "dry_run", False)
        if not dry_run:
            os.makedirs(dest, exist_ok=True)
        for item in os.listdir(src):
            check_cancel(self)
            s = os.path.join(src, item)
            d = os.path.join(dest, item)
            if os.path.isdir(s):
                self._mirror_copy(s, d)
            else:
                if os.path.exists(d):
                    s_stat = os.stat(s)
                    d_stat = os.stat(d)
                    if s_stat.st_size == d_stat.st_size and mtimes_match(s_stat.st_mtime, d_stat.st_mtime):
                        self.step_progress()
                        continue
                if dry_run:
                    self.log_msg(f" -> [DRY RUN] Would copy: {item}")
                else:
                    self.log_msg(f" -> Copying: {item}")
                    _copy_verified(self, s, d)
                _stat_bump(self, "copied")
                try:
                    _stat_bump(self, "bytes", os.path.getsize(s))
                except OSError:
                    pass
                self.step_progress()

    def mac_cleanup(self, path):
        if platform.system() == "Darwin":
            try:
                subprocess.run(
                    ["dot_clean", "-m", path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    check=False
                )
            except (FileNotFoundError, OSError):
                pass

    # ------------------------------------------------------------------ #
    # Input validation & OS detection                                       #
    # ------------------------------------------------------------------ #

    def _validate_inputs(self, source, hacks, dest) -> bool:
        """Validate paths and warn about dangerous destinations. Returns True if valid."""
        if not source and not hacks:
            self.show_error("Error", "Source path required.")
            return False
        if not dest or not os.path.isdir(dest):
            self.show_error("Error", "Invalid Dest path.")
            return False
        real_dest = os.path.realpath(dest)
        if (source and os.path.realpath(source) == real_dest) or \
                (hacks and os.path.realpath(hacks) == real_dest):
            self.show_error("Error", "Source and Dest cannot match.")
            return False
        # A source inside dest would be deleted by clean_sd; a dest inside
        # source would be rescanned as ROM input. Refuse both.
        for label, p in (("Source", source), ("ROM Hacks", hacks)):
            if not p:
                continue
            real_p = os.path.realpath(p)
            if SyncApp._path_contains(real_dest, real_p) or \
                    SyncApp._path_contains(real_p, real_dest):
                self.show_error(
                    "Error",
                    f"{label} and Dest cannot be nested inside each other —"
                    " a sync could delete or rescan its own files."
                )
                return False
        if not self._confirm_dest_safe(dest, real_dest):
            return False
        has_os = any(
            os.path.exists(os.path.join(dest, d))
            for d in ["EDGB", "GBOS", "GBCSYS", "ED64", "GBASYS", "EDGBA"]
        )
        if not has_os:
            self.show_error("Error", "Missing OS folder on SD.")
            return False
        return True

    @staticmethod
    def _path_contains(parent, child):
        try:
            return os.path.commonpath([parent, child]) == parent
        except ValueError:
            return False

    def _confirm_dest_safe(self, dest, real_dest) -> bool:
        """Warn and confirm if dest looks like a system or dangerous path."""
        sys_drive = (
            os.path.splitdrive(os.environ.get('SystemRoot', 'C:'))[0]
            if platform.system() == "Windows" else ""
        )
        if platform.system() == "Windows" and os.path.splitdrive(dest)[0] == sys_drive:
            return self.ask_okcancel("WARNING", f"Dest is System Drive ({sys_drive}). Proceed?")
        if platform.system() != "Windows" and real_dest in ["/", str(Path.home())]:
            return self.ask_okcancel(
                "WARNING", f"Dest '{dest}' looks like a system path. Proceed?"
            )
        return True

    def _check_free_space(self, source, hacks, dest) -> bool:
        """Pre-flight: refuse to start when the card clearly can't hold the library."""
        try:
            free = shutil.disk_usage(dest).free
        except OSError:
            return True  # can't determine — proceed
        required = 0
        for base in (source, hacks):
            if not (base and os.path.isdir(base)):
                continue
            for p in Path(base).rglob("*"):
                try:
                    if p.is_file() and "Saves_Backup" not in p.parts:
                        required += p.stat().st_size
                except OSError:
                    continue
        reclaimable = 0
        if self.chk_reorganize_var.get():
            # Reorganise moves or deletes every non-system entry on the card,
            # so that space becomes available again during the sync.
            for item in os.listdir(dest):
                if item.lower() in SYSTEM_FOLDERS:
                    continue
                full = os.path.join(dest, item)
                try:
                    if os.path.isfile(full):
                        reclaimable += os.path.getsize(full)
                    else:
                        for root, _, files in os.walk(full):
                            for f in files:
                                try:
                                    reclaimable += os.path.getsize(os.path.join(root, f))
                                except OSError:
                                    continue
                except OSError:
                    continue
        available = free + reclaimable
        if required > available:
            msg = (
                f"Not enough space on the SD card: the library needs"
                f" ~{required / 1_000_000:.0f} MB but only"
                f" ~{available / 1_000_000:.0f} MB would be available."
            )
            if getattr(self, "dry_run", False):
                self.log_msg(f"Warning: {msg} (continuing — dry run)")
                return True
            self.show_error("Error", msg)
            return False
        return True

    def _detect_os_folder(self, dest) -> Tuple[str, str, str]:
        """Detect and return (os_folder, save_base, rtc_base) for the SD card."""
        os_folder = "EDGB"
        for candidate in ["GBOS", "GBCSYS", "ED64", "GBASYS", "EDGBA"]:
            if os.path.exists(os.path.join(dest, candidate)):
                os_folder = candidate
                break

        # Resolve the actual case-preserved folder name on the SD card
        if os.path.isdir(dest):
            for item in os.listdir(dest):
                if item.lower() == os_folder.lower():
                    os_folder = item
                    break

        if os_folder.upper() == "GBOS":
            save_base, rtc_base = "SAVES", "SAVES"
        elif os_folder.upper() in {"ED64", "GBASYS", "EDGBA"}:
            save_base, rtc_base = "SAVE", "SAVE"
        else:
            save_base, rtc_base = "SAVE", "RTC"

        return os_folder, save_base, rtc_base

    # ------------------------------------------------------------------ #
    # Sync pipeline helpers                                                 #
    # ------------------------------------------------------------------ #

    def _prepare_sd_catalog(
        self, dest, rom_exts
    ) -> Tuple[Dict[int, List[Tuple[int, str]]], Optional[str]]:
        """Catalog existing ROMs; if reorganizing, move them to a temp dir first.
        Returns (catalog, temp_sd_dir)."""
        sd_catalog = self.catalog_sd(dest, rom_exts)
        temp_sd_dir = None

        if self.chk_reorganize_var.get() and sd_catalog and not self.dry_run:
            temp_sd_dir = os.path.join(dest, ".sync_temp")
            os.makedirs(temp_sd_dir, exist_ok=True)
            updated_catalog: Dict[int, List[Tuple[int, str]]] = {}
            file_counter = 0
            for size, entries in sd_catalog.items():
                check_cancel(self)
                new_entries = []
                for mtime, path in entries:
                    if os.path.exists(path):
                        # Files already staged by an interrupted previous sync
                        # stay where they are.
                        if os.path.dirname(path) == temp_sd_dir:
                            new_entries.append((mtime, path))
                            continue
                        ext = os.path.splitext(path)[1]
                        while True:
                            temp_file_path = os.path.join(
                                temp_sd_dir, f"temp_{file_counter}{ext}"
                            )
                            file_counter += 1
                            if not os.path.exists(temp_file_path):
                                break
                        try:
                            shutil.move(path, temp_file_path)
                            new_entries.append((mtime, temp_file_path))
                        except OSError as e:
                            self.log_msg(f"Warning: Could not move {path} to temp SD location: {e}")
                if new_entries:
                    updated_catalog[size] = new_entries
            sd_catalog = updated_catalog

        return sd_catalog, temp_sd_dir

    def _extract_zips(self, source, rom_exts) -> Optional[str]:
        """Extract ROM zips to a temp directory. Returns the temp dir path or None."""
        if not (self.chk_zip_var.get() and source and os.path.isdir(source)):
            return None
        zip_files = list(Path(source).rglob("*.zip"))
        if not zip_files:
            return None
        temp_dir = tempfile.mkdtemp(prefix="EverDrive_")
        self.log_msg(f"Extracting {len(zip_files)} zip files to temp directory...")
        for zf in zip_files:
            check_cancel(self)
            try:
                with zipfile.ZipFile(zf, 'r') as zip_ref:
                    for member in zip_ref.namelist():
                        member_ext = os.path.splitext(member.lower())[1]
                        if member_ext in rom_exts:
                            zip_ref.extract(member, temp_dir)
            except (zipfile.BadZipFile, OSError) as e:
                self.log_msg(f"Failed to extract {zf.name}: {e}")
        return temp_dir

    def _load_favorites(self, source) -> set:
        """Load favorites.txt. Returns a set of fuzzy-matched titles."""
        favs: set = set()
        if not (self.chk_fav_var.get() and source):
            return favs
        fav_path = os.path.join(source, "favorites.txt")
        if not os.path.exists(fav_path):
            return favs
        self.log_msg("Loading favorites from favorites.txt...")
        try:
            with open(fav_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        favs.add(get_fuzzy_title(line))
        except OSError as e:
            self.log_msg(f"Failed to load favorites: {e}")
        return favs

    def _scan_source_files(
        self, source, temp_unzip_dir, rom_exts, save_exts, os_folder_upper
    ) -> Tuple[dict, list, list]:
        """Scan source for files. Returns (system_groups, sav_files, other_files)."""
        _os_excl = {"saves_backup", "gbcsys", "gbos", "edgb", "ed64", "gbasys", "edgba"}
        all_files = []
        if source and os.path.isdir(source):
            for p in Path(source).rglob("*"):
                if not p.is_file():
                    continue
                if p.name.startswith("._") or p.name == ".DS_Store":
                    continue
                if any(part.lower() in _os_excl for part in p.parts):
                    continue
                if p.suffix.lower() == ".zip" and self.chk_zip_var.get():
                    continue
                all_files.append(p)

        if temp_unzip_dir:
            all_files.extend(p for p in Path(temp_unzip_dir).rglob("*") if p.is_file())

        if os_folder_upper == "ED64":
            system_groups = {
                "N64": [f for f in all_files if f.suffix.lower() in {".z64", ".n64", ".v64"}]
            }
        elif os_folder_upper in {"GBASYS", "EDGBA"}:
            system_groups = {"GBA": [f for f in all_files if f.suffix.lower() == ".gba"]}
        else:
            system_groups = {
                "GB": [f for f in all_files if f.suffix.lower() == ".gb"],
                "GBC": [f for f in all_files if f.suffix.lower() == ".gbc"],
            }

        sav_files = [f for f in all_files if f.suffix.lower() in save_exts]
        other_files = [
            f for f in all_files if f.suffix.lower() not in (rom_exts | save_exts | {".zip"})
        ]
        return system_groups, sav_files, other_files

    def _build_reorganize_tree(  # pylint: disable=too-many-arguments,too-many-locals,too-many-branches
        self, source, hacks, os_folder, save_base, rtc_base,
        rom_exts, save_exts, system_groups, sav_files, other_files, favs
    ) -> Tuple[VirtualNode, Dict[str, str]]:
        """Build a virtual tree for reorganize mode. Returns (v_root, rom_name_map)."""
        if self.chk_1g1r_var.get():
            self.log_msg("Applying 1G1R filter...")
            for sys_name, files in system_groups.items():
                system_groups[sys_name] = get_best_region_games(
                    files,
                    self.chk_usa_var.get(), self.chk_world_var.get(),
                    self.chk_eur_var.get(), self.chk_jpn_var.get()
                )

        if self.chk_series_var.get():
            self.log_msg("Analyzing files for series grouping...")

        rom_name_map: Dict[str, str] = {}
        v_root = VirtualNode("", True)

        for sys_name, files in system_groups.items():
            groups = get_series_groups(files) if self.chk_series_var.get() else {}
            for f in files:
                group = groups.get(str(f.absolute()), "")
                parts = [sys_name] if self.chk_type_var.get() else []
                if group:
                    parts.append(group)
                elif self.chk_az_var.get():
                    fc = get_clean_rom_name(f.stem)
                    parts.append(fc[0].upper() if fc and fc[0].isalpha() else "#")
                clean_name = get_clean_rom_name(f.stem, self.chk_tags_var.get())
                parts.append(clean_name + f.suffix)
                add_to_virtual_tree(v_root, str(f.absolute()), parts, False, favs)
                rom_name_map[get_fuzzy_title(f.stem)] = clean_name

        if hacks and os.path.isdir(hacks):
            self._add_hacks_to_tree(v_root, hacks, rom_exts, save_exts, rom_name_map, favs)

        for f in other_files:
            if source:
                try:
                    rel = os.path.relpath(str(f), source)
                    parts = rel.replace("\\", "/").split("/")
                    add_to_virtual_tree(v_root, str(f.absolute()), parts, False, favs)
                except ValueError:
                    pass

        if os_folder.lower() == "edgba":
            add_to_virtual_tree(v_root, "", [os_folder, "gamedata"], True, favs)
        else:
            add_to_virtual_tree(v_root, "", [os_folder, save_base], True, favs)
            add_to_virtual_tree(v_root, "", [os_folder, rtc_base], True, favs)

        all_saves = list(sav_files)
        if hacks and os.path.isdir(hacks):
            all_saves.extend(
                p for p in Path(hacks).rglob("*")
                if p.is_file() and p.suffix.lower() in save_exts
            )

        for s in all_saves:
            self._place_save_in_tree(v_root, s, os_folder, save_base, rtc_base, rom_name_map, favs)

        return v_root, rom_name_map

    def _add_hacks_to_tree(
        self, v_root, hacks, rom_exts, save_exts, rom_name_map, favs
    ):
        self.log_msg("Analyzing ROM Hacks...")
        hack_roms = [
            p for p in Path(hacks).rglob("*")
            if p.is_file() and not p.name.startswith("._") and p.name != ".DS_Store"
            and p.suffix.lower() in rom_exts
        ]
        if self.chk_1g1r_var.get():
            hack_roms = get_best_region_games(
                hack_roms,
                self.chk_usa_var.get(), self.chk_world_var.get(),
                self.chk_eur_var.get(), self.chk_jpn_var.get()
            )
        hack_groups = get_series_groups(hack_roms) if self.chk_series_var.get() else {}
        for f in hack_roms:
            group = hack_groups.get(str(f.absolute()), "")
            parts = ["[ROM Hacks]"]
            if group:
                parts.append(group)
            elif self.chk_az_var.get():
                fc = get_clean_rom_name(f.stem)
                parts.append(fc[0].upper() if fc and fc[0].isalpha() else "#")
            clean_name = get_clean_rom_name(f.stem, self.chk_tags_var.get())
            parts.append(clean_name + f.suffix)
            add_to_virtual_tree(v_root, str(f.absolute()), parts, False, favs)
            rom_name_map[get_fuzzy_title(f.stem)] = clean_name

        for p in Path(hacks).rglob("*"):
            if p.name.startswith("._") or p.name == ".DS_Store":
                continue
            if p.is_file() and p.suffix.lower() not in (rom_exts | save_exts | {".zip"}):
                rel = os.path.relpath(str(p), hacks)
                hack_parts = ["[ROM Hacks]"] + rel.replace("\\", "/").split("/")
                add_to_virtual_tree(v_root, str(p.absolute()), hack_parts, False, favs)

    def _place_save_in_tree(
        self, v_root, s, os_folder, save_base, rtc_base, rom_name_map, favs
    ):
        final_ext = s.suffix
        clean_base: str = str(re.sub(
            r'(?i)^(GBC|GB|GBA|EDGB|GBCSYS|GBOS|SAVE|RTC|SAVES)_+', '', s.stem
        ))
        if not clean_base:
            return
        matched_name = self._fuzzy_match_rom(clean_base, rom_name_map)
        base_name = matched_name if matched_name else get_clean_rom_name(clean_base)
        # Apply the favorites prefix here (not via add_to_virtual_tree) so the
        # GBA Pro gamedata folder gets the same prefix as the save file.
        final_save_name = SyncApp._fav_prefixed(base_name + final_ext, favs)
        if os_folder.lower() == "edgba":
            rom_folder_name = SyncApp._fav_prefixed(base_name + ".gba", favs)
            add_to_virtual_tree(
                v_root, str(s.absolute()),
                [os_folder, "gamedata", rom_folder_name, final_save_name], False, None
            )
        else:
            save_sub = rtc_base if final_ext.lower() == ".rtc" else save_base
            add_to_virtual_tree(
                v_root, str(s.absolute()), [os_folder, save_sub, final_save_name], False, None
            )

    def _run_bypass_mode(
        self, source, hacks, dest, os_folder, save_base, rtc_base, rom_exts, save_exts
    ):
        self.log_msg("Reorganize is OFF — syncing source directly...")
        if source and os.path.isdir(source):
            self._mirror_copy(source, dest)

        if os_folder.lower() != "edgba":
            for sp in [
                os.path.join(dest, os_folder, save_base),
                os.path.join(dest, os_folder, rtc_base),
            ]:
                if os.path.isdir(sp):
                    for sub in os.listdir(sp):
                        sub_path = os.path.join(sp, sub)
                        if os.path.isdir(sub_path):
                            if self.dry_run:
                                self.log_msg(
                                    f" -> [DRY RUN] Would remove invalid save subdirectory: {sub}"
                                )
                            else:
                                self.log_msg(f" -> Removing invalid save subdirectory: {sub}")
                                shutil.rmtree(sub_path, ignore_errors=True)

        if hacks and os.path.isdir(hacks):
            self._bypass_sync_hacks(
                hacks, dest, os_folder, save_base, rtc_base, rom_exts, save_exts
            )

    def _bypass_sync_hacks(  # pylint: disable=too-many-arguments,too-many-locals,too-many-branches,too-many-statements
        self, hacks, dest, os_folder, save_base, rtc_base, rom_exts, save_exts
    ):
        self.log_msg("Syncing ROM Hacks into '[ROM Hacks]' folder...")
        hacks_dest = os.path.join(dest, "[ROM Hacks]")
        if not self.dry_run:
            os.makedirs(hacks_dest, exist_ok=True)

        bypass_hack_roms = [
            p for p in Path(hacks).rglob("*")
            if p.is_file() and not p.name.startswith("._") and p.name != ".DS_Store"
            and p.suffix.lower() in rom_exts
        ]
        if self.chk_1g1r_var.get():
            bypass_hack_roms = get_best_region_games(
                bypass_hack_roms,
                self.chk_usa_var.get(), self.chk_world_var.get(),
                self.chk_eur_var.get(), self.chk_jpn_var.get()
            )
        bypass_hack_groups = get_series_groups(bypass_hack_roms) if self.chk_series_var.get() else {}
        bypass_rom_name_map: Dict[str, str] = {}

        for f in bypass_hack_roms:
            group = bypass_hack_groups.get(str(f.absolute()), "")
            dest_parts = []
            if group:
                dest_parts.append(group)
            elif self.chk_az_var.get():
                fc = get_clean_rom_name(f.stem)
                dest_parts.append(fc[0].upper() if fc and fc[0].isalpha() else "#")
            clean_name = get_clean_rom_name(f.stem, self.chk_tags_var.get())
            target_dir = hacks_dest
            for part in dest_parts:
                target_dir = os.path.join(target_dir, part)
            if self.dry_run:
                self.log_msg(f" -> [DRY RUN] Would copy hack: {clean_name + f.suffix}")
            else:
                os.makedirs(target_dir, exist_ok=True)
                _copy_verified(self, str(f), os.path.join(target_dir, clean_name + f.suffix))
            _stat_bump(self, "copied")
            bypass_rom_name_map[get_fuzzy_title(f.stem)] = clean_name
            self.step_progress()

        for p in Path(hacks).rglob("*"):
            if p.is_file() and p.suffix.lower() in save_exts:
                clean_sav: str = str(re.sub(
                    r'(?i)^(GBC|GB|GBA|EDGB|GBCSYS|GBOS|SAVE|RTC|SAVES)_+', '', p.stem
                ))
                matched_sav = bypass_rom_name_map.get(get_fuzzy_title(clean_sav))
                final_sav_name = (
                    matched_sav if matched_sav else get_clean_rom_name(clean_sav)
                ) + p.suffix
                if os_folder.lower() == "edgba":
                    rom_folder_name = (
                        matched_sav if matched_sav else get_clean_rom_name(clean_sav)
                    ) + ".gba"
                    save_sub_dir = os.path.join(dest, os_folder, "gamedata", rom_folder_name)
                else:
                    save_sub_dir = os.path.join(
                        dest, os_folder,
                        rtc_base if p.suffix.lower() == ".rtc" else save_base
                    )
                if self.dry_run:
                    self.log_msg(f" -> [DRY RUN] Would place save: {final_sav_name}")
                else:
                    os.makedirs(save_sub_dir, exist_ok=True)
                    _copy_verified(self, str(p), os.path.join(save_sub_dir, final_sav_name))
                _stat_bump(self, "copied")

    def _copy_gbcsys_payload(self, gbcsys, dest, os_folder):
        if not (gbcsys and os.path.isdir(gbcsys)):
            return
        self.log_msg("Copying GBCSYS/GBOS payload files...")
        target_os_dir = os.path.join(dest, os_folder)
        if not self.dry_run:
            os.makedirs(target_os_dir, exist_ok=True)
        for root, _, filenames in os.walk(gbcsys):
            check_cancel(self)
            for f in filenames:
                if f.startswith("._") or f == ".DS_Store":
                    continue
                src_file = os.path.join(root, f)
                rel_path = os.path.relpath(src_file, gbcsys)
                target_path = os.path.join(target_os_dir, rel_path)
                if self.dry_run:
                    self.log_msg(f" -> [DRY RUN] Would copy payload: {rel_path}")
                else:
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    _copy_verified(self, src_file, target_path)
                _stat_bump(self, "copied")

    # ------------------------------------------------------------------ #
    # Main sync orchestrator                                                #
    # ------------------------------------------------------------------ #

    def run_sync(self, source=None, hacks=None, gbcsys=None, dest=None, dat=None):
        # Values are passed in by start_sync_thread (read on the main thread);
        # fall back to widget reads for direct callers.
        if source is None:
            source = self.txt_source.get().strip()
        if hacks is None:
            hacks = self.txt_hacks.get().strip()
        if gbcsys is None:
            gbcsys = self.txt_gbcsys.get().strip()
        if dest is None:
            dest = self.txt_dest.get().strip()
        if dat is None:
            dat_widget = getattr(self, "txt_dat", None)
            dat = dat_widget.get().strip() if dat_widget else ""

        dryrun_var = getattr(self, "chk_dryrun_var", None)
        self.dry_run = bool(dryrun_var.get()) if dryrun_var else False
        verify_var = getattr(self, "chk_verify_var", None)
        self.verify_writes = bool(verify_var.get()) if verify_var else False

        if not self._validate_inputs(source, hacks, dest):
            return

        os_folder, save_base, rtc_base = self._detect_os_folder(dest)
        os_folder_upper = os_folder.upper()

        if os_folder_upper == "ED64":
            rom_exts = {".z64", ".n64", ".v64"}
        elif os_folder_upper in {"GBASYS", "EDGBA"}:
            rom_exts = {".gba"}
        else:
            rom_exts = {".gb", ".gbc"}

        save_exts = set(SAVE_EXTS)

        if not self._check_free_space(source, hacks, dest):
            return

        self.after(0, lambda: self.toggle_ui(False))
        temp_unzip_dir = None
        temp_sd_dir = None
        sync_ok = False
        self.stats = {
            "copied": 0, "moved": 0, "removed": 0,
            "renamed": 0, "archived": 0, "bytes": 0,
        }
        merged_name_map: Dict[str, str] = {}
        try:
            if self.dry_run:
                self.log_msg("Starting DRY RUN — no changes will be made...")
            else:
                self.log_msg("Starting Python Sync...")
            self.prog_max = 1
            self.after(0, lambda: self.progress_bar.set(0))

            if self.chk_backups_var.get() and os.path.isdir(dest):
                self.backup_saves(source, hacks, dest, os_folder)

            sd_catalog, temp_sd_dir = self._prepare_sd_catalog(dest, rom_exts)

            if self.chk_reorganize_var.get():
                self.clean_sd(dest, os_folder)

            temp_unzip_dir = self._extract_zips(source, rom_exts)
            favs = self._load_favorites(source)

            system_groups, sav_files, other_files = self._scan_source_files(
                source, temp_unzip_dir, rom_exts, save_exts, os_folder_upper
            )

            if dat:
                self._verify_dat(dat, system_groups)

            persisted_name_map = SyncApp._load_name_manifest(source, hacks)

            if self.chk_reorganize_var.get():
                v_root, rom_name_map = self._build_reorganize_tree(
                    source, hacks, os_folder, save_base, rtc_base,
                    rom_exts, save_exts, system_groups, sav_files, other_files, favs
                )
                merged_name_map = SyncApp._build_merged_name_map(
                    rom_name_map, persisted_name_map
                )

                def count_files(n):
                    c = sum(1 for ch in n.children if not ch.is_folder)
                    for ch in n.children:
                        if ch.is_folder:
                            c += count_files(ch)
                    return c

                self.prog_max = max(1, count_files(v_root))
                self.rename_sd_saves(dest, os_folder, save_base, rtc_base, merged_name_map, favs)
                self._handle_orphaned_saves(
                    dest, os_folder, save_base, rtc_base, merged_name_map,
                    SyncApp._backup_root(source, hacks)
                )
                self.copy_virtual_tree(
                    v_root, dest, sd_catalog,
                    self.chk_folders_last_var.get(), self.chk_recent_var.get()
                )
            else:
                merged_name_map = persisted_name_map
                self._run_bypass_mode(
                    source, hacks, dest, os_folder, save_base, rtc_base, rom_exts, save_exts
                )

            self._copy_gbcsys_payload(gbcsys, dest, os_folder)

            if self.chk_restore_var.get():
                restore_base = source if (source and os.path.isdir(source)) else hacks
                if restore_base and os.path.isdir(restore_base):
                    self.restore_saves(restore_base, dest, os_folder)

            if not self.dry_run:
                self.mac_cleanup(dest)

            self._log_summary()

            if self.dry_run:
                self.log_msg("Dry run complete — no changes were made.")
                self.show_info("Dry Run", "Dry run complete! Check the log for planned changes.")
            else:
                self.log_msg("Sync Complete!")
                ejected = False
                eject_var = getattr(self, "chk_eject_var", None)
                if eject_var and eject_var.get():
                    ejected = self.eject_sd(dest)
                if ejected:
                    self.show_info("Success", "Sync complete! SD card ejected — safe to remove.")
                else:
                    self.show_info("Success", "Sync complete! Safely eject your SD card.")
            sync_ok = True

        except SyncCancelled:
            self.log_msg("Sync cancelled by user.")
            self.show_info(
                "Cancelled",
                "Sync was cancelled. The SD card may be in a partial state"
                " — run a sync again to finish."
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.log_msg(f"ERROR: {str(e)}")
            self.show_error("Error", str(e))
        finally:
            if temp_unzip_dir and os.path.exists(temp_unzip_dir):
                shutil.rmtree(temp_unzip_dir)
            if temp_sd_dir and os.path.exists(temp_sd_dir):
                if sync_ok:
                    # Anything still staged here has no source counterpart —
                    # removing it is the mirror-delete step.
                    shutil.rmtree(temp_sd_dir, ignore_errors=True)
                else:
                    # Cancelled or failed: keep the staged ROMs so nothing on
                    # the SD is lost — the next sync re-catalogs and reuses them.
                    self.log_msg(
                        "Kept staged files in '.sync_temp' on the SD card —"
                        " they will be reused when you run the sync again."
                    )
            if not self.dry_run and merged_name_map:
                self._save_name_manifest(source, hacks, merged_name_map)
            self._write_sync_report(source, hacks)
            self.after(0, lambda: self.toggle_ui(True))
            self.after(0, lambda: self.progress_bar.set(0))

    def _write_sync_report(self, source, hacks):
        """Persist the session log next to the save backups for post-sync auditing."""
        if getattr(self, "dry_run", False):
            return  # dry runs promise to touch nothing, including the log file
        lines = getattr(self, "session_log", None)
        if not lines:
            return
        if source and os.path.isdir(source):
            base = source
        elif hacks and os.path.isdir(hacks):
            base = hacks
        else:
            return
        backup_root = os.path.join(base, "Saves_Backup")
        try:
            os.makedirs(backup_root, exist_ok=True)
            with open(os.path.join(backup_root, "last_sync.log"), "w", encoding="utf-8") as f:
                f.write(
                    f"EverDrive Sync report — {datetime.now().isoformat(timespec='seconds')}\n\n"
                )
                f.write("\n".join(lines) + "\n")
        except OSError:
            pass

    # ------------------------------------------------------------------ #
    # Name manifest — persists fuzzy→clean mappings across syncs          #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _backup_root(source: str, hacks: str) -> Optional[str]:
        """Return the Saves_Backup directory to use, or None if neither path is valid."""
        for base in (source, hacks):
            if base and os.path.isdir(base):
                return os.path.join(base, "Saves_Backup")
        return None

    @staticmethod
    def _load_name_manifest(source: str, hacks: str) -> Dict[str, str]:
        """Load the persisted fuzzy→clean name map from the previous sync."""
        for base in (source, hacks):
            if not (base and os.path.isdir(base)):
                continue
            path = os.path.join(base, "Saves_Backup", "rom_name_map.json")
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return {str(k): str(v) for k, v in data.items()}
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    @staticmethod
    def _build_merged_name_map(
        live_map: Dict[str, str], persisted_map: Dict[str, str]
    ) -> Dict[str, str]:
        """Merge live and persisted maps so saves survive clean-name changes.

        Strategy:
        - Start with persisted entries (historical coverage).
        - Add entries keyed by each live clean name's own fuzzy title — this lets a
          save named after a *previous* clean name be matched on the next sync even
          if the source ROM's fuzzy title has changed slightly.
        - Override with live entries last so the current clean name always wins.
        """
        # Map from get_fuzzy_title(clean_name) → clean_name for every live ROM.
        # Example: clean name "Pokemon - Red Version" → key "pokemon red version"
        live_clean_fuzzies: Dict[str, str] = {}
        for clean_name in live_map.values():
            live_clean_fuzzies[get_fuzzy_title(clean_name)] = clean_name

        merged: Dict[str, str] = {}
        merged.update(persisted_map)       # oldest: persisted history
        merged.update(live_clean_fuzzies)  # middle: clean-name fuzzy aliases
        merged.update(live_map)            # newest: live source-ROM fuzzies (always wins)

        # Word-anagram propagation: if a persisted key's words (ignoring punctuation)
        # are the same set as a live key's words, update the persisted entry to the
        # current clean name. Handles "The X" ↔ "X, The" word-order changes where
        # the comma in the fuzzy key makes the sets differ from the live map key.
        live_word_sets: Dict[frozenset, str] = {}
        for k, v in live_map.items():
            words = frozenset(re.sub(r'[^\w\s]', '', k).split())
            if words:
                live_word_sets[words] = v
        for old_fuzzy in list(persisted_map.keys()):
            if old_fuzzy in live_map:
                continue
            old_words = frozenset(re.sub(r'[^\w\s]', '', old_fuzzy).split())
            if old_words and old_words in live_word_sets:
                merged[old_fuzzy] = live_word_sets[old_words]

        # Prune entries whose clean name no longer exists in the live library:
        # keeps the manifest from growing forever and lets orphan detection
        # fire for saves whose ROM was removed. (When live_map is empty the
        # caller does not persist the empty result, so a bad scan can never
        # wipe the manifest file.)
        live_clean_names = set(live_map.values())
        return {k: v for k, v in merged.items() if v in live_clean_names}

    def _save_name_manifest(
        self, source: str, hacks: str, manifest: Dict[str, str]
    ) -> None:
        """Persist the merged fuzzy→clean name map for the next sync."""
        backup_root = SyncApp._backup_root(source, hacks)
        if not backup_root:
            return
        try:
            os.makedirs(backup_root, exist_ok=True)
            with open(
                os.path.join(backup_root, "rom_name_map.json"), "w", encoding="utf-8"
            ) as f:
                json.dump(manifest, f, indent=2, sort_keys=True)
        except OSError:
            pass

    def _archive_orphan(self, path: str, backup_root: str) -> None:
        """Move an orphaned save (file, or GBA Pro gamedata folder) to the PC backup."""
        name = os.path.basename(path)
        if getattr(self, "dry_run", False):
            self.log_msg(f" -> [DRY RUN] Would archive orphaned save: {name}")
            _stat_bump(self, "archived")
            return
        orphan_dir = os.path.join(backup_root, "Orphaned")
        os.makedirs(orphan_dir, exist_ok=True)
        target = os.path.join(orphan_dir, name)
        base, ext = os.path.splitext(name)
        n = 1
        while os.path.exists(target):
            target = os.path.join(orphan_dir, f"{base} ({n}){ext}")
            n += 1
        try:
            shutil.move(path, target)
            self.log_msg(f" -> Archived orphaned save to PC: {name}")
            _stat_bump(self, "archived")
        except OSError as e:
            self.log_msg(f"Warning: could not archive orphaned save '{name}': {e}")

    def _handle_orphaned_saves(  # pylint: disable=too-many-arguments
        self, dest: str, os_folder: str, save_base: str, rtc_base: str,
        merged_map: Dict[str, str], backup_root: Optional[str] = None
    ) -> None:
        """Warn about SD saves with no matching ROM; optionally archive them to the PC."""
        orphans_var = getattr(self, "chk_orphans_var", None)
        archive = bool(orphans_var.get()) if orphans_var else False
        archive = archive and backup_root is not None

        def _handle(path, label):
            if archive:
                self._archive_orphan(path, backup_root)
            else:
                self.log_msg(
                    f"Warning: {label} has no matching ROM"
                    " — save may be orphaned (source ROM was renamed or removed)."
                )

        if os_folder.lower() == "edgba":
            gamedata = os.path.join(dest, os_folder, "gamedata")
            if not os.path.isdir(gamedata):
                return
            for folder in os.listdir(gamedata):
                stem = os.path.splitext(folder)[0]
                if SyncApp._fuzzy_match_rom(stem, merged_map) is None:
                    _handle(os.path.join(gamedata, folder), f"save folder '{folder}'")
        else:
            for save_dir in [save_base, rtc_base]:
                sp = os.path.join(dest, os_folder, save_dir)
                if not os.path.isdir(sp):
                    continue
                for f in os.listdir(sp):
                    if not os.path.isfile(os.path.join(sp, f)):
                        continue
                    stem = os.path.splitext(f)[0]
                    if SyncApp._fuzzy_match_rom(stem, merged_map) is None:
                        _handle(os.path.join(sp, f), f"save '{f}'")

    def _verify_dat(self, dat_path: str, system_groups: dict) -> None:
        """Verify source ROM CRC32s against a No-Intro (Logiqx XML) DAT file."""
        if not os.path.isfile(dat_path):
            self.log_msg(f"Warning: DAT file not found: {dat_path}")
            return
        try:
            dat_index = load_dat_index(dat_path)
        except (OSError, ValueError) as e:
            self.log_msg(f"Warning: could not read DAT file: {e}")
            return
        all_roms = [f for files in system_groups.values() for f in files]
        if not all_roms:
            return
        self.log_msg(
            f"Verifying {len(all_roms)} ROMs against DAT ({len(dat_index)} entries)..."
        )
        verified, unknown, dups = verify_files_against_dat(
            all_roms, dat_index, on_file=lambda _f: check_cancel(self)
        )
        for f, crc in unknown:
            suffix = f" (CRC {crc})" if crc else ""
            self.log_msg(
                f"DAT: no match for '{f.name}'{suffix} — file may be modified or renamed."
            )
        for f, first in dups:
            self.log_msg(f"DAT: duplicate content — '{f.name}' is identical to '{first.name}'.")
        self.log_msg(
            f"DAT check: {len(verified)}/{len(all_roms)} verified,"
            f" {len(unknown)} unknown, {len(dups)} duplicates."
        )

    def _log_summary(self) -> None:
        s = getattr(self, "stats", None)
        if not s:
            return
        prefix = "[DRY RUN] Planned totals" if getattr(self, "dry_run", False) else "Summary"
        parts = [
            f"{s.get('copied', 0)} copied ({s.get('bytes', 0) / 1_000_000:.1f} MB)",
            f"{s.get('moved', 0)} moved",
            f"{s.get('removed', 0)} removed",
            f"{s.get('renamed', 0)} renamed",
        ]
        if s.get("archived"):
            parts.append(f"{s['archived']} orphaned saves archived")
        self.log_msg(f"{prefix}: " + ", ".join(parts) + ".")

    def eject_sd(self, dest) -> bool:
        sysname = platform.system()
        try:
            if sysname == "Darwin":
                real = os.path.realpath(dest)
                if real.startswith("/Volumes/") and len(real.split("/")) > 2:
                    volume = "/Volumes/" + real.split("/")[2]
                    self.log_msg(f"Ejecting {volume}...")
                    result = subprocess.run(
                        ["diskutil", "eject", volume],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        check=False
                    )
                    if result.returncode == 0:
                        self.log_msg("SD card ejected.")
                        return True
                self.log_msg("Warning: Could not eject automatically — eject manually.")
            elif sysname == "Linux":
                subprocess.run(["sync"], check=False)
                self.log_msg("Filesystem buffers flushed — unmount/eject the card manually.")
            elif sysname == "Windows":
                drive = os.path.splitdrive(dest)[0]
                # Only plain drive letters — never interpolate arbitrary
                # path text into the PowerShell command below.
                if drive and re.fullmatch(r"[A-Za-z]:", drive):
                    self.log_msg(f"Ejecting drive {drive}...")
                    ps_cmd = [
                        "powershell", "-NoProfile", "-Command",
                        f"$sh = New-Object -ComObject Shell.Application; "
                        f"$item = $sh.Namespace(17).ParseName('{drive}'); "
                        f"if ($item) {{ $item.InvokeVerb('Eject'); write-output 'success' }} "
                        f"else {{ throw 'Drive not found' }}"
                    ]
                    result = subprocess.run(ps_cmd, capture_output=True, text=True, check=True)
                    if "success" in result.stdout.lower():
                        self.log_msg("SD card ejected.")
                        return True
                self.log_msg("Warning: Could not eject automatically — eject manually.")
            else:
                self.log_msg("Auto-eject is not supported on this platform — eject manually.")
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.log_msg(f"Warning: Eject failed — eject manually. ({e})")
        return False

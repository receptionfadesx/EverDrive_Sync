import os
import json
import shutil
import re
import zipfile
import platform
from pathlib import Path
from datetime import datetime
import threading
import unicodedata
import tkinter as tk
import itertools
import sys
from tkinter import filedialog, messagebox
import subprocess
import tempfile
import uuid
from collections import defaultdict
from typing import Dict, List, Any, Tuple

try:
    import customtkinter as ctk # type: ignore
except ImportError:
    print("Error: customtkinter is not installed. Please run `pip install customtkinter`")
    exit(1)

# This ensures the UI scales correctly on high-DPI Windows displays
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

CONFIG_FILE = os.path.expanduser("~/.everdrive_sync_config.json")

def get_clean_rom_name(base_name, preserve_tags=False):
    clean = base_name
    suffix = ""
    if re.search(r'(?i)(Hack|Translation|Patched)', clean):
        suffix = " [Hack]"
    
    if not preserve_tags:
        clean = re.sub(r'\s*\([^)]+\)\s*', ' ', clean)
        clean = re.sub(r'\s*\[[^\]]+\]\s*', ' ', clean)
    
    # Strip accents
    clean = unicodedata.normalize('NFKD', clean).encode('ascii', 'ignore').decode('ascii')
    
    clean = re.sub(r'_+', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    
    match = re.match(r'(?i)^The\s+(.+)$', clean)
    if match:
        clean = match.group(1) + ", The"
        
    final = (clean + suffix).strip()
    return final if final else base_name

def get_fuzzy_title(base_name):
    t = re.sub(r'\s*\([^)]+\)\s*', ' ', base_name)
    t = re.sub(r'\s*\[[^\]]+\]\s*', ' ', t)
    t = re.sub(r'[-_]', ' ', t)
    t = re.sub(r'\s+', ' ', t)
    return t.strip().lower()

def get_best_region_games(files, usa=True, world=True, eur=True, jpn=True):
    best_games = []
    grouped = {}
    
    for f in files:
        clean = get_clean_rom_name(f.stem)
        if clean not in grouped: grouped[clean] = []
        grouped[clean].append(f)
        
    for clean, group in grouped.items():
        if len(group) == 1:
            best_games.append(group[0])
            continue
            
        best_game = None
        best_score = 999
        
        for f in group:
            name = f.stem
            score = 500
            
            if re.search(r'\(USA', name):
                if usa: score = 10
                else: continue
            elif re.search(r'\(World', name):
                if world: score = 20
                else: continue
            elif re.search(r'\(Europe', name):
                if eur: score = 30
                else: continue
            elif re.search(r'\(Japan', name):
                if jpn: score = 80
                else: continue
            else:
                score = 50
                
            rev_match = re.search(r'\(Rev ([0-9]+|[A-Z]+)\)', name)
            if rev_match:
                rev = rev_match.group(1)
                if rev in ['1', 'A']: score -= 1
                else: score -= 2
                
            if re.search(r'(?i)Bugfix', name): score -= 5
            elif re.search(r'(?i)Hack', name): score -= 4
            
            if score < best_score:
                best_score = score
                best_game = f
                
        if best_game:
            best_games.append(best_game)
            
    return best_games

def get_series_groups(files):
    mapping = {str(f.absolute()): "" for f in files}
    if len(files) < 2: return mapping
    
    known = ["Pokemon", "Mario", "Zelda", "Donkey Kong", "Wario", "Mega Man", 
        "Castlevania", "Bomberman", "Final Fantasy", "Dragon Quest", 
        "Kirby", "Tetris", "Metroid", "Street Fighter", "Mortal Kombat",
        "Tomb Raider", "Resident Evil", "Tony Hawk", "Pac-Man", "Crash Bandicoot",
        "Rayman", "Harvest Moon", "Star Wars", "Disney", "Batman", "Spider-Man",
        "X-Men", "Yu-Gi-Oh", "Harry Potter", "Ninja Turtles", "Contra",
        "Metal Gear", "Ghosts 'n Goblins", "Gex", "Earthworm Jim", "Bionic Commando",
        "Double Dragon", "Game & Watch", "R-Type", "Sonic", "Shantae", "Metal Slug",
        "Medabots", "Digimon", "Monster Rancher", "Micro Machines", "SimCity"]
        
    assigned = set()
    for f in files:
        clean = get_clean_rom_name(f.stem)
        for k in known:
            if re.search(rf'(?i)\b{re.escape(k)}\b', clean):
                mapping[str(f.absolute())] = k
                assigned.add(str(f.absolute()))
                break
                
    prefix_files = {}
    unassigned = [f for f in files if str(f.absolute()) not in assigned]
    
    for f1, f2 in itertools.combinations(unassigned, 2):
        if not isinstance(f1, Path) or not isinstance(f2, Path): continue
        n1 = re.sub(r'\s*[:-].*', '', get_clean_rom_name(f1.stem))
        n2 = re.sub(r'\s*[:-].*', '', get_clean_rom_name(f2.stem))
        w1 = [w for w in re.split(r'[\s_]+', n1) if w.strip()]
        w2 = [w for w in re.split(r'[\s_]+', n2) if w.strip()]
        
        lcp = []
        for k in range(min(len(w1), len(w2))):
            if w1[k].lower() == w2[k].lower():
                lcp.append(w1[k])
            else: break
            
        if len(lcp) >= 2:
            prefix = " ".join(lcp)
            if prefix not in prefix_files: prefix_files[prefix] = set()
            curr_set = prefix_files.get(prefix)
            if curr_set is not None:
                curr_set.add(str(f1.absolute()))
                curr_set.add(str(f2.absolute()))
                
    valid = []
    for p, f_set in prefix_files.items():
        valid.append((p, len(p.split(" ")), f_set))
        
    sorted_pref = sorted(valid, key=lambda x: (x[1], -len(x[2])))
    
    for p, words, f_set in sorted_pref:
        un = [f for f in f_set if f not in assigned]
        if len(un) >= 3:
            for f in un:
                f_str = str(f)
                mapping[f_str] = p
                assigned.add(f_str)
                
    return mapping

class VirtualNode:
    def __init__(self, name, is_folder=False, source_path=None, last_write_time=0.0):
        self.name = name
        self.is_folder = is_folder
        self.source_path = source_path
        self.last_write_time = last_write_time
        self.children = []

def add_to_virtual_tree(root, source_path, dest_parts, folder_only=False, fav_list=None):
    current = root
    clean_parts = [p for p in dest_parts if p.strip()]
    
    for i, part in enumerate(clean_parts):
        is_last = (i == len(clean_parts) - 1)
        is_folder = True if folder_only else not is_last
        
        child = next((c for c in current.children if c.name == part), None)
        
        if child:
            if is_folder and not child.is_folder:
                child.is_folder = True
        else:
            last_write = 0
            if not is_folder and source_path and os.path.exists(source_path):
                last_write = os.path.getmtime(source_path)
                
            if not is_folder and fav_list and len(fav_list) > 0:
                base_no_ext = os.path.splitext(part)[0]
                fuzzy = get_fuzzy_title(base_no_ext)
                if fuzzy in fav_list:
                    part = "! " + part
                    
            child = VirtualNode(part, is_folder, source_path if not is_folder else None, last_write)
            current.children.append(child)
            
        current = child

class SyncApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Sync Tool for EverDrive (GB/GBA/64)")
        self.geometry("600x850")
        self.resizable(False, False)
        
        self.config_data = {
            "Source": "", "Hacks": "", "GbcSysPayload": "", "Dest": ""
        }
        self.load_config()
        self.set_app_icon()
        self.create_widgets()

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
            except Exception:
                pass
        
    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                for k in self.config_data:
                    if k in data: self.config_data[k] = data[k]
            except (json.JSONDecodeError, OSError):
                pass 

    def save_config(self):
        self.config_data["Source"] = self.txt_source.get()
        self.config_data["Hacks"] = self.txt_hacks.get()
        self.config_data["GbcSysPayload"] = self.txt_gbcsys.get()
        self.config_data["Dest"] = self.txt_dest.get()
        try:
            with open(CONFIG_FILE, "w") as f: json.dump(self.config_data, f)
        except OSError:
            pass

    def create_widgets(self):
        path_frame = ctk.CTkFrame(self)
        path_frame.pack(pady=10, padx=20, fill="x")

        ctk.CTkLabel(path_frame, text="Source:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.txt_source = ctk.CTkEntry(path_frame, width=350)
        self.txt_source.insert(0, self.config_data["Source"])
        self.txt_source.grid(row=0, column=1, padx=5, pady=5)
        ctk.CTkButton(path_frame, text="Browse...", width=80, command=lambda: self.browse_folder(self.txt_source)).grid(row=0, column=2, padx=5, pady=5)

        ctk.CTkLabel(path_frame, text="ROM Hacks:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.txt_hacks = ctk.CTkEntry(path_frame, width=350)
        self.txt_hacks.insert(0, self.config_data["Hacks"])
        self.txt_hacks.grid(row=1, column=1, padx=5, pady=5)
        ctk.CTkButton(path_frame, text="Browse...", width=80, command=lambda: self.browse_folder(self.txt_hacks)).grid(row=1, column=2, padx=5, pady=5)

        ctk.CTkLabel(path_frame, text="GBCSYS:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.txt_gbcsys = ctk.CTkEntry(path_frame, width=350)
        self.txt_gbcsys.insert(0, self.config_data["GbcSysPayload"])
        self.txt_gbcsys.grid(row=2, column=1, padx=5, pady=5)
        ctk.CTkButton(path_frame, text="Browse...", width=80, command=lambda: self.browse_folder(self.txt_gbcsys)).grid(row=2, column=2, padx=5, pady=5)

        ctk.CTkLabel(path_frame, text="SD Card:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.txt_dest = ctk.CTkEntry(path_frame, width=350)
        self.txt_dest.insert(0, self.config_data["Dest"])
        self.txt_dest.grid(row=3, column=1, padx=5, pady=5)
        ctk.CTkButton(path_frame, text="Browse...", width=80, command=lambda: self.browse_folder(self.txt_dest)).grid(row=3, column=2, padx=5, pady=5)

        opt_frame = ctk.CTkFrame(self)
        opt_frame.pack(pady=5, padx=20, fill="both", expand=True)

        self.chk_reorganize_var = tk.BooleanVar(value=True)
        self.chk_reorganize = ctk.CTkCheckBox(opt_frame, text="Auto-Reorganize (Alphabetical)", variable=self.chk_reorganize_var, command=self.toggle_reorg)
        self.chk_reorganize.pack(anchor="w", padx=10, pady=5)

        self.chk_type_var = tk.BooleanVar(value=True)
        self.chk_type = ctk.CTkCheckBox(opt_frame, text="Separate Systems/Types (GB/GBC/GBA/N64)", variable=self.chk_type_var)
        self.chk_type.pack(anchor="w", padx=30, pady=2)

        self.chk_series_var = tk.BooleanVar(value=True)
        self.chk_series = ctk.CTkCheckBox(opt_frame, text="Auto-Create Series Folders", variable=self.chk_series_var)
        self.chk_series.pack(anchor="w", padx=30, pady=2)

        self.chk_az_var = tk.BooleanVar(value=True)
        self.chk_az = ctk.CTkCheckBox(opt_frame, text="A-Z Folders", variable=self.chk_az_var)
        self.chk_az.pack(anchor="w", padx=30, pady=2)

        self.chk_1g1r_var = tk.BooleanVar(value=False)
        self.chk_1g1r = ctk.CTkCheckBox(opt_frame, text="1G1R Filter", variable=self.chk_1g1r_var, command=self.toggle_1g1r)
        self.chk_1g1r.pack(anchor="w", padx=10, pady=5)

        reg_frame = ctk.CTkFrame(opt_frame, fg_color="transparent")
        reg_frame.pack(anchor="w", padx=30, pady=0)
        
        self.chk_usa_var = tk.BooleanVar(value=True)
        self.chk_usa = ctk.CTkCheckBox(reg_frame, text="USA (1)", variable=self.chk_usa_var, state="disabled")
        self.chk_usa.pack(side="left", padx=5)

        self.chk_world_var = tk.BooleanVar(value=True)
        self.chk_world = ctk.CTkCheckBox(reg_frame, text="World (2)", variable=self.chk_world_var, state="disabled")
        self.chk_world.pack(side="left", padx=5)

        self.chk_eur_var = tk.BooleanVar(value=True)
        self.chk_eur = ctk.CTkCheckBox(reg_frame, text="Europe (3)", variable=self.chk_eur_var, state="disabled")
        self.chk_eur.pack(side="left", padx=5)

        self.chk_jpn_var = tk.BooleanVar(value=True)
        self.chk_jpn = ctk.CTkCheckBox(reg_frame, text="Japan (4)", variable=self.chk_jpn_var, state="disabled")
        self.chk_jpn.pack(side="left", padx=5)

        self.chk_zip_var = tk.BooleanVar(value=False)
        self.chk_zip = ctk.CTkCheckBox(opt_frame, text="Extract zip files", variable=self.chk_zip_var)
        self.chk_zip.pack(anchor="w", padx=10, pady=5)

        self.chk_tags_var = tk.BooleanVar(value=True)
        self.chk_tags = ctk.CTkCheckBox(opt_frame, text="Keep Tags", variable=self.chk_tags_var)
        self.chk_tags.pack(anchor="w", padx=10, pady=2)

        self.chk_backups_var = tk.BooleanVar(value=True)
        self.chk_backups = ctk.CTkCheckBox(opt_frame, text="Backup SD saves to PC", variable=self.chk_backups_var)
        self.chk_backups.pack(anchor="w", padx=10, pady=2)

        self.chk_restore_var = tk.BooleanVar(value=False)
        self.chk_restore = ctk.CTkCheckBox(opt_frame, text="Restore saves from PC to SD", variable=self.chk_restore_var)
        self.chk_restore.pack(anchor="w", padx=10, pady=2)

        self.chk_folders_last_var = tk.BooleanVar(value=False)
        self.chk_folders_last = ctk.CTkCheckBox(opt_frame, text="Advanced: Folders AFTER games", variable=self.chk_folders_last_var)
        self.chk_folders_last.pack(anchor="w", padx=10, pady=2)

        self.chk_recent_var = tk.BooleanVar(value=False)
        self.chk_recent = ctk.CTkCheckBox(opt_frame, text="Advanced: Sort Hacks by Date", variable=self.chk_recent_var)
        self.chk_recent.pack(anchor="w", padx=10, pady=2)

        self.chk_fav_var = tk.BooleanVar(value=False)
        self.chk_fav = ctk.CTkCheckBox(opt_frame, text="Advanced: Push favorites to top", variable=self.chk_fav_var)
        self.chk_fav.pack(anchor="w", padx=10, pady=2)

        self.txt_log = ctk.CTkTextbox(self, height=150, font=("Consolas", 12))
        self.txt_log.pack(pady=10, padx=20, fill="x")
        self.txt_log.insert("0.0", "Ready to sync.\n")
        self.txt_log.configure(state="disabled")

        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.pack(pady=5, padx=20, fill="x")
        self.progress_bar.set(0)

        self.btn_start = ctk.CTkButton(self, text="Start Sync", fg_color="green", hover_color="darkgreen", command=self.start_sync_thread)
        self.btn_start.pack(pady=10)

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

    def browse_folder(self, entry_widget):
        folder = filedialog.askdirectory()
        if folder:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, folder)

    def log_msg(self, msg):
        print(msg)
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
        val = self.progress_bar.get() + (1/max(1, self.prog_max))
        self.progress_bar.set(min(1.0, val))
        self.update_idletasks()

    def toggle_ui(self, enabled):
        state = "normal" if enabled else "disabled"
        self.btn_start.configure(state=state)
        self.txt_source.configure(state=state)
        self.txt_dest.configure(state=state)
        self.txt_hacks.configure(state=state)
        self.txt_gbcsys.configure(state=state)
        if enabled:
            self.toggle_reorg()
            self.toggle_1g1r()
        else:
            self.chk_type.configure(state="disabled")
            self.chk_series.configure(state="disabled")
            self.chk_az.configure(state="disabled")
            self.chk_usa.configure(state="disabled")
            self.chk_world.configure(state="disabled")
            self.chk_eur.configure(state="disabled")
            self.chk_jpn.configure(state="disabled")
        self.chk_reorganize.configure(state=state)
        self.chk_1g1r.configure(state=state)
        self.chk_zip.configure(state=state)
        self.chk_tags.configure(state=state)
        self.chk_backups.configure(state=state)
        self.chk_restore.configure(state=state)
        self.chk_fav.configure(state=state)
        self.chk_folders_last.configure(state=state)
        self.chk_recent.configure(state=state)

    def start_sync_thread(self):
        self.save_config()
        self.txt_log.configure(state="normal")
        self.txt_log.delete("0.0", "end")
        self.txt_log.configure(state="disabled")
        threading.Thread(target=self.run_sync, daemon=True).start()
        
    def copy_virtual_tree(self, node, current_dest, sd_catalog, folders_last, recent_sort):
        if not node.children: return
        
        # folder_sort_desc=True means folders should sort FIRST (lower key value)
        # We use != so that when is_folder matches folder_sort_desc, the key is False (lower = earlier)
        folder_sort_desc = not folders_last
        
        if recent_sort and re.search(r'(?i)\[?(ROM Hacks|New Additions|Recent)\]?', node.name):
            sorted_child = sorted(node.children, key=lambda c: (c.is_folder != folder_sort_desc, -c.last_write_time))
        else:
            sorted_child = sorted(node.children, key=lambda c: (c.is_folder != folder_sort_desc, c.name.lower()))
            
        for child in sorted_child:
            target_name = child.name
            
            # Path Length Guard: Windows MAX_PATH is 260. 
            # We target 240 as a safe limit for the full path.
            projected_path = os.path.join(current_dest, target_name)
            if len(projected_path) > 240:
                allowed_chars = 240 - len(current_dest) - 1
                if not child.is_folder and "." in target_name:
                    base, ext = os.path.splitext(target_name)
                    if allowed_chars > len(ext):
                        target_name = base[:allowed_chars - len(ext)] + ext
                else:
                    if allowed_chars > 0:
                        target_name = target_name[:allowed_chars]
            
            target_path = os.path.join(current_dest, target_name)
            
            if child.is_folder:
                # Path traversal guard
                dest_real = os.path.realpath(current_dest)
                target_real = os.path.realpath(target_path)
                try:
                    is_safe = os.path.commonpath([dest_real, target_real]) == dest_real
                except ValueError:
                    is_safe = False
                    
                if not is_safe:
                    raise ValueError(f"Path traversal detected: {target_path}")

                if not os.path.exists(target_path):
                    os.makedirs(target_path, exist_ok=True)
                    self.log_msg(f"Created Folder: {target_name}")
                self.copy_virtual_tree(child, target_path, sd_catalog, folders_last, recent_sort)
            else:
                if not child.source_path:
                    self.step_progress()
                    continue
                    
                # Path traversal guard for file
                dest_real = os.path.realpath(current_dest)
                target_real = os.path.realpath(target_path)
                try:
                    is_safe = os.path.commonpath([dest_real, target_real]) == dest_real
                except ValueError:
                    is_safe = False
                    
                if not is_safe:
                    raise ValueError(f"Path traversal detected: {target_path}")

                source_stat = os.stat(child.source_path)
                file_sig = (source_stat.st_size, int(source_stat.st_mtime), os.path.basename(child.source_path))
                
                # Check if already at destination
                if os.path.exists(target_path):
                    dst_stat = os.stat(target_path)
                    if dst_stat.st_size == source_stat.st_size and int(dst_stat.st_mtime) == int(source_stat.st_mtime):
                        if file_sig in sd_catalog and target_path in sd_catalog[file_sig]:
                            sd_catalog[file_sig].remove(target_path)
                        self.step_progress()
                        continue
                    os.remove(target_path)

                # Check if exists elsewhere on SD for a quick move
                if file_sig in sd_catalog and sd_catalog[file_sig]:
                    existing_path = sd_catalog[file_sig].pop()
                    self.log_msg(f" -> Moving (Local): {child.name}")
                    shutil.move(existing_path, target_path)
                    self.step_progress()
                    continue
                    
                self.log_msg(f" -> Copying: {child.name}")
                shutil.copy2(child.source_path, target_path)
                self.step_progress()

    def backup_saves(self, source: str, hacks: str, dest: str, os_folder: str) -> None:
        self.log_msg("Backing up save files to PC...")
        # Choose best backup location: prefer source, fallback to hacks, skip if neither valid
        if source and os.path.isdir(source):
            backup_dir = os.path.join(source, "Saves_Backup")
        elif hacks and os.path.isdir(hacks):
            backup_dir = os.path.join(hacks, "Saves_Backup")
        else:
            self.log_msg("Warning: Cannot back up saves — no valid source folder found.")
            return
        os.makedirs(backup_dir, exist_ok=True)
        
        saves_found: List[str] = []
        for root, _, filenames in os.walk(dest):
            if any(x in root.split(os.sep) for x in ["System Volume Information", "Saves_Backup"]):
                continue
            for f in filenames:
                if f.lower().endswith(('.sav', '.srm', '.rtc', '.fla', '.eep', '.sra')):
                    src_file = os.path.join(root, f)
                    rel_path = f
                    root_parts_lower = [p.lower() for p in Path(root).parts]
                    if os_folder.lower() in root_parts_lower:
                        idx = root_parts_lower.index(os_folder.lower())
                        actual_os_path = os.path.join(*Path(root).parts[:idx+1])
                        rel_path = os.path.relpath(src_file, actual_os_path)
                    
                    save_dest = os.path.join(backup_dir, rel_path)
                    os.makedirs(os.path.dirname(save_dest), exist_ok=True)
                    shutil.copy2(src_file, save_dest)
                    saves_found.append(src_file)
        self.log_msg(f"Backed up {len(saves_found)} files.")

    def restore_saves(self, source: str, dest: str, os_folder: str) -> None:
        backup_dir = os.path.join(source, "Saves_Backup")
        if os.path.isdir(backup_dir):
            self.log_msg("Restoring saves from PC to SD...")
            save_base = "SAVES" if os_folder.upper() == "GBOS" else "SAVE"
            rtc_base = "SAVES" if os_folder.upper() == "GBOS" else "RTC"
            restored_files: List[str] = []
            for root, _, filenames in os.walk(backup_dir):
                for f in filenames:
                    if f.lower().endswith(('.sav', '.srm', '.rtc', '.fla', '.eep', '.sra')):
                        src_file = os.path.join(root, f)
                        rel_path = os.path.relpath(src_file, backup_dir)
                        path_parts = Path(rel_path).parts
                        if len(path_parts) == 1:
                            if os_folder.lower() == "edgba":
                                stem, ext = os.path.splitext(f)
                                save_sub = os.path.join("gamedata", f"{stem}.gba")
                                target_path = os.path.join(dest, os_folder, save_sub, f)
                            else:
                                save_sub = rtc_base if f.lower().endswith('.rtc') else save_base
                                target_path = os.path.join(dest, os_folder, save_sub, f)
                        else:
                            target_path = os.path.join(dest, os_folder, rel_path)
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        shutil.copy2(src_file, target_path)
                        restored_files.append(target_path)
            self.log_msg(f"Restored {len(restored_files)} files.")

    def catalog_sd(self, dest: str, rom_exts: set) -> Dict[Tuple[int, int, str], List[str]]:
        catalog: Dict[Tuple[int, int, str], List[str]] = {}
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
                            sig = (int(f_stat.st_size), int(f_stat.st_mtime), str(f))
                            catalog.setdefault(sig, []).append(f_path)
                        except OSError:
                            continue
        return catalog

    def clean_sd(self, dest: str, os_folder: str) -> None:
        """Remove all non-system files/folders from the SD card root (Soft Format).
        This ensures the FAT32 filesystem creates entries in alphabetical order."""
        self.log_msg("Cleaning SD card (preserving EverDrive OS folders)...")
        system_folders = {"edgb", "gbos", "gbcsys", "ed64", "gbasys", "edgba", "system volume information"}
        for item in os.listdir(dest):
            if item.lower() in system_folders:
                continue
            full = os.path.join(dest, item)
            try:
                if os.path.isdir(full):
                    shutil.rmtree(full)
                else:
                    os.remove(full)
            except OSError as e:
                self.log_msg(f"Warning: Could not remove '{item}': {e}")

    def rename_sd_saves(self, dest: str, os_folder: str, save_base: str, rtc_base: str, rom_name_map: dict) -> None:
        """Rename existing saves on the SD card to match current ROM naming settings."""
        is_gba_pro = (os_folder.lower() == "edgba")
        if is_gba_pro:
            gamedata_path = os.path.join(dest, os_folder, "gamedata")
            if os.path.isdir(gamedata_path):
                self.log_msg("Checking GBA PRO gamedata folders for renames...")
                for item in os.listdir(gamedata_path):
                    item_path = os.path.join(gamedata_path, item)
                    if os.path.isdir(item_path) and item.lower().endswith(".gba"):
                        stem = os.path.splitext(item)[0]
                        clean_stem = str(re.sub(r'(?i)^(GBC|GB|GBA|EDGB|GBCSYS|GBOS|SAVE|RTC|SAVES)_*', '', stem))
                        if not clean_stem:
                            continue
                        fuzzy = get_fuzzy_title(clean_stem)
                        matched = rom_name_map.get(fuzzy)
                        if matched is None:
                            chars = list(clean_stem)
                            chars_len = len(chars)
                            for j in range(1, min(21, chars_len - 2)):
                                sub_str = "".join(itertools.islice(iter(chars), j, None))
                                matched_candidate = rom_name_map.get(get_fuzzy_title(sub_str))
                                if matched_candidate is not None:
                                    matched = matched_candidate
                                    break
                        if matched:
                            new_folder_name = matched + ".gba"
                            # Rename files inside the folder first
                            for f in os.listdir(item_path):
                                f_path = os.path.join(item_path, f)
                                if os.path.isfile(f_path):
                                    f_stem, f_ext = os.path.splitext(f)
                                    if f_stem.lower() == stem.lower():
                                        new_f_name = matched + f_ext
                                        new_f_path = os.path.join(item_path, new_f_name)
                                        if not os.path.exists(new_f_path):
                                            os.rename(f_path, new_f_path)
                            
                            # Rename the folder itself
                            if item != new_folder_name:
                                new_folder_path = os.path.join(gamedata_path, new_folder_name)
                                if not os.path.exists(new_folder_path):
                                    self.log_msg(f" -> Renaming GBA PRO folder: {item} -> {new_folder_name}")
                                    os.rename(item_path, new_folder_path)
        else:
            sys_paths = [
                (os.path.join(dest, os_folder, save_base), False),
                (os.path.join(dest, os_folder, rtc_base), True),
            ]
            for sp, is_rtc in sys_paths:
                if not os.path.isdir(sp):
                    continue
                self.log_msg(f"Checking SD saves folder '{os.path.basename(sp)}' for renames...")
                for f in os.listdir(sp):
                    full = os.path.join(sp, f)
                    if not os.path.isfile(full):
                        continue
                    stem, ext = os.path.splitext(f)
                    clean_stem: str = str(re.sub(r'(?i)^(GBC|GB|GBA|EDGB|GBCSYS|GBOS|SAVE|RTC|SAVES)_*', '', stem))
                    if not clean_stem:
                        continue
                    fuzzy = get_fuzzy_title(clean_stem)
                    matched = rom_name_map.get(fuzzy)
                    if matched is None:
                        # Smart fallback: strip leading chars iteratively
                        # Note: using itertools.islice to avoid Pyre2 slice type issue on Python 3.14
                        chars = list(clean_stem)
                        chars_len = len(chars)
                        for j in range(1, min(21, chars_len - 2)):
                            sub_str: str = "".join(itertools.islice(iter(chars), j, None))
                            sub_fuzzy = get_fuzzy_title(sub_str)
                            matched_candidate = rom_name_map.get(sub_fuzzy)
                            if matched_candidate is not None:
                                matched = matched_candidate
                                break
                    new_name = (matched if matched else get_clean_rom_name(clean_stem)) + ext

    def _mirror_copy(self, src: str, dest: str) -> None:
        """Recursively mirror-copy src to dest, skipping files that match by size+mtime."""
        os.makedirs(dest, exist_ok=True)
        for item in os.listdir(src):
            s = os.path.join(src, item)
            d = os.path.join(dest, item)
            if os.path.isdir(s):
                self._mirror_copy(s, d)
            else:
                if os.path.exists(d):
                    s_stat = os.stat(s)
                    d_stat = os.stat(d)
                    if s_stat.st_size == d_stat.st_size and int(s_stat.st_mtime) == int(d_stat.st_mtime):
                        self.step_progress()
                        continue
                self.log_msg(f" -> Copying: {item}")
                shutil.copy2(s, d)
                self.step_progress()

    def mac_cleanup(self, path):
        if platform.system() == "Darwin":
            try:
                subprocess.run(["dot_clean", "-m", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except (FileNotFoundError, OSError):
                pass

    def run_sync(self):
        source = self.txt_source.get().strip()
        hacks = self.txt_hacks.get().strip()
        gbcsys = self.txt_gbcsys.get().strip()
        dest = self.txt_dest.get().strip()
        
        if not source and not hacks:
            self.after(0, lambda: messagebox.showerror("Error", "Source path required."))
            return
        if not dest or not os.path.isdir(dest):
            self.after(0, lambda: messagebox.showerror("Error", "Invalid Dest path."))
            return
        if source == dest or hacks == dest:
            self.after(0, lambda: messagebox.showerror("Error", "Source and Dest cannot match."))
            return
            
        sys_drive = os.path.splitdrive(os.environ.get('SystemRoot', 'C:'))[0] if platform.system() == "Windows" else ""
        if platform.system() == "Windows" and os.path.splitdrive(dest)[0] == sys_drive:
            if not messagebox.askokcancel("WARNING", f"Dest is System Drive ({sys_drive}). Proceed?"):
                return
        
        if platform.system() != "Windows":
            real_dest = os.path.realpath(dest)
            dangerous = ["/", str(Path.home())]
            if real_dest in dangerous:
                if not messagebox.askokcancel("WARNING", f"Dest '{dest}' looks like a system path. Proceed?"):
                    return
                
        has_os = any(os.path.exists(os.path.join(dest, d)) for d in ["EDGB", "GBOS", "GBCSYS", "ED64", "GBASYS", "EDGBA"])
        if not has_os:
            self.after(0, lambda: messagebox.showerror("Error", "Missing OS folder on SD."))
            return
            
        os_folder = "EDGB"
        if os.path.exists(os.path.join(dest, "GBOS")): os_folder = "GBOS"
        elif os.path.exists(os.path.join(dest, "GBCSYS")): os_folder = "GBCSYS"
        elif os.path.exists(os.path.join(dest, "ED64")): os_folder = "ED64"
        elif os.path.exists(os.path.join(dest, "GBASYS")): os_folder = "GBASYS"
        elif os.path.exists(os.path.join(dest, "EDGBA")): os_folder = "EDGBA"
        
        # Resolve the actual case-preserved folder name on the SD card
        if os.path.isdir(dest):
            for item in os.listdir(dest):
                if item.lower() == os_folder.lower():
                    os_folder = item
                    break
        
        if os_folder.upper() == "GBOS":
            save_base = "SAVES"
            rtc_base = "SAVES"
        elif os_folder.upper() in {"ED64", "GBASYS", "EDGBA"}:
            save_base = "SAVE"
            rtc_base = "SAVE"
        else:
            save_base = "SAVE"
            rtc_base = "RTC"
        
        self.after(0, lambda: self.toggle_ui(False))
        try:
            self.log_msg("Starting Python Sync...")
            self.prog_max = 1
            self.progress_bar.set(0)
            
            temp_unzip_dir = None
            
            # --- Save Backup --- #
            if self.chk_backups_var.get() and os.path.isdir(dest):
                self.backup_saves(source, hacks, dest, os_folder)

            # Define systems / categories based on target console
            os_folder_upper = os_folder.upper()
            if os_folder_upper == "ED64":
                rom_exts = {".z64", ".n64", ".v64"}
            elif os_folder_upper in {"GBASYS", "EDGBA"}:
                rom_exts = {".gba"}
            else:
                rom_exts = {".gb", ".gbc"}

            save_exts = {".sav", ".rtc", ".srm", ".fla", ".eep", ".sra"}

            # --- SD Cataloging MUST run before clean_sd so we capture existing files for moves --- #
            sd_catalog = self.catalog_sd(dest, rom_exts)

            # --- SD Cleaning (Soft Format) --- #
            if self.chk_reorganize_var.get():
                self.clean_sd(dest, os_folder)

            # --- Zip Extraction --- #
            if self.chk_zip_var.get() and source and os.path.isdir(source):
                zip_files = list(Path(source).rglob("*.zip"))
                if zip_files:
                    temp_unzip_dir = tempfile.mkdtemp(prefix="EverDrive_")
                    self.log_msg(f"Extracting {len(zip_files)} zip files to temp directory...")
                    for zf in zip_files:
                        try:
                            with zipfile.ZipFile(zf, 'r') as zip_ref:
                                for member in zip_ref.namelist():
                                    member_ext = os.path.splitext(member.lower())[1]
                                    if member_ext in rom_exts:
                                        zip_ref.extract(member, temp_unzip_dir)
                        except Exception as e:
                            self.log_msg(f"Failed to extract {zf.name}: {e}")

            # --- Favorites Support --- #
            favs = set()
            if self.chk_fav_var.get() and source:
                fav_path = os.path.join(source, "favorites.txt")
                if os.path.exists(fav_path):
                    self.log_msg("Loading favorites from favorites.txt...")
                    try:
                        with open(fav_path, "r", encoding="utf-8") as f:
                            for line in f:
                                line = line.strip()
                                if line:
                                    favs.add(get_fuzzy_title(line))
                    except Exception as e:
                        self.log_msg(f"Failed to load favorites: {e}")

            # GAP 5: Exclude OS subfolders + Saves_Backup from source scan
            _os_excl = {"saves_backup", "gbcsys", "gbos", "edgb", "ed64", "gbasys", "edgba"}

            # --- Scan Source Files --- #
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
                for p in Path(temp_unzip_dir).rglob("*"):
                    if p.is_file():
                        all_files.append(p)

            # Categorize ROMs and saves
            if os_folder_upper == "ED64":
                system_groups = {
                    "N64": [f for f in all_files if f.suffix.lower() in {".z64", ".n64", ".v64"}]
                }
            elif os_folder_upper in {"GBASYS", "EDGBA"}:
                system_groups = {
                    "GBA": [f for f in all_files if f.suffix.lower() == ".gba"]
                }
            else:
                system_groups = {
                    "GB": [f for f in all_files if f.suffix.lower() == ".gb"],
                    "GBC": [f for f in all_files if f.suffix.lower() == ".gbc"]
                }

            sav_files = [f for f in all_files if f.suffix.lower() in save_exts]
            other_files = [f for f in all_files if f.suffix.lower() not in (rom_exts | save_exts | {".zip"})]

            if self.chk_reorganize_var.get():
                # ==========================================================
                # REORGANIZE MODE: Build virtual tree, then copy it
                # ==========================================================
                if self.chk_1g1r_var.get():
                    self.log_msg("Applying 1G1R filter...")
                    for sys_name, files in system_groups.items():
                        system_groups[sys_name] = get_best_region_games(files, self.chk_usa_var.get(), self.chk_world_var.get(), self.chk_eur_var.get(), self.chk_jpn_var.get())

                if self.chk_series_var.get():
                    self.log_msg("Analyzing files for series grouping...")

                rom_name_map: Dict[str, str] = {}
                vRoot = VirtualNode("", True)

                # Process dynamically categorized main library files
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
                        add_to_virtual_tree(vRoot, str(f.absolute()), parts, False, favs)
                        rom_name_map[get_fuzzy_title(f.stem)] = clean_name

                # GAP 1: ROM Hacks folder → [ROM Hacks] with full 1G1R/series/A-Z support
                if hacks and os.path.isdir(hacks):
                    self.log_msg("Analyzing ROM Hacks...")
                    hack_roms = [
                        p for p in Path(hacks).rglob("*")
                        if p.is_file() and not p.name.startswith("._") and p.name != ".DS_Store"
                        and p.suffix.lower() in rom_exts
                    ]
                    if self.chk_1g1r_var.get():
                        hack_roms = get_best_region_games(hack_roms, self.chk_usa_var.get(), self.chk_world_var.get(), self.chk_eur_var.get(), self.chk_jpn_var.get())
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
                        add_to_virtual_tree(vRoot, str(f.absolute()), parts, False, favs)
                        rom_name_map[get_fuzzy_title(f.stem)] = clean_name
                    # Non-ROM files from hacks folder (readmes, images, etc.)
                    for p in Path(hacks).rglob("*"):
                        if p.is_file() and p.suffix.lower() not in (rom_exts | save_exts | {".zip"}):
                            rel = os.path.relpath(str(p), hacks)
                            hack_parts = ["[ROM Hacks]"] + rel.replace("\\", "/").split("/")
                            add_to_virtual_tree(vRoot, str(p.absolute()), hack_parts, False, favs)

                # GAP 3: Non-ROM file passthrough from source at relative path
                for f in other_files:
                    if source:
                        try:
                            rel = os.path.relpath(str(f), source)
                            parts = rel.replace("\\", "/").split("/")
                            add_to_virtual_tree(vRoot, str(f.absolute()), parts, False, favs)
                        except ValueError:
                            pass

                # GAP 2: Pre-seed OS save nodes and place save files
                if os_folder.lower() == "edgba":
                    add_to_virtual_tree(vRoot, "", [os_folder, "gamedata"], True, favs)
                else:
                    add_to_virtual_tree(vRoot, "", [os_folder, save_base], True, favs)
                    add_to_virtual_tree(vRoot, "", [os_folder, rtc_base], True, favs)

                all_saves = list(sav_files)
                if hacks and os.path.isdir(hacks):
                    for p in Path(hacks).rglob("*"):
                        if p.is_file() and p.suffix.lower() in save_exts:
                            all_saves.append(p)

                for s in all_saves:
                    final_ext = s.suffix
                    clean_base: str = str(re.sub(r'(?i)^(GBC|GB|GBA|EDGB|GBCSYS|GBOS|SAVE|RTC|SAVES)_*', '', s.stem))
                    if not clean_base:
                        continue
                    fuzzy = get_fuzzy_title(clean_base)
                    matched_name = rom_name_map.get(fuzzy)
                    if matched_name is None:
                        chars_s = list(clean_base)
                        for j in range(1, min(21, len(chars_s) - 2)):
                            sub_str_s: str = "".join(itertools.islice(iter(chars_s), j, None))
                            cand = rom_name_map.get(get_fuzzy_title(sub_str_s))
                            if cand is not None:
                                matched_name = cand
                                break
                    final_save_name = (matched_name if matched_name else get_clean_rom_name(clean_base)) + final_ext
                    if os_folder.lower() == "edgba":
                        rom_folder_name = (matched_name if matched_name else get_clean_rom_name(clean_base)) + ".gba"
                        add_to_virtual_tree(vRoot, str(s.absolute()), [os_folder, "gamedata", rom_folder_name, final_save_name], False, favs)
                    else:
                        save_sub = rtc_base if final_ext.lower() == ".rtc" else save_base
                        add_to_virtual_tree(vRoot, str(s.absolute()), [os_folder, save_sub, final_save_name], False, favs)

                # Count file nodes for progress bar
                def count(n):
                    c = sum(1 for ch in n.children if not ch.is_folder)
                    for ch in n.children:
                        if ch.is_folder:
                            c += count(ch)
                    return c
                self.prog_max = max(1, count(vRoot))

                # Rename existing SD saves to match current naming
                self.rename_sd_saves(dest, os_folder, save_base, rtc_base, rom_name_map)

                self.copy_virtual_tree(vRoot, dest, sd_catalog, self.chk_folders_last_var.get(), self.chk_recent_var.get())

            else:
                # ==========================================================
                # BYPASS MODE — direct mirror copy when Reorganize is OFF
                # ==========================================================
                self.log_msg("Reorganize is OFF — syncing source directly...")
                if source and os.path.isdir(source):
                    self._mirror_copy(source, dest)

                # Fix subdirectories in system save folders (hardware doesn't support them except GBA PRO)
                if os_folder.lower() != "edgba":
                    for sp in [os.path.join(dest, os_folder, save_base), os.path.join(dest, os_folder, rtc_base)]:
                        if os.path.isdir(sp):
                            for sub in os.listdir(sp):
                                sub_path = os.path.join(sp, sub)
                                if os.path.isdir(sub_path):
                                    self.log_msg(f" -> Removing invalid save subdirectory: {sub}")
                                    shutil.rmtree(sub_path, ignore_errors=True)

                if hacks and os.path.isdir(hacks):
                    self.log_msg("Syncing ROM Hacks into '[ROM Hacks]' folder...")
                    hacks_dest = os.path.join(dest, "[ROM Hacks]")
                    os.makedirs(hacks_dest, exist_ok=True)

                    # Apply 1G1R + series grouping to hacks even in bypass mode
                    bypass_hack_roms = [
                        p for p in Path(hacks).rglob("*")
                        if p.is_file() and not p.name.startswith("._") and p.name != ".DS_Store"
                        and p.suffix.lower() in rom_exts
                    ]
                    if self.chk_1g1r_var.get():
                        bypass_hack_roms = get_best_region_games(bypass_hack_roms, self.chk_usa_var.get(), self.chk_world_var.get(), self.chk_eur_var.get(), self.chk_jpn_var.get())
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
                        os.makedirs(target_dir, exist_ok=True)
                        shutil.copy2(str(f), os.path.join(target_dir, clean_name + f.suffix))
                        bypass_rom_name_map[get_fuzzy_title(f.stem)] = clean_name
                        self.step_progress()

                    # Fuzzy-match and place .sav files from hacks into OS save folders
                    for p in Path(hacks).rglob("*"):
                        if p.is_file() and p.suffix.lower() in save_exts:
                            clean_sav: str = str(re.sub(r'(?i)^(GBC|GB|GBA|EDGB|GBCSYS|GBOS|SAVE|RTC|SAVES)_*', '', p.stem))
                            matched_sav = bypass_rom_name_map.get(get_fuzzy_title(clean_sav))
                            final_sav_name = (matched_sav if matched_sav else get_clean_rom_name(clean_sav)) + p.suffix
                            if os_folder.lower() == "edgba":
                                rom_folder_name = (matched_sav if matched_sav else get_clean_rom_name(clean_sav)) + ".gba"
                                save_sub_dir = os.path.join(dest, os_folder, "gamedata", rom_folder_name)
                            else:
                                save_sub_dir = os.path.join(dest, os_folder, rtc_base if p.suffix.lower() == ".rtc" else save_base)
                            os.makedirs(save_sub_dir, exist_ok=True)
                            shutil.copy2(str(p), os.path.join(save_sub_dir, final_sav_name))

            # --- GBCSYS Payload --- #
            if gbcsys and os.path.isdir(gbcsys):
                self.log_msg("Copying GBCSYS/GBOS payload files...")
                target_os_dir = os.path.join(dest, os_folder)
                os.makedirs(target_os_dir, exist_ok=True)
                for root, _, filenames in os.walk(gbcsys):
                    for f in filenames:
                        src_file = os.path.join(root, f)
                        rel_path = os.path.relpath(src_file, gbcsys)
                        target_path = os.path.join(target_os_dir, rel_path)
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        shutil.copy2(src_file, target_path)

            # --- Save Restore --- #
            if self.chk_restore_var.get() and source:
                self.restore_saves(source, dest, os_folder)

            self.mac_cleanup(dest)
            self.log_msg("Sync Complete!")
            self.after(0, lambda: messagebox.showinfo("Success", "Sync complete! Safely eject your SD card."))

        except Exception as e:
            self.log_msg(f"ERROR: {str(e)}")
            self.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            if temp_unzip_dir and os.path.exists(temp_unzip_dir):
                shutil.rmtree(temp_unzip_dir)
            self.after(0, lambda: self.toggle_ui(True))
            self.progress_bar.set(0)

if __name__ == "__main__":
    app = SyncApp()
    app.mainloop()

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

try:
    import customtkinter as ctk # type: ignore
except ImportError:
    print("Error: customtkinter is not installed. Please run `pip install customtkinter`")
    exit(1)

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
        "Yu-Gi-Oh", "Harry Potter", "Ninja Turtles"]
        
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
        self.title("Sync Tool for EverDrive GB X7")
        self.geometry("600x850")
        self.resizable(False, False)
        
        self.config_data = {
            "Source": "", "Hacks": "", "GbcSysPayload": "", "Dest": ""
        }
        self.load_config()
        self.set_app_icon()
        self.create_widgets()

    def get_asset_path(self, relative_path):
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
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
        self.chk_type = ctk.CTkCheckBox(opt_frame, text="Separate (GB/GBC)", variable=self.chk_type_var)
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
        ctk.CTkCheckBox(opt_frame, text="Extract zip files", variable=self.chk_zip_var).pack(anchor="w", padx=10, pady=5)

        self.chk_tags_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(opt_frame, text="Keep Tags", variable=self.chk_tags_var).pack(anchor="w", padx=10, pady=2)

        self.chk_backups_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(opt_frame, text="Backup SD saves to PC", variable=self.chk_backups_var).pack(anchor="w", padx=10, pady=2)

        self.chk_restore_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(opt_frame, text="Restore saves from PC to SD", variable=self.chk_restore_var).pack(anchor="w", padx=10, pady=2)

        self.chk_folders_last_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(opt_frame, text="Advanced: Folders AFTER games", variable=self.chk_folders_last_var).pack(anchor="w", padx=10, pady=2)

        self.chk_recent_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(opt_frame, text="Advanced: Sort Hacks by Date", variable=self.chk_recent_var).pack(anchor="w", padx=10, pady=2)

        self.chk_fav_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(opt_frame, text="Advanced: Push favorites to top", variable=self.chk_fav_var).pack(anchor="w", padx=10, pady=2)

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

    def start_sync_thread(self):
        self.save_config()
        self.txt_log.configure(state="normal")
        self.txt_log.delete("0.0", "end")
        self.txt_log.configure(state="disabled")
        threading.Thread(target=self.run_sync, daemon=True).start()
        
    def copy_virtual_tree(self, node, current_dest, sd_catalog, folders_last, recent_sort):
        if not node.children: return
        
        folder_sort_desc = not folders_last
        
        if recent_sort and re.search(r'(?i)\[?(ROM Hacks|New Additions|Recent)\]?', node.name):
            sorted_child = sorted(node.children, key=lambda c: (c.is_folder == folder_sort_desc, -c.last_write_time))
        else:
            sorted_child = sorted(node.children, key=lambda c: (c.is_folder == folder_sort_desc, c.name.lower()))
            
        for child in sorted_child:
            target_name = child.name
            target_path = os.path.join(current_dest, target_name)
            
            if child.is_folder:
                # Path traversal guard
                dest_real = os.path.realpath(current_dest)
                target_real = os.path.realpath(target_path)
                if not target_real.startswith(dest_real + os.sep) and target_real != dest_real:
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
                if not target_real.startswith(dest_real + os.sep):
                    raise ValueError(f"Path traversal detected: {target_path}")

                if os.path.exists(target_path):
                    dst_stat = os.stat(target_path)
                    src_stat = os.stat(child.source_path)
                    if dst_stat.st_size == src_stat.st_size and int(dst_stat.st_mtime) == int(src_stat.st_mtime):
                        self.step_progress()
                        continue
                    os.remove(target_path)
                    
                self.log_msg(f" -> Copying: {child.name}")
                shutil.copy2(child.source_path, target_path)
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
                
        has_os = any(os.path.exists(os.path.join(dest, d)) for d in ["EDGB", "GBOS", "GBCSYS"])
        if not has_os:
            self.after(0, lambda: messagebox.showerror("Error", "Missing OS folder on SD."))
            return
            
        os_folder = "EDGB"
        if os.path.exists(os.path.join(dest, "GBOS")): os_folder = "GBOS"
        elif os.path.exists(os.path.join(dest, "GBCSYS")): os_folder = "GBCSYS"
        
        save_base = "SAVES" if os_folder == "GBOS" else "SAVE"
        rtc_base = "SAVES" if os_folder == "GBOS" else "RTC"
        
        self.after(0, lambda: self.toggle_ui(False))
        try:
            self.log_msg("Starting Python Sync...")
            self.prog_max = 1
            self.progress_bar.set(0)
            
            # --- Quick Sync Logic --- #
            all_files = []
            if source and os.path.isdir(source):
                for p in Path(source).rglob("*"):
                    if p.is_file() and not p.name.startswith("._") and p.name != ".DS_Store" and p.suffix.lower() != ".zip" and "Saves_Backup" not in p.parts:
                        all_files.append(p)
                        
            gb_files = [f for f in all_files if f.suffix.lower() == ".gb"]
            gbc_files = [f for f in all_files if f.suffix.lower() == ".gbc"]
            
            if self.chk_reorganize_var.get():
                if self.chk_1g1r_var.get():
                    self.log_msg("Applying 1G1R...")
                    gb_files = get_best_region_games(gb_files, self.chk_usa_var.get(), self.chk_world_var.get(), self.chk_eur_var.get(), self.chk_jpn_var.get())
                    gbc_files = get_best_region_games(gbc_files, self.chk_usa_var.get(), self.chk_world_var.get(), self.chk_eur_var.get(), self.chk_jpn_var.get())
                    
                gb_groups = get_series_groups(gb_files) if self.chk_series_var.get() else {}
                gbc_groups = get_series_groups(gbc_files) if self.chk_series_var.get() else {}
                
                vRoot = VirtualNode("", True)
                favs = set() # Optional fav implementation
                
                for f in gb_files:
                    group = gb_groups.get(str(f.absolute()), "")
                    parts = ["GB"] if self.chk_type_var.get() else []
                    if group: parts.append(group)
                    elif self.chk_az_var.get():
                        fc = get_clean_rom_name(f.stem)
                        parts.append(fc[0].upper() if fc and fc[0].isalpha() else "#")
                    parts.append(get_clean_rom_name(f.stem, self.chk_tags_var.get()) + f.suffix)
                    add_to_virtual_tree(vRoot, str(f.absolute()), parts, False, favs)
                    
                for f in gbc_files:
                    group = gbc_groups.get(str(f.absolute()), "")
                    parts = ["GBC"] if self.chk_type_var.get() else []
                    if group: parts.append(group)
                    elif self.chk_az_var.get():
                        fc = get_clean_rom_name(f.stem)
                        parts.append(fc[0].upper() if fc and fc[0].isalpha() else "#")
                    parts.append(get_clean_rom_name(f.stem, self.chk_tags_var.get()) + f.suffix)
                    add_to_virtual_tree(vRoot, str(f.absolute()), parts, False, favs)
                    
                # Count nodes
                def count(n):
                    c = sum(1 for ch in n.children if not ch.is_folder)
                    for ch in n.children:
                        if ch.is_folder: c += count(ch)
                    return c
                self.prog_max = max(1, count(vRoot))
                
                self.log_msg("Virtual tree built. Sequential sync starting...")
                self.copy_virtual_tree(vRoot, dest, {}, self.chk_folders_last_var.get(), self.chk_recent_var.get())

            self.mac_cleanup(dest)
            self.log_msg("Sync Complete!")
            self.after(0, lambda: messagebox.showinfo("Success", "Sync complete! Safely eject your SD card."))

        except Exception as e:
            self.log_msg(f"ERROR: {str(e)}")
            self.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            self.after(0, lambda: self.toggle_ui(True))
            self.progress_bar.set(0)

if __name__ == "__main__":
    app = SyncApp()
    app.mainloop()

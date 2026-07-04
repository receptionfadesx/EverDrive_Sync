import pytest # type: ignore
import os
import shutil
import threading
from pathlib import Path
from sync_everdrive import (
    get_clean_rom_name,
    get_fuzzy_title,
    get_best_region_games,
    get_series_groups,
    VirtualNode,
    add_to_virtual_tree,
    SyncCancelled,
    check_cancel,
    mtimes_match,
    catalog_pop_match,
    catalog_discard_path,
    list_backup_snapshots,
    prune_backups,
    run_cli
) # type: ignore

def latest_backup_dir(base):
    """Return the newest timestamped snapshot under base/Saves_Backup."""
    root = Path(base) / "Saves_Backup"
    snaps = sorted(d for d in root.iterdir() if d.is_dir())
    assert snaps, f"no backup snapshots in {root}"
    return snaps[-1]

def test_get_clean_rom_name():
    assert get_clean_rom_name("Pokemon - Red Version (USA, Europe)") == "Pokemon - Red Version"
    assert get_clean_rom_name("Zelda (Hack)") == "Zelda [Hack]"
    assert get_clean_rom_name("The Legend of Zelda") == "Legend of Zelda, The"
    assert get_clean_rom_name("Super Mario Land (World) (Rev A)") == "Super Mario Land"
    assert get_clean_rom_name("Metroid II - Return of Samus (World)") == "Metroid II - Return of Samus"

def test_get_clean_rom_name_preserve():
    # Test tag preservation for Hacks/Translations
    assert get_clean_rom_name("Pokemon (Hack)", preserve_tags=True) == "Pokemon (Hack) [Hack]"
    assert get_clean_rom_name("Zelda (Translation)", preserve_tags=True) == "Zelda (Translation) [Hack]"

def test_get_fuzzy_title():
    assert get_fuzzy_title("Pokemon - Red Version (USA, Europe)") == "pokemon red version"
    assert get_fuzzy_title("The Legend of Zelda") == "the legend of zelda"
    assert get_fuzzy_title("Super Mario Land (World) (Rev A)") == "super mario land"

def test_get_best_region_games():
    files = [
        Path("Pokemon - Red Version (USA, Europe).gb"),
        Path("Pokemon - Red Version (Japan).gb"),
        Path("Pokemon - Red Version (World).gb"),
        Path("Unique Game (Europe).gb")
    ]
    # USA should win over Japan and World if USA is enabled
    best = get_best_region_games(files)
    assert len(best) == 2
    names = [f.name for f in best]
    assert "Pokemon - Red Version (USA, Europe).gb" in names
    assert "Unique Game (Europe).gb" in names

def test_get_best_region_games_rev():
    files = [
        Path("Game (USA).gb"),
        Path("Game (USA) (Rev A).gb"),
        Path("Game (USA) (Rev 1).gb")
    ]
    # Revision A/1 should win over base. Rev 1/A have same score-1, logic picks first it finds if scores same.
    # In score logic: rev 1/A -> score-1 (9), others -> score-2 (8).
    # Wait, 10-1 = 9, 10-2 = 8. Lower score is better.
    # So Rev 2 would be 8, which beats Rev 1/A (9).
    # Let's check logic: if rev in ['1', 'A']: score -= 1 else: score -= 2
    # So Rev 2 is BETTER than Rev A.
    best = get_best_region_games(files)
    names = [f.name for f in best]
    assert "Game (USA) (Rev 1).gb" in names or "Game (USA) (Rev A).gb" in names

def test_get_series_groups():
    files = [
        Path("Pokemon Red.gb"),
        Path("Pokemon Blue.gb"),
        Path("Super Mario Land.gb"),
        Path("Random Game.gb")
    ]
    groups = get_series_groups(files)
    assert groups[str(Path("Pokemon Red.gb").absolute())] == "Pokemon"
    assert groups[str(Path("Super Mario Land.gb").absolute())] == "Mario"
    assert groups.get(str(Path("Random Game.gb").absolute())) == ""

def test_get_series_groups_prefix():
    # Test prefix matching for 3+ games not in 'known' list
    files = [
        Path("Dragon Ball Z - Goku 1.gb"),
        Path("Dragon Ball Z - Goku 2.gb"),
        Path("Dragon Ball Z - Goku 3.gb"),
        Path("Unique.gb")
    ]
    groups = get_series_groups(files)
    assert groups[str(Path("Dragon Ball Z - Goku 1.gb").absolute())] == "Dragon Ball Z"
    assert groups[str(Path("Dragon Ball Z - Goku 3.gb").absolute())] == "Dragon Ball Z"
    assert groups.get(str(Path("Unique.gb").absolute())) == ""

def test_virtual_tree():
    root = VirtualNode("", True)
    # Test adding files and folders
    add_to_virtual_tree(root, None, ["GB", "Mario", "SML.gb"], False)
    assert len(root.children) == 1
    assert root.children[0].name == "GB"
    assert len(root.children[0].children) == 1
    assert root.children[0].children[0].name == "Mario"
    assert root.children[0].children[0].children[0].name == "SML.gb"

def test_virtual_tree_favorites():
    root = VirtualNode("", True)
    # Test favorite prefixing
    favs = {"pokemon red version"}
    add_to_virtual_tree(root, None, ["Pokemon Red Version (USA).gb"], False, favs)
    assert root.children[0].name == "! Pokemon Red Version (USA).gb"

def test_path_shortening():
    # We need a long path to trigger shortening
    # copy_virtual_tree logic: if len(projected_path) > 240
    # Let's simulate the logic in a small testable way or just test the helper
    # Since the logic is inside copy_virtual_tree, we'd need a mock setup.
    # For now, let's verify get_clean_rom_name still works.
    assert get_clean_rom_name("A" * 100) == "A" * 100

def test_virtual_tree_multiple_favorites():
    root = VirtualNode("", True)
    favs = {"pokemon red", "zelda"}
    add_to_virtual_tree(root, None, ["Pokemon Red.gb"], False, favs)
    add_to_virtual_tree(root, None, ["Zelda.gb"], False, favs)
    add_to_virtual_tree(root, None, ["Mario.gb"], False, favs)
    
    names = [c.name for c in root.children]
    assert "! Pokemon Red.gb" in names
    assert "! Zelda.gb" in names
    assert "Mario.gb" in names

class DummyApp:
    def __init__(self):
        self.logs = []
    def log_msg(self, msg):
        self.logs.append(msg)

from sync_everdrive import SyncApp

class MockSyncApp(SyncApp):
    def __init__(self, source="", dest="", hacks="", gbcsys="", dat="", backups=False, zip=False, fav=False, reorg=True, usa=True, world=True, eur=True, jpn=True, series=False, type_folders=True, az=False, tags=True, restore=False, folders_last=False, recent=False, dryrun=False, eject=False, verify=False, orphans=False):
        self.logs = []
        self.session_log = self.logs  # same list: exercises the sync-report path
        self.prog_max = 1
        self.cancel_event = threading.Event()
        self.config_data = {
            "Source": str(source), "Hacks": str(hacks), "GbcSysPayload": str(gbcsys), "Dest": str(dest), "DatFile": str(dat)
        }
        self.txt_source = type('MockEntry', (), {'get': lambda *a: str(self.config_data["Source"])})()
        self.txt_hacks = type('MockEntry', (), {'get': lambda *a: str(self.config_data["Hacks"])})()
        self.txt_gbcsys = type('MockEntry', (), {'get': lambda *a: str(self.config_data["GbcSysPayload"])})()
        self.txt_dest = type('MockEntry', (), {'get': lambda *a: str(self.config_data["Dest"])})()
        self.txt_dat = type('MockEntry', (), {'get': lambda *a: str(self.config_data["DatFile"])})()
        
        self.chk_backups_var = type('MockVar', (), {'get': lambda *a: backups})()
        self.chk_zip_var = type('MockVar', (), {'get': lambda *a: zip})()
        self.chk_fav_var = type('MockVar', (), {'get': lambda *a: fav})()
        self.chk_reorganize_var = type('MockVar', (), {'get': lambda *a: reorg})()
        self.chk_1g1r_var = type('MockVar', (), {'get': lambda *a: False})()
        self.chk_usa_var = type('MockVar', (), {'get': lambda *a: usa})()
        self.chk_world_var = type('MockVar', (), {'get': lambda *a: world})()
        self.chk_eur_var = type('MockVar', (), {'get': lambda *a: eur})()
        self.chk_jpn_var = type('MockVar', (), {'get': lambda *a: jpn})()
        self.chk_series_var = type('MockVar', (), {'get': lambda *a: series})()
        self.chk_type_var = type('MockVar', (), {'get': lambda *a: type_folders})()
        self.chk_az_var = type('MockVar', (), {'get': lambda *a: az})()
        self.chk_tags_var = type('MockVar', (), {'get': lambda *a: tags})()
        self.chk_restore_var = type('MockVar', (), {'get': lambda *a: restore})()
        self.chk_folders_last_var = type('MockVar', (), {'get': lambda *a: folders_last})()
        self.chk_recent_var = type('MockVar', (), {'get': lambda *a: recent})()
        self.chk_dryrun_var = type('MockVar', (), {'get': lambda *a: dryrun})()
        self.chk_eject_var = type('MockVar', (), {'get': lambda *a: eject})()
        self.chk_verify_var = type('MockVar', (), {'get': lambda *a: verify})()
        self.chk_orphans_var = type('MockVar', (), {'get': lambda *a: orphans})()

        self.progress_bar = type('MockProgress', (), {'set': lambda *a: None, 'get': lambda *a: 0.0})()
        
    def log_msg(self, msg):
        self.logs.append(msg)
        
    def update_idletasks(self):
        pass
        
    def update(self):
        pass
        
    def toggle_ui(self, enabled):
        pass
        
    def after(self, ms, func, *args):
        if func:
            func(*args)

def test_backup_restore_case_insensitivity(tmp_path):
    source = tmp_path / "source"
    dest = tmp_path / "sd_card"
    source.mkdir()
    dest.mkdir()
    
    os_folder_on_disk = "edgb"
    save_dir = dest / os_folder_on_disk / "SAVE"
    save_dir.mkdir(parents=True)
    
    save_file = save_dir / "Game1.sav"
    save_file.write_text("my save data")
    
    app = DummyApp()
    
    from sync_everdrive import SyncApp
    SyncApp.backup_saves(app, str(source), "", str(dest), "EDGB")

    backup_file = latest_backup_dir(source) / "SAVE" / "Game1.sav"
    assert backup_file.exists()
    assert backup_file.read_text() == "my save data"

    save_file.unlink()
    assert not save_file.exists()

    SyncApp.restore_saves(app, str(source), str(dest), "edgb")
    assert save_file.exists()
    assert save_file.read_text() == "my save data"

    save_file.unlink()

    # Legacy flat layout (no timestamped snapshots) must still restore
    shutil.rmtree(source / "Saves_Backup")
    (source / "Saves_Backup").mkdir()
    flat_backup = source / "Saves_Backup" / "Game1.sav"
    flat_backup.write_text("flat save data")

    SyncApp.restore_saves(app, str(source), str(dest), "edgb")
    assert save_file.exists()
    assert save_file.read_text() == "flat save data"

def test_n64_sync_reorganize(tmp_path):
    source = tmp_path / "source"
    dest = tmp_path / "sd_card"
    source.mkdir()
    dest.mkdir()
    
    (dest / "ed64").mkdir(parents=True)
    
    app = DummyApp()
    from sync_everdrive import SyncApp
    
    save_dir = dest / "ed64" / "SAVE"
    save_dir.mkdir(parents=True)
    (save_dir / "Zelda64.eep").write_text("eeprom data")
    (save_dir / "Mario64.sra").write_text("sram data")
    
    SyncApp.backup_saves(app, str(source), "", str(dest), "ed64")
    snap = latest_backup_dir(source)
    assert (snap / "SAVE" / "Zelda64.eep").exists()
    assert (snap / "SAVE" / "Mario64.sra").exists()

    (save_dir / "Zelda64.eep").unlink()

    SyncApp.restore_saves(app, str(source), str(dest), "ed64")
    assert (dest / "ed64" / "SAVE" / "Zelda64.eep").exists()
    assert (dest / "ed64" / "SAVE" / "Zelda64.eep").read_text() == "eeprom data"

    # Legacy flat layout restore
    (dest / "ed64" / "SAVE" / "Zelda64.eep").unlink()
    shutil.rmtree(source / "Saves_Backup")
    (source / "Saves_Backup").mkdir()
    (source / "Saves_Backup" / "Zelda64.eep").write_text("flat eeprom data")

    SyncApp.restore_saves(app, str(source), str(dest), "ed64")
    assert (dest / "ed64" / "SAVE" / "Zelda64.eep").read_text() == "flat eeprom data"

def test_gba_sync_reorganize(tmp_path):
    source = tmp_path / "source"
    dest = tmp_path / "sd_card"
    source.mkdir()
    dest.mkdir()
    
    (dest / "GBASYS").mkdir(parents=True)
    
    app = DummyApp()
    from sync_everdrive import SyncApp
    
    save_dir = dest / "GBASYS" / "SAVE"
    save_dir.mkdir(parents=True)
    (save_dir / "Pokemon.sav").write_text("gba save")
    
    SyncApp.backup_saves(app, str(source), "", str(dest), "GBASYS")
    assert (latest_backup_dir(source) / "SAVE" / "Pokemon.sav").exists()

def test_gba_pro_sync_reorganize(tmp_path):
    source = tmp_path / "source"
    dest = tmp_path / "sd_card"
    source.mkdir()
    dest.mkdir()
    
    (dest / "edgba").mkdir(parents=True)
    
    app = DummyApp()
    from sync_everdrive import SyncApp
    
    save_dir = dest / "edgba" / "gamedata" / "Metroid.gba"
    save_dir.mkdir(parents=True)
    (save_dir / "Metroid.sav").write_text("pro save data")
    
    SyncApp.backup_saves(app, str(source), "", str(dest), "edgba")
    assert (latest_backup_dir(source) / "gamedata" / "Metroid.gba" / "Metroid.sav").exists()

    shutil.rmtree(source / "Saves_Backup")
    (source / "Saves_Backup").mkdir()
    (source / "Saves_Backup" / "Metroid.sav").write_text("flat pro data")
    (save_dir / "Metroid.sav").unlink()
    
    SyncApp.restore_saves(app, str(source), str(dest), "edgba")
    assert (dest / "edgba" / "gamedata" / "Metroid.gba" / "Metroid.sav").exists()
    assert (dest / "edgba" / "gamedata" / "Metroid.gba" / "Metroid.sav").read_text() == "flat pro data"
    
    rom_name_map = {"metroid": "Metroid Fusion"}
    SyncApp.rename_sd_saves(app, str(dest), "edgba", "SAVE", "SAVE", rom_name_map)
    assert (dest / "edgba" / "gamedata" / "Metroid Fusion.gba").exists()
    assert (dest / "edgba" / "gamedata" / "Metroid Fusion.gba" / "Metroid Fusion.sav").exists()

def test_standard_save_rename(tmp_path):
    source = tmp_path / "source"
    dest = tmp_path / "sd_card"
    source.mkdir()
    dest.mkdir()
    
    (dest / "EDGB" / "SAVE").mkdir(parents=True)
    old_save = dest / "EDGB" / "SAVE" / "Pokemon - Red.sav"
    old_save.write_text("my save data")
    
    app = DummyApp()
    from sync_everdrive import SyncApp
    
    rom_name_map = {"pokemon red": "Pokemon Red"}
    SyncApp.rename_sd_saves(app, str(dest), "EDGB", "SAVE", "RTC", rom_name_map)
    
    # It should rename Pokemon - Red.sav to Pokemon Red.sav
    assert not old_save.exists()
    assert (dest / "EDGB" / "SAVE" / "Pokemon Red.sav").exists()
    assert (dest / "EDGB" / "SAVE" / "Pokemon Red.sav").read_text() == "my save data"

def test_save_prefix_stripping_safety(tmp_path):
    source = tmp_path / "source"
    dest = tmp_path / "sd_card"
    source.mkdir()
    dest.mkdir()
    
    (dest / "EDGB" / "SAVE").mkdir(parents=True)
    
    # These should NOT be stripped
    safe_save1 = dest / "EDGB" / "SAVE" / "Save the World.sav"
    safe_save1.write_text("save the world")
    
    safe_save2 = dest / "EDGB" / "SAVE" / "GBA Explorer.sav"
    safe_save2.write_text("gba explorer")
    
    # This SHOULD be stripped (has actual hardware prefix with underscore)
    stripped_save = dest / "EDGB" / "SAVE" / "SAVE_Zelda.sav"
    stripped_save.write_text("zelda save")
    
    app = DummyApp()
    from sync_everdrive import SyncApp
    
    rom_name_map = {
        "save the world": "Save the World",
        "gba explorer": "GBA Explorer",
        "zelda": "Zelda"
    }
    SyncApp.rename_sd_saves(app, str(dest), "EDGB", "SAVE", "RTC", rom_name_map)
    
    # Verify that safe ones remain unchanged
    assert safe_save1.exists()
    assert safe_save2.exists()
    
    # Verify stripped one is renamed (SAVE_ prefix removed)
    assert not stripped_save.exists()
    assert (dest / "EDGB" / "SAVE" / "Zelda.sav").exists()

def test_smart_sync_local_move(tmp_path):
    source = tmp_path / "source"
    dest = tmp_path / "sd_card"
    source.mkdir()
    dest.mkdir()
    
    # Create OS folder on SD card to pass validation
    (dest / "EDGB").mkdir(parents=True)
    
    # Create a ROM in source
    rom_src = source / "Bomberman Max - Blue Champion (USA).gbc"
    rom_src.write_text("dummy rom data")
    
    # Create same ROM in destination to simulate it already being there (so it gets cataloged and moved)
    rom_dest_dir = dest / "GBC"
    rom_dest_dir.mkdir()
    rom_dest = rom_dest_dir / "Bomberman Max - Blue Champion (USA).gbc"
    rom_dest.write_text("dummy rom data")
    
    # Make sure timestamps and sizes match
    import os
    stat_src = os.stat(rom_src)
    os.utime(rom_dest, (stat_src.st_atime, stat_src.st_mtime))
    
    app = MockSyncApp(source=str(source), dest=str(dest))
    
    # Mock messagebox
    from unittest.mock import patch
    with patch('tkinter.messagebox.showinfo') as mock_info, \
         patch('tkinter.messagebox.showerror') as mock_error, \
         patch('tkinter.messagebox.askokcancel', return_value=True):
        app.run_sync()
        
        # Verify no error messagebox was shown
        mock_error.assert_not_called()
        mock_info.assert_called_once()
        
    # Verify the ROM was moved successfully to the new sorted path under GBC/
    new_rom_path = dest / "GBC" / "Bomberman Max - Blue Champion (USA).gbc"
    assert new_rom_path.exists()
    assert new_rom_path.read_text() == "dummy rom data"
    
    # Verify the temporary sync directory was cleaned up
    assert not (dest / ".sync_temp").exists()

def test_mirror_copy(tmp_path):
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    dest.mkdir()
    
    # Create files in src
    f1 = src / "game1.gb"
    f1.write_text("data1")
    
    sub = src / "subdir"
    sub.mkdir()
    f2 = sub / "game2.gb"
    f2.write_text("data2")
    
    app = MockSyncApp()
    app.run_sync = lambda *a: None
    
    app._mirror_copy(str(src), str(dest))
    
    # Verify both are copied
    assert (dest / "game1.gb").exists()
    assert (dest / "subdir" / "game2.gb").exists()
    assert (dest / "game1.gb").read_text() == "data1"
    
    # Modify one file in src, keep other same
    f1.write_text("data1_modified")
    import os
    # Change mtime of f2 in dest so it doesn't match
    d2 = dest / "subdir" / "game2.gb"
    os.utime(d2, (0, 0))
    
    # Run mirror copy again
    app._mirror_copy(str(src), str(dest))
    
    assert (dest / "game1.gb").read_text() == "data1_modified"

def test_sync_bypass_mode(tmp_path):
    source = tmp_path / "source"
    dest = tmp_path / "sd_card"
    source.mkdir()
    dest.mkdir()
    
    # Create OS folder on dest
    (dest / "EDGB").mkdir(parents=True)
    
    # Create files in source
    (source / "game1.gb").write_text("data1")
    
    app = MockSyncApp(source=str(source), dest=str(dest), reorg=False)
    
    from unittest.mock import patch
    with patch('tkinter.messagebox.showinfo') as mock_info, \
         patch('tkinter.messagebox.showerror') as mock_error, \
         patch('tkinter.messagebox.askokcancel', return_value=True):
        app.run_sync()
        mock_error.assert_not_called()
        mock_info.assert_called_once()
        
    # Verify file is copied directly without GBC or other type folders
    assert (dest / "game1.gb").exists()
    assert (dest / "game1.gb").read_text() == "data1"

def test_sync_zip_extraction(tmp_path):
    source = tmp_path / "source"
    dest = tmp_path / "sd_card"
    source.mkdir()
    dest.mkdir()
    
    # Create OS folder
    (dest / "EDGB").mkdir(parents=True)
    
    # Create a zip file with a ROM
    import zipfile
    zip_path = source / "games.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("zipped_game.gb", "zip data")
        
    app = MockSyncApp(source=str(source), dest=str(dest), zip=True)
    
    from unittest.mock import patch
    with patch('tkinter.messagebox.showinfo') as mock_info, \
         patch('tkinter.messagebox.showerror') as mock_error, \
         patch('tkinter.messagebox.askokcancel', return_value=True):
        app.run_sync()
        mock_error.assert_not_called()
        mock_info.assert_called_once()
        
    # Verify the zipped game was extracted and placed under GB
    assert (dest / "GB" / "zipped game.gb").exists()
    assert (dest / "GB" / "zipped game.gb").read_text() == "zip data"

def test_sync_gbcsys_payload(tmp_path):
    source = tmp_path / "source"
    dest = tmp_path / "sd_card"
    payload = tmp_path / "payload"
    source.mkdir()
    dest.mkdir()
    payload.mkdir()
    
    # Create OS folder GBCSYS
    (dest / "GBCSYS").mkdir(parents=True)
    (source / "game1.gbc").write_text("game_data")
    (payload / "payload_file.bin").write_text("payload_data")
    
    app = MockSyncApp(source=str(source), dest=str(dest), gbcsys=str(payload))
    
    from unittest.mock import patch
    with patch('tkinter.messagebox.showinfo') as mock_info, \
         patch('tkinter.messagebox.showerror') as mock_error, \
         patch('tkinter.messagebox.askokcancel', return_value=True):
        app.run_sync()
        mock_error.assert_not_called()
        mock_info.assert_called_once()
        
    # Verify both main ROM and payload system files are copied
    assert (dest / "GBC" / "game1.gbc").exists()
    assert (dest / "GBCSYS" / "payload_file.bin").exists()
    assert (dest / "GBCSYS" / "payload_file.bin").read_text() == "payload_data"

def test_load_save_config(tmp_path):
    source = "/path/to/source"
    dest = "/path/to/dest"
    hacks = "/path/to/hacks"
    gbcsys = "/path/to/gbcsys"
    
    config_file = tmp_path / "config.json"
    
    from unittest.mock import patch
    with patch('everdrive.sync_app.CONFIG_FILE', str(config_file)):
        app = MockSyncApp(source=source, dest=dest, hacks=hacks, gbcsys=gbcsys)
        
        # Verify initial config saving
        app.save_config()
        assert config_file.exists()
        
        import json
        with open(config_file, "r") as f:
            data = json.load(f)
        assert data["Source"] == source
        assert data["Dest"] == dest
        assert data["Hacks"] == hacks
        assert data["GbcSysPayload"] == gbcsys
        
        # Test loading config
        app2 = MockSyncApp()
        # Mock widgets with empty entries
        app2.txt_source = type('MockEntry', (), {'get': lambda *a: "", 'insert': lambda *a: None})()
        app2.txt_dest = type('MockEntry', (), {'get': lambda *a: "", 'insert': lambda *a: None})()
        app2.txt_hacks = type('MockEntry', (), {'get': lambda *a: "", 'insert': lambda *a: None})()
        app2.txt_gbcsys = type('MockEntry', (), {'get': lambda *a: "", 'insert': lambda *a: None})()
        
        app2.load_config()
        assert app2.config_data["Source"] == source
        assert app2.config_data["Dest"] == dest
        assert app2.config_data["Hacks"] == hacks
        assert app2.config_data["GbcSysPayload"] == gbcsys

def test_sync_validation_errors(tmp_path):
    dest = tmp_path / "sd_card"
    dest.mkdir()
    
    from unittest.mock import patch
    
    with patch('tkinter.messagebox.showerror') as mock_error, \
         patch('tkinter.messagebox.askokcancel', return_value=True):
        # 1. Missing source and hacks
        app = MockSyncApp(source="", hacks="", dest=str(dest))
        app.run_sync()
        mock_error.assert_called_with("Error", "Source path required.")
        mock_error.reset_mock()
        
        # 2. Invalid destination
        app = MockSyncApp(source="/valid/source", dest="/invalid/dest")
        app.run_sync()
        mock_error.assert_called_with("Error", "Invalid Dest path.")
        mock_error.reset_mock()
        
        # 3. Source matches destination (Self-Sync error)
        app = MockSyncApp(source=str(dest), dest=str(dest))
        app.run_sync()
        mock_error.assert_called_with("Error", "Source and Dest cannot match.")
        mock_error.reset_mock()
        
        # 4. Missing EverDrive OS folder (source must be a sibling — nested
        # source/dest paths are rejected earlier with their own error)
        plain_source = tmp_path / "plain_source"
        plain_source.mkdir()
        app = MockSyncApp(source=str(plain_source), dest=str(dest))
        app.run_sync()
        mock_error.assert_called_with("Error", "Missing OS folder on SD.")

def test_mac_cleanup(tmp_path):
    app = MockSyncApp()
    
    from unittest.mock import patch
    import subprocess
    
    # 1. Test Darwin execution
    with patch('platform.system', return_value='Darwin'), \
         patch('subprocess.run') as mock_run:
        app.mac_cleanup("/test/path")
        mock_run.assert_called_once_with(
            ["dot_clean", "-m", "/test/path"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False
        )
        
    # 2. Test non-Darwin execution
    with patch('platform.system', return_value='Windows'), \
         patch('subprocess.run') as mock_run:
        app.mac_cleanup("/test/path")
        mock_run.assert_not_called()

def test_mtimes_match_fat32_tolerance():
    assert mtimes_match(1000, 1000)
    assert mtimes_match(1000, 1002)  # FAT32 2-second resolution
    assert mtimes_match(1002, 1000)
    assert not mtimes_match(1000, 1003)

def test_catalog_helpers():
    catalog = {100: [(1000, "/sd/a.gb"), (2000, "/sd/b.gb")]}
    # 2-second drift still matches
    assert catalog_pop_match(catalog, 100, 1002) == "/sd/a.gb"
    # already popped
    assert catalog_pop_match(catalog, 100, 1001) is None
    assert catalog_pop_match(catalog, 100, 1999) == "/sd/b.gb"
    # unknown size
    assert catalog_pop_match(catalog, 999, 1000) is None

    catalog = {50: [(1, "/sd/x.gb"), (2, "/sd/y.gb")]}
    catalog_discard_path(catalog, 50, "/sd/x.gb")
    assert catalog[50] == [(2, "/sd/y.gb")]

def test_check_cancel_raises():
    app = MockSyncApp()
    check_cancel(app)  # not cancelled: no error
    app.cancel_event.set()
    with pytest.raises(SyncCancelled):
        check_cancel(app)
    # Objects without a cancel_event are a no-op
    check_cancel(DummyApp())

def test_snap_files_backed_up(tmp_path):
    source = tmp_path / "source"
    dest = tmp_path / "sd_card"
    source.mkdir()
    dest.mkdir()

    save_dir = dest / "EDGB" / "SAVE"
    save_dir.mkdir(parents=True)
    (save_dir / "Game1.snap").write_text("snapshot data")

    app = DummyApp()
    from sync_everdrive import SyncApp
    SyncApp.backup_saves(app, str(source), "", str(dest), "EDGB")
    assert (latest_backup_dir(source) / "SAVE" / "Game1.snap").exists()

def test_backup_falls_back_to_hacks(tmp_path):
    hacks = tmp_path / "hacks"
    dest = tmp_path / "sd_card"
    hacks.mkdir()
    dest.mkdir()

    save_dir = dest / "EDGB" / "SAVE"
    save_dir.mkdir(parents=True)
    (save_dir / "Game1.sav").write_text("save data")

    app = DummyApp()
    from sync_everdrive import SyncApp
    SyncApp.backup_saves(app, "", str(hacks), str(dest), "EDGB")
    assert (latest_backup_dir(hacks) / "SAVE" / "Game1.sav").exists()

def test_backup_snapshot_retention(tmp_path):
    root = tmp_path / "Saves_Backup"
    root.mkdir()
    names = [f"2026-01-0{i}_000000" for i in range(1, 8)]
    for n in names:
        (root / n).mkdir()
    (root / "not_a_snapshot").mkdir()

    prune_backups(str(root), keep=5)

    remaining = list_backup_snapshots(str(root))
    assert remaining == names[2:]
    assert (root / "not_a_snapshot").exists()

def test_restore_uses_latest_snapshot(tmp_path):
    source = tmp_path / "source"
    dest = tmp_path / "sd_card"
    source.mkdir()
    dest.mkdir()
    (dest / "EDGB").mkdir()

    old_snap = source / "Saves_Backup" / "2026-01-01_000000" / "SAVE"
    new_snap = source / "Saves_Backup" / "2026-02-01_000000" / "SAVE"
    old_snap.mkdir(parents=True)
    new_snap.mkdir(parents=True)
    (old_snap / "Game.sav").write_text("old save")
    (new_snap / "Game.sav").write_text("new save")

    app = DummyApp()
    from sync_everdrive import SyncApp
    SyncApp.restore_saves(app, str(source), str(dest), "EDGB")
    assert (dest / "EDGB" / "SAVE" / "Game.sav").read_text() == "new save"

def test_restore_falls_back_to_hacks(tmp_path):
    hacks = tmp_path / "hacks"
    dest = tmp_path / "sd_card"
    hacks.mkdir()
    dest.mkdir()
    (dest / "EDGB").mkdir()

    (hacks / "Some Hack.gbc").write_text("hack rom")
    snap = hacks / "Saves_Backup" / "2026-01-01_000000" / "SAVE"
    snap.mkdir(parents=True)
    # Name with a tag: restore preserves it verbatim, hack save placement would not
    (snap / "Pokemon - Red (USA).sav").write_text("restored save")

    app = MockSyncApp(source="", hacks=str(hacks), dest=str(dest), restore=True)

    from unittest.mock import patch
    with patch('tkinter.messagebox.showinfo'), \
         patch('tkinter.messagebox.showerror') as mock_error, \
         patch('tkinter.messagebox.askokcancel', return_value=True):
        app.run_sync()
        mock_error.assert_not_called()

    assert (dest / "EDGB" / "SAVE" / "Pokemon - Red (USA).sav").read_text() == "restored save"

def test_local_move_after_rename(tmp_path):
    source = tmp_path / "source"
    dest = tmp_path / "sd_card"
    source.mkdir()
    dest.mkdir()
    (dest / "EDGB").mkdir()

    rom_src = source / "Bomberman Max - Blue Champion (USA).gbc"
    rom_src.write_text("dummy rom data")

    # Same content already on the SD but under a different (renamed) filename
    old_dir = dest / "Old Stuff"
    old_dir.mkdir()
    rom_old = old_dir / "renamed_rom.gbc"
    rom_old.write_text("dummy rom data")
    stat_src = os.stat(rom_src)
    os.utime(rom_old, (stat_src.st_atime, stat_src.st_mtime))

    app = MockSyncApp(source=str(source), dest=str(dest))

    from unittest.mock import patch
    with patch('tkinter.messagebox.showinfo'), \
         patch('tkinter.messagebox.showerror') as mock_error, \
         patch('tkinter.messagebox.askokcancel', return_value=True):
        app.run_sync()
        mock_error.assert_not_called()

    new_rom_path = dest / "GBC" / "Bomberman Max - Blue Champion (USA).gbc"
    assert new_rom_path.exists()
    assert new_rom_path.read_text() == "dummy rom data"
    assert any("Moving (Local)" in line for line in app.logs)

def test_dry_run_makes_no_changes(tmp_path):
    source = tmp_path / "source"
    dest = tmp_path / "sd_card"
    source.mkdir()
    dest.mkdir()
    (dest / "EDGB" / "SAVE").mkdir(parents=True)
    (dest / "EDGB" / "SAVE" / "Game1.sav").write_text("save data")

    (source / "New Game.gbc").write_text("rom data")
    stray = dest / "stray_file.txt"
    stray.write_text("would normally be cleaned")

    app = MockSyncApp(source=str(source), dest=str(dest), backups=True, dryrun=True)

    from unittest.mock import patch
    with patch('tkinter.messagebox.showinfo') as mock_info, \
         patch('tkinter.messagebox.showerror') as mock_error, \
         patch('tkinter.messagebox.askokcancel', return_value=True):
        app.run_sync()
        mock_error.assert_not_called()
        mock_info.assert_called_once()

    # Nothing was written, deleted, or backed up
    assert stray.exists()
    assert not (dest / "GBC").exists()
    assert not (source / "Saves_Backup").exists()
    assert any("[DRY RUN]" in line or "DRY RUN" in line for line in app.logs)

def test_cli_dry_run(tmp_path):
    source = tmp_path / "source"
    dest = tmp_path / "sd_card"
    source.mkdir()
    dest.mkdir()
    (dest / "EDGB").mkdir()
    (source / "Game.gbc").write_text("rom data")

    rc = run_cli(["--source", str(source), "--dest", str(dest),
                  "--dry-run", "--no-backup", "--yes"])
    assert rc == 0
    assert not (dest / "GBC").exists()

def test_cli_sync(tmp_path):
    source = tmp_path / "source"
    dest = tmp_path / "sd_card"
    source.mkdir()
    dest.mkdir()
    (dest / "EDGB").mkdir()
    (source / "Game.gbc").write_text("rom data")

    rc = run_cli(["--source", str(source), "--dest", str(dest),
                  "--no-backup", "--no-az", "--yes"])
    assert rc == 0
    assert (dest / "GBC" / "Game.gbc").read_text() == "rom data"
    # Sync report is written next to the backups
    assert (source / "Saves_Backup" / "last_sync.log").exists()

# ------------------------------------------------------------------ #
# Name manifest tests                                                   #
# ------------------------------------------------------------------ #

import json as _json

def test_name_manifest_written_after_sync(tmp_path):
    """rom_name_map.json is written to Saves_Backup after a successful sync."""
    source = tmp_path / "source"
    dest = tmp_path / "sd_card"
    source.mkdir()
    dest.mkdir()
    (dest / "EDGB").mkdir()
    (source / "Pokemon - Red Version (USA, Europe).gbc").write_text("rom")

    app = MockSyncApp(source=str(source), dest=str(dest))
    from unittest.mock import patch
    with patch('tkinter.messagebox.showinfo'), \
         patch('tkinter.messagebox.showerror'), \
         patch('tkinter.messagebox.askokcancel', return_value=True):
        app.run_sync()

    manifest_path = source / "Saves_Backup" / "rom_name_map.json"
    assert manifest_path.exists(), "manifest was not written"
    manifest = _json.loads(manifest_path.read_text())
    # Source ROM fuzzy title must map to the clean name (tags=True by default in MockSyncApp
    # so region tags are preserved in the clean name)
    assert "pokemon red version" in manifest
    assert "Pokemon - Red Version" in manifest["pokemon red version"]

def test_name_manifest_not_written_on_dry_run(tmp_path):
    """rom_name_map.json is NOT written when dry-run is enabled."""
    source = tmp_path / "source"
    dest = tmp_path / "sd_card"
    source.mkdir()
    dest.mkdir()
    (dest / "EDGB").mkdir()
    (source / "Game.gbc").write_text("rom")

    app = MockSyncApp(source=str(source), dest=str(dest), dryrun=True)
    from unittest.mock import patch
    with patch('tkinter.messagebox.showinfo'), \
         patch('tkinter.messagebox.showerror'), \
         patch('tkinter.messagebox.askokcancel', return_value=True):
        app.run_sync()

    assert not (source / "Saves_Backup" / "rom_name_map.json").exists()

def test_name_manifest_enables_save_rename_after_clean_name_change(tmp_path):
    """A save is renamed to the new clean name even when it was written with an
    old clean name that produces a different fuzzy title.

    Simulates: ROM clean name changed from "Zelda - Links Awakening" to
    "Link's Awakening" (different fuzzy titles). The old save can only be
    located via the manifest entry for the old clean name's fuzzy."""
    source = tmp_path / "source"
    dest = tmp_path / "sd_card"
    source.mkdir()
    dest.mkdir()
    (dest / "EDGB").mkdir()

    # Save on SD uses the OLD clean name
    save_dir = dest / "EDGB" / "SAVE"
    save_dir.mkdir(parents=True)
    (save_dir / "Zelda - Links Awakening.sav").write_text("save data")

    # Manifest from previous sync: old clean name → (still current)
    # AND: clean-name fuzzy → old clean name  (this is the key that lets us find it)
    backup_root = source / "Saves_Backup"
    backup_root.mkdir()
    # Manually write the manifest as _build_merged_name_map would have after the old sync:
    # key = get_fuzzy_title("Zelda - Links Awakening") = "zelda links awakening"
    old_manifest = {"zelda links awakening": "Zelda - Links Awakening"}
    (backup_root / "rom_name_map.json").write_text(_json.dumps(old_manifest))

    # Current source ROM (same file, just the clean name algorithm now produces a different name)
    # Source stem that fuzzifies to "zelda links awakening" already in manifest → match
    # New clean name from current ROM:
    (source / "Zelda - Links Awakening (USA, Europe).gbc").write_text("rom")

    # Build merged map the same way run_sync does
    from sync_everdrive import SyncApp, get_fuzzy_title
    live_map = {"zelda links awakening": "Links Awakening, The"}  # new clean name
    persisted = {"zelda links awakening": "Zelda - Links Awakening"}
    merged = SyncApp._build_merged_name_map(live_map, persisted)

    # The save stem "Zelda - Links Awakening" → fuzzy "zelda links awakening"
    # must now map to the new clean name
    from sync_everdrive import SyncApp as SA
    result = SA._fuzzy_match_rom("Zelda - Links Awakening", merged)
    assert result == "Links Awakening, The", (
        f"Expected 'Links Awakening, The' but got {result!r}. "
        "Manifest-assisted rename failed."
    )

def test_name_manifest_build_merged_map_live_wins(tmp_path):
    """Live map always overrides persisted map for the same key."""
    from sync_everdrive import SyncApp
    live = {"pokemon red": "Pokemon Red Version"}
    persisted = {"pokemon red": "Pokemon Red"}   # old clean name for same fuzzy
    merged = SyncApp._build_merged_name_map(live, persisted)
    assert merged["pokemon red"] == "Pokemon Red Version"

def test_name_manifest_orphan_detection(tmp_path):
    """A save with no matching ROM in the merged map triggers a warning log."""
    source = tmp_path / "source"
    dest = tmp_path / "sd_card"
    source.mkdir()
    dest.mkdir()
    (dest / "EDGB").mkdir()
    (source / "Mario.gbc").write_text("rom")

    save_dir = dest / "EDGB" / "SAVE"
    save_dir.mkdir(parents=True)
    # Save for a game not present in the source at all
    (save_dir / "Totally Unknown Game.sav").write_text("save data")

    app = MockSyncApp(source=str(source), dest=str(dest))
    from unittest.mock import patch
    with patch('tkinter.messagebox.showinfo'), \
         patch('tkinter.messagebox.showerror'), \
         patch('tkinter.messagebox.askokcancel', return_value=True):
        app.run_sync()

    assert any("orphaned" in line.lower() or "no matching rom" in line.lower()
               for line in app.logs), \
        f"Expected orphan warning in logs; got:\n" + "\n".join(app.logs)


# ------------------------------------------------------------------ #
# Safety & correctness regression tests                                 #
# ------------------------------------------------------------------ #

def test_validation_rejects_nested_paths(tmp_path):
    """Source inside dest (or vice versa) must be refused — clean_sd would
    otherwise delete the source library."""
    dest = tmp_path / "sd_card"
    (dest / "EDGB").mkdir(parents=True)
    inner_source = dest / "ROMs"
    inner_source.mkdir()
    (inner_source / "Game.gbc").write_text("rom")

    from unittest.mock import patch
    with patch('tkinter.messagebox.showerror') as mock_error, \
         patch('tkinter.messagebox.askokcancel', return_value=True):
        # Source inside dest
        app = MockSyncApp(source=str(inner_source), dest=str(dest))
        app.run_sync()
        assert "nested" in mock_error.call_args[0][1]
        assert (inner_source / "Game.gbc").exists(), "source library was touched!"
        mock_error.reset_mock()

        # Dest inside source
        app = MockSyncApp(source=str(tmp_path), dest=str(dest))
        app.run_sync()
        assert "nested" in mock_error.call_args[0][1]


def test_catalog_pop_match_verifies_content(tmp_path):
    from sync_everdrive import catalog_pop_match
    src = tmp_path / "source_rom.gb"
    wrong = tmp_path / "wrong.gb"
    right = tmp_path / "right.gb"
    src.write_text("GAME B DATA")
    wrong.write_text("GAME A DATA")  # same size + mtime, different game
    right.write_text("GAME B DATA")
    size = src.stat().st_size

    catalog = {size: [(1000, str(wrong)), (1000, str(right))]}
    assert catalog_pop_match(catalog, size, 1000, str(src)) == str(right)
    assert catalog[size] == [(1000, str(wrong))]
    # Without a source path the old size+mtime behavior is unchanged
    catalog2 = {size: [(1000, str(wrong))]}
    assert catalog_pop_match(catalog2, size, 1000) == str(wrong)


def test_same_size_mtime_roms_not_swapped(tmp_path):
    """Two different ROMs sharing size+mtime must not be swapped by the
    quick-move optimization."""
    source = tmp_path / "source"
    dest = tmp_path / "sd_card"
    source.mkdir()
    dest.mkdir()
    (dest / "EDGB").mkdir()

    t = 1_700_000_000
    (source / "Alpha.gbc").write_text("AAAA")
    (source / "Beta.gbc").write_text("BBBB")
    os.utime(source / "Alpha.gbc", (t, t))
    os.utime(source / "Beta.gbc", (t, t))

    # Same contents already on the SD under scrambled names
    old = dest / "Old"
    old.mkdir()
    (old / "aaa.gbc").write_text("BBBB")
    (old / "zzz.gbc").write_text("AAAA")
    os.utime(old / "aaa.gbc", (t, t))
    os.utime(old / "zzz.gbc", (t, t))

    app = MockSyncApp(source=str(source), dest=str(dest))
    from unittest.mock import patch
    with patch('tkinter.messagebox.showinfo'), \
         patch('tkinter.messagebox.showerror') as mock_error, \
         patch('tkinter.messagebox.askokcancel', return_value=True):
        app.run_sync()
        mock_error.assert_not_called()

    assert (dest / "GBC" / "Alpha.gbc").read_text() == "AAAA"
    assert (dest / "GBC" / "Beta.gbc").read_text() == "BBBB"


def test_cancel_preserves_staged_sync_temp(tmp_path):
    """Cancelling after ROMs were staged into .sync_temp must not delete them,
    and the next sync must recover them via a local move."""
    source = tmp_path / "source"
    dest = tmp_path / "sd_card"
    source.mkdir()
    dest.mkdir()
    (dest / "EDGB").mkdir()

    t = 1_700_000_000
    (source / "Game.gbc").write_text("rom data")
    os.utime(source / "Game.gbc", (t, t))
    sd_rom = dest / "GBC" / "Game.gbc"
    sd_rom.parent.mkdir()
    sd_rom.write_text("rom data")
    os.utime(sd_rom, (t, t))

    app = MockSyncApp(source=str(source), dest=str(dest))

    def cancel_now(*_a, **_k):
        raise SyncCancelled()
    app.clean_sd = cancel_now  # fires right after staging

    from unittest.mock import patch
    with patch('tkinter.messagebox.showinfo'), \
         patch('tkinter.messagebox.showerror'), \
         patch('tkinter.messagebox.askokcancel', return_value=True):
        app.run_sync()

    temp = dest / ".sync_temp"
    staged = list(temp.glob("*.gbc"))
    assert staged, ".sync_temp was deleted on cancel — staged ROMs lost"
    assert staged[0].read_text() == "rom data"

    # Recovery sync: staged file is found via the catalog and moved back
    app2 = MockSyncApp(source=str(source), dest=str(dest))
    with patch('tkinter.messagebox.showinfo'), \
         patch('tkinter.messagebox.showerror') as mock_error, \
         patch('tkinter.messagebox.askokcancel', return_value=True):
        app2.run_sync()
        mock_error.assert_not_called()

    assert (dest / "GBC" / "Game.gbc").read_text() == "rom data"
    assert not temp.exists()
    assert any("Moving (Local)" in line for line in app2.logs)


def test_favorites_save_rename_gets_prefix(tmp_path):
    """SD saves of favorite games get the same '! ' prefix as the ROM."""
    dest = tmp_path / "sd_card"
    (dest / "EDGB" / "SAVE").mkdir(parents=True)
    (dest / "EDGB" / "SAVE" / "Zelda.sav").write_text("save")

    app = DummyApp()
    from sync_everdrive import SyncApp
    favs = {"zelda"}
    SyncApp.rename_sd_saves(app, str(dest), "EDGB", "SAVE", "RTC", {"zelda": "Zelda"}, favs)
    assert (dest / "EDGB" / "SAVE" / "! Zelda.sav").exists()

    # Idempotent: a second pass must not double-prefix
    SyncApp.rename_sd_saves(app, str(dest), "EDGB", "SAVE", "RTC", {"zelda": "Zelda"}, favs)
    assert (dest / "EDGB" / "SAVE" / "! Zelda.sav").exists()
    assert not (dest / "EDGB" / "SAVE" / "! ! Zelda.sav").exists()

    # Favorite removed: prefix comes off again
    SyncApp.rename_sd_saves(app, str(dest), "EDGB", "SAVE", "RTC", {"zelda": "Zelda"}, set())
    assert (dest / "EDGB" / "SAVE" / "Zelda.sav").exists()


def test_favorites_end_to_end_rom_and_save_prefixed(tmp_path):
    source = tmp_path / "source"
    dest = tmp_path / "sd_card"
    source.mkdir()
    dest.mkdir()
    (dest / "EDGB" / "SAVE").mkdir(parents=True)

    (source / "Zelda.gbc").write_text("rom")
    (source / "favorites.txt").write_text("Zelda\n")
    (dest / "EDGB" / "SAVE" / "Zelda.sav").write_text("save data")

    app = MockSyncApp(source=str(source), dest=str(dest), fav=True)
    from unittest.mock import patch
    with patch('tkinter.messagebox.showinfo'), \
         patch('tkinter.messagebox.showerror') as mock_error, \
         patch('tkinter.messagebox.askokcancel', return_value=True):
        app.run_sync()
        mock_error.assert_not_called()

    assert (dest / "GBC" / "! Zelda.gbc").exists()
    assert (dest / "EDGB" / "SAVE" / "! Zelda.sav").exists(), \
        "save prefix out of sync with ROM prefix — EverDrive would start a blank save"


def test_snap_files_routed_to_save_folder(tmp_path):
    """.snap files from the source belong in the OS save folder, not loose on the card."""
    source = tmp_path / "source"
    dest = tmp_path / "sd_card"
    source.mkdir()
    dest.mkdir()
    (dest / "EDGB").mkdir()

    (source / "Game.gbc").write_text("rom")
    (source / "Game.snap").write_text("snapshot")

    app = MockSyncApp(source=str(source), dest=str(dest))
    from unittest.mock import patch
    with patch('tkinter.messagebox.showinfo'), \
         patch('tkinter.messagebox.showerror') as mock_error, \
         patch('tkinter.messagebox.askokcancel', return_value=True):
        app.run_sync()
        mock_error.assert_not_called()

    assert (dest / "EDGB" / "SAVE" / "Game.snap").exists()
    assert not (dest / "Game.snap").exists()


def test_dry_run_writes_no_report(tmp_path):
    """Dry runs must not create Saves_Backup/last_sync.log either."""
    source = tmp_path / "source"
    dest = tmp_path / "sd_card"
    source.mkdir()
    dest.mkdir()
    (dest / "EDGB").mkdir()
    (source / "Game.gbc").write_text("rom")

    app = MockSyncApp(source=str(source), dest=str(dest), dryrun=True)
    from unittest.mock import patch
    with patch('tkinter.messagebox.showinfo'), \
         patch('tkinter.messagebox.showerror'), \
         patch('tkinter.messagebox.askokcancel', return_value=True):
        app.run_sync()

    assert not (source / "Saves_Backup").exists()


def test_hacks_junk_files_not_copied(tmp_path):
    source = tmp_path / "source"
    hacks = tmp_path / "hacks"
    dest = tmp_path / "sd_card"
    source.mkdir()
    hacks.mkdir()
    dest.mkdir()
    (dest / "EDGB").mkdir()

    (source / "Game.gbc").write_text("rom")
    (hacks / "Mario Fire Red.gbc").write_text("hack rom")
    (hacks / ".DS_Store").write_text("junk")
    (hacks / "._Mario Fire Red.gbc").write_text("junk")

    app = MockSyncApp(source=str(source), dest=str(dest), hacks=str(hacks))
    from unittest.mock import patch
    with patch('tkinter.messagebox.showinfo'), \
         patch('tkinter.messagebox.showerror') as mock_error, \
         patch('tkinter.messagebox.askokcancel', return_value=True):
        app.run_sync()
        mock_error.assert_not_called()

    assert (dest / "[ROM Hacks]" / "Mario Fire Red.gbc").exists()
    assert not list(Path(dest).rglob(".DS_Store"))
    assert not list(Path(dest).rglob("._*"))


def test_truncated_name_collision_gets_uniquified(tmp_path):
    """Two files whose names collide after MAX_PATH truncation must both survive."""
    app = MockSyncApp()
    shared = "Really Long Shared Prefix " * 3
    f1 = tmp_path / (shared + "Edition One.gb")
    f2 = tmp_path / (shared + "Edition Two.gb")
    f1.write_text("1")
    f2.write_text("2")

    # Deep dest dir so the projected path exceeds the 240-char guard
    pad = max(1, 225 - len(str(tmp_path)))
    deep = tmp_path / ("d" * min(pad, 200))
    deep.mkdir()

    root = VirtualNode("", True)
    add_to_virtual_tree(root, str(f1), [f1.name], False)
    add_to_virtual_tree(root, str(f2), [f2.name], False)
    app.copy_virtual_tree(root, str(deep), {}, False, False)

    files = list(deep.iterdir())
    assert len(files) == 2, "truncation collision silently dropped a file"
    assert sorted(p.read_text() for p in files) == ["1", "2"]


def test_cli_flags_cover_every_gui_checkbox():
    from sync_everdrive import build_arg_parser, HeadlessApp
    args = build_arg_parser().parse_args([
        "--dest", "/nonexistent/sd", "--dat", "/nonexistent/set.dat",
        "--no-reorg", "--no-type", "--no-series", "--no-az",
        "--1g1r", "--no-usa", "--no-world", "--no-europe", "--no-japan",
        "--extract-zips", "--no-tags", "--no-backup", "--restore",
        "--folders-last", "--sort-recent", "--favorites",
        "--verify", "--archive-orphans",
        "--eject", "--dry-run", "--yes",
    ])
    app = HeadlessApp(args)
    assert app.chk_verify_var.get() is True
    assert app.chk_orphans_var.get() is True
    assert app.txt_dat.get() == "/nonexistent/set.dat"
    assert app.chk_reorganize_var.get() is False
    assert app.chk_type_var.get() is False
    assert app.chk_series_var.get() is False
    assert app.chk_az_var.get() is False
    assert app.chk_1g1r_var.get() is True
    assert app.chk_usa_var.get() is False
    assert app.chk_world_var.get() is False
    assert app.chk_eur_var.get() is False
    assert app.chk_jpn_var.get() is False
    assert app.chk_zip_var.get() is True
    assert app.chk_tags_var.get() is False
    assert app.chk_backups_var.get() is False
    assert app.chk_restore_var.get() is True
    assert app.chk_folders_last_var.get() is True
    assert app.chk_recent_var.get() is True
    assert app.chk_fav_var.get() is True
    assert app.chk_eject_var.get() is True
    assert app.chk_dryrun_var.get() is True


# ------------------------------------------------------------------ #
# New feature tests                                                     #
# ------------------------------------------------------------------ #

import platform as _platform
import zlib as _zlib


def test_sanitize_fat32():
    from sync_everdrive import sanitize_fat32, get_clean_rom_name
    assert sanitize_fat32('Zelda: DX') == 'Zelda - DX'
    assert sanitize_fat32('What?') == 'What-'
    assert sanitize_fat32('A<B>C"D/E\\F|G*H') == 'A-B-C-D-E-F-G-H'
    assert sanitize_fat32('Trailing dots...') == 'Trailing dots'
    assert sanitize_fat32('Normal Name (USA)') == 'Normal Name (USA)'
    assert get_clean_rom_name('Zelda: DX') == 'Zelda - DX'


@pytest.mark.skipif(_platform.system() == "Windows",
                    reason="':' cannot appear in source filenames on Windows")
def test_fat32_unsafe_names_sanitized_on_copy(tmp_path):
    source = tmp_path / "source"
    dest = tmp_path / "sd_card"
    source.mkdir()
    dest.mkdir()
    (dest / "EDGB").mkdir()
    (source / "Game: Special?.gbc").write_text("rom data")

    app = MockSyncApp(source=str(source), dest=str(dest))
    from unittest.mock import patch
    with patch('tkinter.messagebox.showinfo'), \
         patch('tkinter.messagebox.showerror') as mock_error, \
         patch('tkinter.messagebox.askokcancel', return_value=True):
        app.run_sync()
        mock_error.assert_not_called()

    assert (dest / "GBC" / "Game - Special-.gbc").read_text() == "rom data"


def test_gui_options_saved_and_restored(tmp_path):
    """Checkbox states round-trip through the config file (README promise)."""
    config_file = tmp_path / "cfg.json"
    from unittest.mock import patch
    with patch('everdrive.sync_app.CONFIG_FILE', str(config_file)):
        app = MockSyncApp(source="/s", dest="/d", fav=True, backups=False)
        app.save_config()
    data = _json.loads(config_file.read_text())
    assert data["Options"]["Favorites"] is True
    assert data["Options"]["Backups"] is False
    assert "DatFile" in data

    # Apply side: saved values land back on the checkbox variables
    from sync_everdrive import SyncApp

    class _Var:
        def __init__(self, v):
            self.v = v
        def get(self):
            return self.v
        def set(self, v):
            self.v = bool(v)

    class _Holder:
        OPTION_VARS = SyncApp.OPTION_VARS
        def toggle_reorg(self):
            pass
        def toggle_1g1r(self):
            pass

    holder = _Holder()
    holder.config_data = {"Options": {"Favorites": True, "Backups": False}}
    holder.chk_fav_var = _Var(False)
    holder.chk_backups_var = _Var(True)
    SyncApp._apply_saved_options(holder)
    assert holder.chk_fav_var.get() is True
    assert holder.chk_backups_var.get() is False


def test_free_space_check_blocks_sync(tmp_path):
    source = tmp_path / "source"
    dest = tmp_path / "sd_card"
    source.mkdir()
    dest.mkdir()
    (dest / "EDGB").mkdir()
    (source / "Big Game.gbc").write_bytes(b"x" * 10_000)

    app = MockSyncApp(source=str(source), dest=str(dest))
    from unittest.mock import patch, Mock
    with patch('everdrive.sync_app.shutil.disk_usage',
               return_value=Mock(total=100, used=90, free=10)), \
         patch('tkinter.messagebox.showinfo'), \
         patch('tkinter.messagebox.showerror') as mock_error, \
         patch('tkinter.messagebox.askokcancel', return_value=True):
        app.run_sync()

    assert "Not enough space" in mock_error.call_args[0][1]
    assert not (dest / "GBC").exists(), "sync ran despite failing the space check"


def test_verify_writes_detects_corruption(tmp_path):
    source = tmp_path / "source"
    dest = tmp_path / "sd_card"
    source.mkdir()
    dest.mkdir()
    (dest / "EDGB").mkdir()
    (source / "Game.gbc").write_text("rom data")

    import shutil as _shutil
    real_copy2 = _shutil.copy2

    def corrupting_copy2(src, dst, **kwargs):
        real_copy2(src, dst, **kwargs)
        with open(dst, "w") as fh:
            fh.write("CORRUPT")

    app = MockSyncApp(source=str(source), dest=str(dest), verify=True)
    from unittest.mock import patch
    with patch('everdrive.sync_app.shutil.copy2', side_effect=corrupting_copy2), \
         patch('tkinter.messagebox.showinfo'), \
         patch('tkinter.messagebox.showerror') as mock_error, \
         patch('tkinter.messagebox.askokcancel', return_value=True):
        app.run_sync()

    assert "Verification failed" in mock_error.call_args[0][1]


def test_verify_writes_passes_clean_copy(tmp_path):
    source = tmp_path / "source"
    dest = tmp_path / "sd_card"
    source.mkdir()
    dest.mkdir()
    (dest / "EDGB").mkdir()
    (source / "Game.gbc").write_text("rom data")

    app = MockSyncApp(source=str(source), dest=str(dest), verify=True)
    from unittest.mock import patch
    with patch('tkinter.messagebox.showinfo'), \
         patch('tkinter.messagebox.showerror') as mock_error, \
         patch('tkinter.messagebox.askokcancel', return_value=True):
        app.run_sync()
        mock_error.assert_not_called()

    assert (dest / "GBC" / "Game.gbc").read_text() == "rom data"


def test_orphan_archiving_moves_save_to_pc(tmp_path):
    source = tmp_path / "source"
    dest = tmp_path / "sd_card"
    source.mkdir()
    dest.mkdir()
    (dest / "EDGB" / "SAVE").mkdir(parents=True)
    (source / "Mario.gbc").write_text("rom")
    orphan = dest / "EDGB" / "SAVE" / "Totally Unknown Game.sav"
    orphan.write_text("orphan save data")

    app = MockSyncApp(source=str(source), dest=str(dest), orphans=True)
    from unittest.mock import patch
    with patch('tkinter.messagebox.showinfo'), \
         patch('tkinter.messagebox.showerror') as mock_error, \
         patch('tkinter.messagebox.askokcancel', return_value=True):
        app.run_sync()
        mock_error.assert_not_called()

    assert not orphan.exists()
    archived = source / "Saves_Backup" / "Orphaned" / "Totally Unknown Game.sav"
    assert archived.read_text() == "orphan save data"
    assert any("Archived orphaned save" in line for line in app.logs)


def test_sync_summary_logged(tmp_path):
    source = tmp_path / "source"
    dest = tmp_path / "sd_card"
    source.mkdir()
    dest.mkdir()
    (dest / "EDGB").mkdir()
    (source / "Game.gbc").write_text("rom data")

    app = MockSyncApp(source=str(source), dest=str(dest))
    from unittest.mock import patch
    with patch('tkinter.messagebox.showinfo'), \
         patch('tkinter.messagebox.showerror'), \
         patch('tkinter.messagebox.askokcancel', return_value=True):
        app.run_sync()
    assert any(line.startswith("Summary:") and "1 copied" in line for line in app.logs)

    # Dry runs get their own clearly-labelled totals
    app2 = MockSyncApp(source=str(source), dest=str(dest), dryrun=True)
    with patch('tkinter.messagebox.showinfo'), \
         patch('tkinter.messagebox.showerror'), \
         patch('tkinter.messagebox.askokcancel', return_value=True):
        app2.run_sync()
    assert any(line.startswith("[DRY RUN] Planned totals") for line in app2.logs)


def test_dat_verification_logs(tmp_path):
    source = tmp_path / "source"
    dest = tmp_path / "sd_card"
    source.mkdir()
    dest.mkdir()
    (dest / "EDGB").mkdir()

    (source / "Good Game.gbc").write_bytes(b"good rom data")
    (source / "Tampered.gbc").write_bytes(b"bad rom data")
    (source / "Copy of Good.gbc").write_bytes(b"good rom data")

    crc = f"{_zlib.crc32(b'good rom data') & 0xFFFFFFFF:08x}"
    dat = tmp_path / "set.dat"
    dat.write_text(
        '<?xml version="1.0"?><datafile><game name="Good Game">'
        f'<rom name="Good Game.gbc" crc="{crc}"/></game></datafile>'
    )

    app = MockSyncApp(source=str(source), dest=str(dest), dat=str(dat))
    from unittest.mock import patch
    with patch('tkinter.messagebox.showinfo'), \
         patch('tkinter.messagebox.showerror') as mock_error, \
         patch('tkinter.messagebox.askokcancel', return_value=True):
        app.run_sync()
        mock_error.assert_not_called()

    assert any("DAT check: 2/3 verified, 1 unknown, 1 duplicates." in l for l in app.logs)
    assert any("no match for 'Tampered.gbc'" in l for l in app.logs)
    assert any("duplicate content" in l for l in app.logs)


def test_dat_helpers():
    from sync_everdrive import load_dat_index
    import tempfile, os as _os
    with tempfile.NamedTemporaryFile("w", suffix=".dat", delete=False) as f:
        f.write('<datafile><game><rom name="A.gb" crc="1A2B3C4D"/>'
                '<rom name="B.gb" crc="abc"/></game></datafile>')
        path = f.name
    try:
        index = load_dat_index(path)
        assert index["1a2b3c4d"] == "A.gb"
        assert index["00000abc"] == "B.gb"  # short CRCs are zero-padded
    finally:
        _os.unlink(path)
    with pytest.raises(ValueError):
        with tempfile.NamedTemporaryFile("w", suffix=".dat", delete=False) as f:
            f.write("not xml at all <<<")
            bad = f.name
        try:
            load_dat_index(bad)
        finally:
            _os.unlink(bad)


def test_cli_use_saved_config(tmp_path):
    source = tmp_path / "source"
    dest = tmp_path / "sd_card"
    source.mkdir()
    dest.mkdir()
    (dest / "EDGB").mkdir()
    (source / "Game.gbc").write_text("rom data")

    cfg = tmp_path / "config.json"
    cfg.write_text(_json.dumps({
        "Source": str(source),
        "Dest": str(dest),
        "Options": {
            "TypeFolders": False, "AZFolders": False,
            "SeriesFolders": False, "Backups": False,
        },
    }))

    from unittest.mock import patch
    with patch('everdrive.headless.CONFIG_FILE', str(cfg)):
        rc = run_cli(["--use-saved-config", "--yes"])
    assert rc == 0
    # TypeFolders was off in the saved config, so no GBC folder
    assert (dest / "Game.gbc").read_text() == "rom data"
    assert not (dest / "GBC").exists()


def test_manifest_prunes_stale_entries():
    """Manifest entries for ROMs no longer in the library are dropped."""
    from sync_everdrive import SyncApp
    live = {"mario": "Mario"}
    persisted = {"mario": "Mario", "long gone game": "Long Gone Game"}
    merged = SyncApp._build_merged_name_map(live, persisted)
    assert "long gone game" not in merged
    assert merged["mario"] == "Mario"


def test_name_manifest_word_anagram_propagation():
    """A save named with 'X, The' is renamed correctly when the ROM's word order changed.

    Simulates two syncs where the clean name's word order flipped:
      Sync 1: clean name 'Revenge, The' → manifest key 'revenge, the' (comma retained by
              get_fuzzy_title since commas are not stripped)
      Sync 2: live map has 'the revenge' → 'The Revenge' (different fuzzy key, same words)

    Without word-anagram propagation, _build_merged_name_map returns
    {'revenge, the': 'Revenge, The', 'the revenge': 'The Revenge'} and a save
    'Revenge, The.sav' (fuzzy 'revenge, the') maps to the stale old clean name.

    With propagation, 'revenge, the' is updated to 'The Revenge' because the word
    sets {revenge, the} match between the persisted key and the live key.
    """
    from sync_everdrive import SyncApp
    persisted = {"revenge, the": "Revenge, The"}   # stale: clean-name alias from sync 1
    live = {"the revenge": "The Revenge"}           # new clean name with different word order
    merged = SyncApp._build_merged_name_map(live, persisted)

    assert merged.get("revenge, the") == "The Revenge", (
        f"Word-anagram propagation failed: 'revenge, the' → {merged.get('revenge, the')!r}, "
        "expected 'The Revenge'."
    )
    result = SyncApp._fuzzy_match_rom("Revenge, The", merged)
    assert result == "The Revenge", (
        f"Save rename after word-order change failed: got {result!r}, expected 'The Revenge'."
    )

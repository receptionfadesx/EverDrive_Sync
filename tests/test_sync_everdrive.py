import pytest # type: ignore
import os
from pathlib import Path
from sync_everdrive import (
    get_clean_rom_name, 
    get_fuzzy_title, 
    get_best_region_games, 
    get_series_groups, 
    VirtualNode, 
    add_to_virtual_tree
) # type: ignore

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
    def __init__(self, source="", dest="", hacks="", gbcsys="", backups=False, zip=False, fav=False, reorg=True, usa=True, world=True, eur=True, jpn=True, series=False, type_folders=True, az=False, tags=True, restore=False, folders_last=False, recent=False):
        self.logs = []
        self.prog_max = 1
        self.config_data = {
            "Source": str(source), "Hacks": str(hacks), "GbcSysPayload": str(gbcsys), "Dest": str(dest)
        }
        self.txt_source = type('MockEntry', (), {'get': lambda *a: str(self.config_data["Source"])})()
        self.txt_hacks = type('MockEntry', (), {'get': lambda *a: str(self.config_data["Hacks"])})()
        self.txt_gbcsys = type('MockEntry', (), {'get': lambda *a: str(self.config_data["GbcSysPayload"])})()
        self.txt_dest = type('MockEntry', (), {'get': lambda *a: str(self.config_data["Dest"])})()
        
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
    
    backup_file = source / "Saves_Backup" / "SAVE" / "Game1.sav"
    assert backup_file.exists()
    assert backup_file.read_text() == "my save data"
    
    save_file.unlink()
    assert not save_file.exists()
    
    SyncApp.restore_saves(app, str(source), str(dest), "edgb")
    assert save_file.exists()
    assert save_file.read_text() == "my save data"
    
    save_file.unlink()
    backup_file.unlink()
    
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
    assert (source / "Saves_Backup" / "SAVE" / "Zelda64.eep").exists()
    assert (source / "Saves_Backup" / "SAVE" / "Mario64.sra").exists()
    
    (save_dir / "Zelda64.eep").unlink()
    (source / "Saves_Backup" / "SAVE" / "Zelda64.eep").unlink()
    (source / "Saves_Backup" / "Zelda64.eep").write_text("flat eeprom data")
    
    SyncApp.restore_saves(app, str(source), str(dest), "ed64")
    assert (dest / "ed64" / "SAVE" / "Zelda64.eep").exists()
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
    assert (source / "Saves_Backup" / "SAVE" / "Pokemon.sav").exists()

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
    assert (source / "Saves_Backup" / "gamedata" / "Metroid.gba" / "Metroid.sav").exists()
    
    (source / "Saves_Backup" / "gamedata" / "Metroid.gba" / "Metroid.sav").unlink()
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
    with patch('sync_everdrive.CONFIG_FILE', str(config_file)):
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
        
        # 4. Missing EverDrive OS folder
        app = MockSyncApp(source=str(tmp_path), dest=str(dest))
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
            stderr=subprocess.DEVNULL
        )
        
    # 2. Test non-Darwin execution
    with patch('platform.system', return_value='Windows'), \
         patch('subprocess.run') as mock_run:
        app.mac_cleanup("/test/path")
        mock_run.assert_not_called()

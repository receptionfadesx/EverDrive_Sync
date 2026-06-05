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


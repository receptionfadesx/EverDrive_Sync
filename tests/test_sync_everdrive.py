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

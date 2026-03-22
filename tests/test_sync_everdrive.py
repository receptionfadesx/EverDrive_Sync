import pytest # type: ignore
from pathlib import Path
from sync_everdrive import get_clean_rom_name, get_fuzzy_title, get_best_region_games, get_series_groups # type: ignore

def test_get_clean_rom_name():
    assert get_clean_rom_name("Pokemon - Red Version (USA, Europe)") == "Pokemon - Red Version"
    assert get_clean_rom_name("Zelda (Hack)") == "Zelda [Hack]"
    assert get_clean_rom_name("The Legend of Zelda") == "Legend of Zelda, The"
    assert get_clean_rom_name("Super Mario Land (World) (Rev A)") == "Super Mario Land"
    assert get_clean_rom_name("Metroid II - Return of Samus (World)") == "Metroid II - Return of Samus"

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

def test_get_series_groups():
    files = [
        Path("Pokemon Red.gb"),
        Path("Pokemon Blue.gb"),
        Path("Pokemon Yellow.gb"),
        Path("Super Mario Land.gb"),
        Path("Super Mario Land 2.gb"),
        Path("Super Mario Land 3.gb"),
        Path("Random Game.gb")
    ]
    # Pokemon is in 'known' list so it should get "Pokemon"
    # Super Mario Land is also in 'known' list ("Mario") so it gets "Mario"
    groups = get_series_groups(files)
    assert groups[str(Path("Pokemon Red.gb").absolute())] == "Pokemon"
    assert groups[str(Path("Super Mario Land 3.gb").absolute())] == "Mario"
    assert groups.get(str(Path("Random Game.gb").absolute())) == ""

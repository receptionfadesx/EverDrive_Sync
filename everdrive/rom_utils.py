"""ROM name normalisation, region filtering, and series grouping."""
# pylint: disable=too-many-branches,too-many-statements
import re
import unicodedata
import itertools
from pathlib import Path


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
        if clean not in grouped:
            grouped[clean] = []
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
                if usa:
                    score = 10
                else:
                    continue
            elif re.search(r'\(World', name):
                if world:
                    score = 20
                else:
                    continue
            elif re.search(r'\(Europe', name):
                if eur:
                    score = 30
                else:
                    continue
            elif re.search(r'\(Japan', name):
                if jpn:
                    score = 80
                else:
                    continue
            else:
                score = 50

            rev_match = re.search(r'\(Rev ([0-9]+|[A-Z]+)\)', name)
            if rev_match:
                rev = rev_match.group(1)
                if rev in ['1', 'A']:
                    score -= 1
                else:
                    score -= 2

            if re.search(r'(?i)Bugfix', name):
                score -= 5
            elif re.search(r'(?i)Hack', name):
                score -= 4

            if score < best_score:
                best_score = score
                best_game = f

        if best_game:
            best_games.append(best_game)

    return best_games


KNOWN_SERIES = [
    "Pokemon", "Mario", "Zelda", "Donkey Kong", "Wario", "Mega Man",
    "Castlevania", "Bomberman", "Final Fantasy", "Dragon Quest",
    "Kirby", "Tetris", "Metroid", "Street Fighter", "Mortal Kombat",
    "Tomb Raider", "Resident Evil", "Tony Hawk", "Pac-Man", "Crash Bandicoot",
    "Rayman", "Harvest Moon", "Star Wars", "Disney", "Batman", "Spider-Man",
    "X-Men", "Yu-Gi-Oh", "Harry Potter", "Ninja Turtles", "Contra",
    "Metal Gear", "Ghosts 'n Goblins", "Gex", "Earthworm Jim", "Bionic Commando",
    "Double Dragon", "Game & Watch", "R-Type", "Sonic", "Shantae", "Metal Slug",
    "Medabots", "Digimon", "Monster Rancher", "Micro Machines", "SimCity",
]


def get_series_groups(files):
    mapping = {str(f.absolute()): "" for f in files}
    if len(files) < 2:
        return mapping

    assigned = set()
    for f in files:
        clean = get_clean_rom_name(f.stem)
        for k in KNOWN_SERIES:
            if re.search(rf'(?i)\b{re.escape(k)}\b', clean):
                mapping[str(f.absolute())] = k
                assigned.add(str(f.absolute()))
                break

    prefix_files = {}
    unassigned = [f for f in files if str(f.absolute()) not in assigned]

    for f1, f2 in itertools.combinations(unassigned, 2):
        if not isinstance(f1, Path) or not isinstance(f2, Path):
            continue
        n1 = re.sub(r'\s*[:-].*', '', get_clean_rom_name(f1.stem))
        n2 = re.sub(r'\s*[:-].*', '', get_clean_rom_name(f2.stem))
        w1 = [w for w in re.split(r'[\s_]+', n1) if w.strip()]
        w2 = [w for w in re.split(r'[\s_]+', n2) if w.strip()]

        lcp = []
        for k in range(min(len(w1), len(w2))):
            if w1[k].lower() == w2[k].lower():
                lcp.append(w1[k])
            else:
                break

        if len(lcp) >= 2:
            prefix = " ".join(lcp)
            if prefix not in prefix_files:
                prefix_files[prefix] = set()
            curr_set = prefix_files.get(prefix)
            if curr_set is not None:
                curr_set.add(str(f1.absolute()))
                curr_set.add(str(f2.absolute()))

    valid = [(p, len(p.split(" ")), f_set) for p, f_set in prefix_files.items()]
    sorted_pref = sorted(valid, key=lambda x: (x[1], -len(x[2])))

    for p, _words, f_set in sorted_pref:
        un = [f for f in f_set if f not in assigned]
        if len(un) >= 3:
            for f in un:
                mapping[str(f)] = p
                assigned.add(str(f))

    return mapping

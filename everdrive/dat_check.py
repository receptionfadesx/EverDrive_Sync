"""No-Intro DAT verification — match ROM files by CRC32 against a Logiqx XML DAT."""
import zlib
import xml.etree.ElementTree as ET


def load_dat_index(dat_path):
    """Parse a Logiqx XML DAT file. Returns {crc32_hex_lower: rom_name}."""
    try:
        tree = ET.parse(dat_path)
    except ET.ParseError as e:
        raise ValueError(f"Not a valid DAT/XML file: {e}") from e
    index = {}
    for rom in tree.getroot().iter("rom"):
        crc = (rom.get("crc") or "").strip().lower()
        if crc:
            index[crc.zfill(8)] = rom.get("name") or ""
    return index


def file_crc32(path, chunk_size=1 << 20):
    """CRC32 of a file, streamed; returns 8-char lowercase hex."""
    crc = 0
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk_size), b""):
            crc = zlib.crc32(block, crc)
    return f"{crc & 0xFFFFFFFF:08x}"


def verify_files_against_dat(files, dat_index, on_file=None):
    """Check each file's CRC32 against the DAT index.

    Returns (verified, unknown, duplicates):
      verified   — files whose CRC is in the DAT
      unknown    — (file, crc_or_None) pairs not in the DAT (None = unreadable)
      duplicates — (file, first_file) pairs with identical content
    """
    verified, unknown, duplicates = [], [], []
    seen = {}
    for f in files:
        if on_file:
            on_file(f)
        try:
            crc = file_crc32(str(f))
        except OSError:
            unknown.append((f, None))
            continue
        if crc in seen:
            duplicates.append((f, seen[crc]))
        else:
            seen[crc] = f
        if crc in dat_index:
            verified.append(f)
        else:
            unknown.append((f, crc))
    return verified, unknown, duplicates

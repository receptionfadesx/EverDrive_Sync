"""Low-level sync utilities: cancel, mtime comparison, catalog helpers, backup pruning."""
# pylint: disable=missing-function-docstring
import os
import shutil

from .constants import BACKUP_SNAPSHOT_RE, SAVE_EXTS  # noqa: F401  # pylint: disable=unused-import


class SyncCancelled(Exception):
    """Raised inside the sync worker when the user cancels."""


def check_cancel(instance):
    ev = getattr(instance, "cancel_event", None)
    if ev is not None and ev.is_set():
        raise SyncCancelled()


def mtimes_match(a, b):
    # FAT32 stores modification times with 2-second resolution, so copies to
    # the SD card can land up to 2 seconds off the source mtime.
    return abs(int(a) - int(b)) <= 2


def files_content_match(path_a, path_b, sample_size=65536):
    """Cheap content check: compare head and tail samples of two files.

    ROMs are padded to power-of-two sizes, so size+mtime alone can collide
    across different games; the head sample covers the cartridge header and
    title region, which differs between real ROMs.
    """
    try:
        size = os.path.getsize(path_a)
        if os.path.getsize(path_b) != size:
            return False
        with open(path_a, "rb") as fa, open(path_b, "rb") as fb:
            if fa.read(sample_size) != fb.read(sample_size):
                return False
            if size > sample_size:
                tail_off = max(size - sample_size, 0)
                fa.seek(tail_off)
                fb.seek(tail_off)
                if fa.read(sample_size) != fb.read(sample_size):
                    return False
        return True
    except OSError:
        return False


def catalog_pop_match(catalog, size, mtime, source_path=None):
    """Pop and return a cataloged SD path matching size + mtime (FAT32 tolerant).

    When source_path is given, the candidate's content is sampled and compared
    so two different ROMs that happen to share size+mtime are never swapped.
    """
    entries = catalog.get(size)
    if not entries:
        return None
    for i, (entry_mtime, path) in enumerate(entries):
        if mtimes_match(entry_mtime, mtime):
            if source_path is not None and not files_content_match(source_path, path):
                continue
            entries.pop(i)
            return path
    return None


def catalog_discard_path(catalog, size, path):
    entries = catalog.get(size)
    if entries:
        catalog[size] = [e for e in entries if e[1] != path]


def list_backup_snapshots(backup_root):
    if not os.path.isdir(backup_root):
        return []
    return sorted(
        d for d in os.listdir(backup_root)
        if BACKUP_SNAPSHOT_RE.match(d) and os.path.isdir(os.path.join(backup_root, d))
    )


def prune_backups(backup_root, keep=5, log=None):
    for d in list_backup_snapshots(backup_root)[:-keep]:
        try:
            shutil.rmtree(os.path.join(backup_root, d))
            if log:
                log(f"Pruned old save backup: {d}")
        except OSError:
            pass

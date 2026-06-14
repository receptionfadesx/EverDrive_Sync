"""Virtual destination tree built in memory before writing to SD card."""
# pylint: disable=missing-function-docstring
import os

from .rom_utils import get_fuzzy_title


# pylint: disable=too-few-public-methods
class VirtualNode:
    """A node in the virtual destination tree built before writing to SD."""

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
        is_last = i == len(clean_parts) - 1
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
                if get_fuzzy_title(base_no_ext) in fav_list:
                    part = "! " + part

            child = VirtualNode(part, is_folder, source_path if not is_folder else None, last_write)
            current.children.append(child)

        current = child

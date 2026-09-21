"""Deterministically pack the Holy Stone reagent catalog into its native atlas."""
from pathlib import Path

from isolated_item_artwork import pack_catalog
from .catalog import ATLAS, read_catalog


def pack(root: Path) -> dict[Path, bytes]:
    return pack_catalog(root, read_catalog(root), ATLAS, "Holy Stone upgrade reagents")

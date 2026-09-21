"""The eight reviewed item identities and independent atlas coordinates."""
from __future__ import annotations

import json
from pathlib import Path

from holy_stone_icons.catalog import json_bytes, sha256
from level5_forge_icons.common import InstallError

ATLAS = "HolyStoneReagents.gwo"
TEXTURE = "./Localization/en_us/UI/Texture/" + ATLAS
ITEMS = (
    (9040, "eclipse-level-1", "Level 1 Eclipse Stone", "Icon.gwo", "828,900"),
    (9041, "eclipse-level-2", "Level 2 Eclipse Stone", "Icon.gwo", "864,900"),
    (9042, "eclipse-level-3", "Level 3 Eclipse Stone", "Icon.gwo", "900,900"),
    (9050, "goddess-stone", "Goddess' Stone", "Icon2.gwo", "324,0"),
    (9051, "copper-evasion-signet", "Copper Evasion Signet", "Icon.gwo", "540,936"),
    (9052, "silver-evasion-signet", "Silver Evasion Signet", "Icon.gwo", "576,936"),
    (9053, "gold-evasion-signet", "Gold Evasion Signet", "Icon.gwo", "612,936"),
    (9054, "platinum-evasion-signet", "Platinum Evasion Signet", "Icon.gwo", "612,936"),
)


def expected_manifest() -> dict:
    return {"schema_version": 1, "sprite_size": 36, "atlas_size": 1024,
            "texture": TEXTURE,
            "entries": [{"item_id": item_id, "slug": slug, "name": name,
                         "atlas": ATLAS, "x": index * 36, "y": 0}
                        for index, (item_id, slug, name, _, _) in enumerate(ITEMS)]}


def read_catalog(root: Path) -> list[dict]:
    manifest = json.loads((root / "manifest.json").read_bytes())
    if manifest != expected_manifest():
        raise InstallError("Holy Stone reagent manifest differs from the reviewed eight-item contract")
    return manifest["entries"]

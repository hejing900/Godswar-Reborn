"""Offline checks for AR10--AR14 role-aware armor plus Warrior WR10."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from ArmorRank13And14BindingChecks import (
    CAPSTONE_BINDING_METADATA as CAPSTONE_METADATA,
)
from TestArmorRank12Aether import (
    maximum_rgb,
    verify_ar12_contract_entries,
    verify_ar12_model_contract,
    verify_ar12_package_effects,
)
from TestArmorRank13And14 import verify_capstone_package
from rank_effect_packages.formats import (
    extract_texture_references,
    structural_fingerprint,
    validate_tga_texture,
)
from rank_effect_packages.installer import verify_new_silhouettes
from rank_effect_packages.package import AR10_PROTECTED_CLONE_POLICY, load_package
from rank_effect_v2.armor_ranks import (
    AR9_DERIVED_ARMOR_RANKS,
    ARMOR_RANKS,
    ARMOR_RANK_DESIGNS,
    slot_roles_for_rank,
)


ROOT = Path(__file__).resolve().parents[1]
AR9_STRUCTURES = (
    "558628f87eb52aff06c0113714c8fdf20c3104581c4519d3c8e9aad8eba34982",
    "82bb71925b3a0e5589eb19df3b35de2407ee6139387a8a708cd8c0fdd54669cd",
    "b63a5fdc4e1759b63d60641bb9a7bece52980c551e8ea075ad1d81f1b1fb673c",
)
AR11_STRUCTURES = (
    "c1009933994c465536e3a9fbbecc3d706d6bcf093fb9a9a013434325309a1695",
    "5debb2a030ce23001edb7c8b7312ff8c38818cf6909ee68950a775355c2dffb4",
    AR9_STRUCTURES[2],
)
AR11_COMBINED_STRUCTURE = hashlib.sha256(
    "\n".join(AR11_STRUCTURES).encode("ascii")
).hexdigest()
AR11_ROLES = {
    "animated-core": ("halo", ("182F49", "386B91", "72ACC5"), 0.94, 200),
    "animated-butterfly": ("wings", ("244A70", "5D9FD0", "A9D7EA"), 1.0, 220),
    "animated-rune": ("rune", ("276D87", "63C4DE", "BFEFFF"), 1.08, 230),
    "outer-wing": ("outer_wings", ("0D294B", "285F94", "6F9FC7"), 0.95, 208),
}
AR11_WING_SOURCE_SHA256 = "d37fd11d06c99646015d8b9634961fad00cb87c9a40080b4130d54d9ad361b13"
def _combined_structure(parts: tuple[str, str, str]) -> str:
    return hashlib.sha256("\n".join(parts).encode("ascii")).hexdigest()


def _contracts(root: Path, manifest: dict[str, object]) -> list[dict[str, object]]:
    relative = manifest.get("role_contract")
    assert isinstance(relative, str)
    main = json.loads((root / relative).read_text(encoding="utf-8"))
    assert main["format"] == "reborn-rank-effect-role-contract-v2"
    assert main["prototype"] is False
    result: list[dict[str, object]] = []
    for name in main["contract_manifests"]:
        shard = json.loads((root / name).read_text(encoding="utf-8"))
        assert shard["format"] == "reborn-rank-effect-role-contract-shard-v2"
        result.extend(shard["contracts"])
    return result


def _palette_hex(entry: dict[str, object]) -> tuple[str, str, str]:
    palette = entry["palette"]
    assert isinstance(palette, dict)
    result = []
    for name in ("shadow", "middle", "highlight"):
        colour = palette[name]
        assert isinstance(colour, list) and len(colour) == 3
        result.append(
            "".join(f"{round(float(channel) * 255):02X}" for channel in colour)
        )
    return tuple(result)  # type: ignore[return-value]


def _verify_armor_models(armor: list[dict[str, object]]) -> None:
    ar9_slots = {
        0: ("animated-core", 116, 100, [100], 1),
        1: ("animated-butterfly", 976, 848, [0, 848], 1),
        2: ("animated-rune", 136, 128, [128], 1),
    }
    ar11_outputs: dict[tuple[str, str], dict[int, str]] = {}
    for entry in armor:
        rank = int(str(entry["effect"]).removeprefix("armor-ar"))
        assert rank in AR9_DERIVED_ARMOR_RANKS
        assert entry["design"] == ARMOR_RANK_DESIGNS[rank].name
        slot = int(entry["slot"])
        if rank == 12:
            verify_ar12_model_contract(entry)
            continue
        assert rank in (10, 11) and entry["source_rank"] == 9
        role, vertices, faces, materials, animations = ar9_slots[slot]
        assert entry["role"] == role == slot_roles_for_rank(rank)[slot]
        source, output = entry["source"], entry["output"]
        assert isinstance(source, dict) and isinstance(output, dict)
        output_materials = (
            [256, 592] if rank in (11, 12) and slot == 1 else materials
        )
        for audit, expected_materials in (
            (source, materials), (output, output_materials)
        ):
            assert (audit["vertices"], audit["faces"]) == (vertices, faces)
            assert audit["material_face_counts"] == expected_materials
            assert audit["animation_keys"] == animations
        if rank == 10:
            assert entry["sculpted"] is False and entry["changed_vertices"] == 0
            assert entry["source_structural_sha256"] == entry["output_structural_sha256"]
        elif rank == 11:
            sculpted_flag, changed = {0: (True, 116), 1: (True, 464), 2: (False, 0)}[slot]
            assert entry["sculpted"] is sculpted_flag
            assert int(entry["changed_vertices"]) == changed
            assert entry["source_structural_sha256"] == AR9_STRUCTURES[slot]
            assert entry["output_structural_sha256"] == AR11_STRUCTURES[slot]
            if slot in (0, 1):
                assert entry["source_structural_sha256"] != entry["output_structural_sha256"]
            if slot == 1:
                outer = entry["outer_material"]
                assert isinstance(outer, dict)
                assert outer["output_material_face_counts"] == [256, 592]
                assert outer["changed_faces"] == 256
            key = (str(entry["asset_root"]), str(entry["gender"]))
            ar11_outputs.setdefault(key, {})[slot] = str(entry["output_structural_sha256"])

    assert len(ar11_outputs) == 4
    assert all(values == dict(enumerate(AR11_STRUCTURES)) for values in ar11_outputs.values())


def _verify_armor_atlases(atlases: list[dict[str, object]]) -> None:
    ar10 = [entry for entry in atlases if entry["effect"] == "armor-ar10-atlas"]
    ar11 = [entry for entry in atlases if entry["effect"] == "armor-ar11-atlas"]
    ar12 = [entry for entry in atlases if entry["effect"] == "armor-ar12-atlas"]
    assert (len(ar10), len(ar11), len(ar12)) == (10, 12, 12)
    verify_ar12_contract_entries(ar12)
    assert {str(entry["role"]) for entry in ar10} == {
        "animated-core",
        "animated-butterfly",
        "declared-unused",
        "canonical",
    }
    assert sum(entry["role"] == "canonical" for entry in ar10) == 4
    for entry in ar10:
        assert entry["source_rank"] == 9
        assert entry["preserve_luma"] is True
        assert entry["additive_glow"] is False
        assert entry["region"] == [0.0, 1.0, 0.0, 1.0]
        assert entry["luma_gain"] == 1.0 and entry["maximum_channel"] == 255
        assert entry["changed_pixels"] == (
            2157 if entry["role"] == "canonical" else 2402
        )
        assert entry["source_sha256"] != entry["output_sha256"]

    assert all(sum(entry["role"] == role for entry in ar11) == 2 for role in AR11_ROLES)
    assert sum(entry["role"] == "canonical-composite" for entry in ar11) == 4
    for entry in ar11:
        role = str(entry["role"])
        assert entry["source_rank"] == 9
        assert entry["additive_glow"] is False
        assert entry["region"] == [0.0, 1.0, 0.0, 1.0]
        if role in AR11_ROLES:
            _suffix, palette, gain, ceiling = AR11_ROLES[role]
            assert entry["preserve_luma"] is True
            assert entry["luma_gain"] == gain
            assert entry["maximum_channel"] == ceiling
            assert entry["strength"] == 1.0
            assert _palette_hex(entry) == palette
            assert entry["active_pixels"] == entry["changed_pixels"] == 2402
            assert entry["source_sha256"] != entry["output_sha256"]
            assert Path(str(entry["target"])).name == (
                f"reborn_body_effect_0011_v2_{_suffix}.tga"
            )
            if role in {"animated-butterfly", "outer-wing"}:
                assert entry["source_sha256"] == AR11_WING_SOURCE_SHA256
        else:
            assert role == "canonical-composite"
            assert entry["preserve_luma"] is True
            assert all(
                entry[key] is None
                for key in ("palette", "strength", "luma_gain", "maximum_channel")
            )
            assert entry["active_pixels"] == entry["changed_pixels"] == 2157
            assert entry["source_sha256"] != entry["output_sha256"]
            segments = entry["segments"]
            assert isinstance(segments, list) and len(segments) == 3

    for entry in atlases:
        rank = int(str(entry["effect"]).removeprefix("armor-ar").removesuffix("-atlas"))
        assert entry["design"] == ARMOR_RANK_DESIGNS[rank].name
        assert entry["alpha_changes"] == 0
        assert entry["outside_region_changes"] == 0


def _verify_weapon_contracts(
    weapon: list[dict[str, object]], weapon_atlas: list[dict[str, object]]
) -> None:
    expected = {
        0: ("static-corona", 78, 26, [0, 26], 0),
        1: ("travelling-spark", 240, 80, [80], 2),
    }
    for entry in weapon:
        slot = int(entry["slot"])
        role, vertices, faces, materials, animations = expected[slot]
        assert entry["source_effect_id"] == 9
        assert entry["sculpted"] is False and entry["role"] == role
        assert entry["source_structural_sha256"] == entry["output_structural_sha256"]
        source, output = entry["source"], entry["output"]
        assert isinstance(source, dict) and isinstance(output, dict)
        for audit in (source, output):
            assert audit["vertices"] == vertices and audit["faces"] == faces
            assert audit["material_face_counts"] == materials
            assert audit["animation_keys"] == animations
            assert audit["bounds"] == source["bounds"]

    assert {str(entry["role"]) for entry in weapon_atlas} == {
        "declared-unused",
        "static-corona",
        "travelling-spark",
    }
    for entry in weapon_atlas:
        assert entry["alpha_changes"] == 0
        if entry["role"] == "declared-unused":
            assert entry["source_sha256"] == entry["output_sha256"]
            assert entry["changed_pixels"] == 0
        else:
            assert entry["source_sha256"] != entry["output_sha256"]
            assert int(entry["changed_pixels"]) > 0


def _verify_capstones(package, contracts, effects) -> None:
    entries = [
        entry for entry in contracts
        if str(entry["effect"]).removeprefix("armor-ar")[:2] in {"13", "14"}
    ]
    assert len(entries) == 48
    assert all(all(entry[key] == value for key, value in CAPSTONE_METADATA.items())
               for entry in entries)
    models = [entry for entry in entries if not str(entry["effect"]).endswith("-atlas")]
    expected_routes = {
        0: (4, "animated-rune", "exact-native-ar4-orbit-only", 136, 128),
        1: (9, "animated-butterfly", "exact-approved-ar12-butterfly", 976, 848),
        2: (5, "animated-flame", "native-ar5-animated-flame", 200, 150),
    }
    for entry in models:
        slot = int(entry["slot"])
        source, role, family, vertices, faces = expected_routes[slot]
        assert (entry["source_rank"], entry["role"], entry["geometry_family"]) == (
            source, role, family)
        output = entry["output"]
        assert isinstance(output, dict)
        assert (output["vertices"], output["faces"], output["animation_keys"]) == (
            vertices, faces, 1)
        assert entry["source_slot"] == slot
        if slot == 0:
            materials = [0, 128] if entry["gender"] == "female" else [0, 0, 128]
            assert output["material_face_counts"] == materials
        elif slot == 1:
            assert output["material_face_counts"] == [256, 592]
        else:
            assert output["material_face_counts"] == [150]
            assert output["uv_bounds"] == [0.022013, 0.161324, 0.012963, 0.493873]
            assert entry["native_ar5_slot"] == 2
            assert entry["animation"]["matrix_keys"] == 73
            assert entry["uv_transform"]["method"] == "identity"
            assert entry["uv_transform"]["changed_values"] == 0
            assert entry["ar5_flame_uv_remapped"] is False
    flames = [entry for entry in entries if entry["role"] == "animated-flame"
              and str(entry["effect"]).endswith("-atlas")]
    assert len(flames) == 4
    assert all(entry["source_rank"] == 5
               and entry["texture_source"] == "native-ar5-canonical-gwo"
               and entry["sampling"]["method"] == "native-uv-no-remap"
               for entry in flames)
    for effect in effects:
        matching = sorted(
            (entry for entry in models
             if entry["effect"] == f"armor-ar{effect.rank}"
             and entry["asset_root"] == effect.asset_root
             and entry["gender"] == effect.gender),
            key=lambda entry: int(entry["slot"]),
        )
        expected = tuple(entry["output_structural_sha256"] for entry in matching)
        assert len(expected) == 3
        actual = tuple(structural_fingerprint(package.assets[path], path.as_posix())
                       for path in sorted(effect.models, key=lambda value: value.name))
        assert actual == expected
        assert effect.structural_sha256 == _combined_structure(expected)
        assert {path.name.split("_v2_", 1)[1] for path in effect.private_textures} == {
            "flame.tga", "wings.tga", "outer_wings.tga", "orbit.tga",
        }
        assert validate_tga_texture(
            package.assets[effect.canonical_texture], effect.canonical_texture.as_posix()
        ).bits_per_pixel == 24


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, required=True)
    root = parser.parse_args().package_root.resolve()
    package = load_package(root)
    verify_new_silhouettes(package)
    assert package.manifest["package_id"] == "reborn-role-aware-rank-effects-v2"
    assert package.manifest["armor_rank_10_structure"] == AR10_PROTECTED_CLONE_POLICY
    assert package.manifest["coverage"] == {
        "armor_ranks": list(ARMOR_RANKS),
        "weapon_classes": ["warrior"],
    }
    assert len(package.effects) == 24
    assert len(package.assets) == 142

    ar10_effects = [e for e in package.effects if e.kind == "armor" and e.rank == 10]
    assert len(ar10_effects) == 4
    assert all(
        effect.structural_sha256 == _combined_structure(AR9_STRUCTURES)
        for effect in ar10_effects
    )
    for effect in ar10_effects:
        assert len(effect.private_textures) == 3
        info = validate_tga_texture(
            package.assets[effect.canonical_texture], effect.canonical_texture.as_posix()
        )
        assert info.bits_per_pixel == 24
        assert all(
            validate_tga_texture(package.assets[path], path.as_posix()).bits_per_pixel == 32
            for path in effect.private_textures
        )
        assert tuple(
            structural_fingerprint(package.assets[path], path.as_posix())
            for path in sorted(effect.models, key=lambda value: value.name)
        ) == AR9_STRUCTURES

    ar11_effects = [e for e in package.effects if e.kind == "armor" and e.rank == 11]
    assert len(ar11_effects) == 4
    assert all(
        effect.structural_sha256 == AR11_COMBINED_STRUCTURE
        for effect in ar11_effects
    )
    expected_private_names = {
        f"reborn_body_effect_0011_v2_{values[0]}.tga"
        for values in AR11_ROLES.values()
    }
    expected_references = (
        {b"reborn_body_effect_0011_v2_halo.tga"},
        {
            b"reborn_body_effect_0011_v2_outer_wings.tga",
            b"reborn_body_effect_0011_v2_wings.tga",
        },
        {b"reborn_body_effect_0011_v2_rune.tga"},
    )
    private_ceilings = {
        f"reborn_body_effect_0011_v2_{suffix}.tga": ceiling
        for suffix, _palette, _gain, ceiling in AR11_ROLES.values()
    }
    for effect in ar11_effects:
        assert {path.name for path in effect.private_textures} == expected_private_names
        assert maximum_rgb(
            package.assets[effect.canonical_texture],
            effect.canonical_texture.as_posix(),
        ) == 220
        assert tuple(
            structural_fingerprint(package.assets[path], path.as_posix())
            for path in sorted(effect.models, key=lambda value: value.name)
        ) == AR11_STRUCTURES
        for slot, path in enumerate(sorted(effect.models, key=lambda value: value.name)):
            assert set(
                extract_texture_references(package.assets[path], path.as_posix())
            ) == expected_references[slot]
        for path in effect.private_textures:
            info = validate_tga_texture(package.assets[path], path.as_posix())
            assert info.bits_per_pixel == 32
            if path.name in private_ceilings:
                assert maximum_rgb(package.assets[path], path.as_posix()) == private_ceilings[
                    path.name
                ]

    ar12_effects = [e for e in package.effects if e.kind == "armor" and e.rank == 12]
    verify_ar12_package_effects(package, ar12_effects)
    capstone_effects = [
        effect for effect in package.effects
        if effect.kind == "armor" and effect.rank in (13, 14)
    ]
    assert len(ar12_effects) == 4 and len(capstone_effects) == 8
    assert all(len(effect.private_textures) == 4 for effect in capstone_effects)

    contracts = _contracts(root, package.manifest)
    assert len(contracts) == 138
    armor_contracts = [e for e in contracts if str(e["effect"]).startswith("armor-ar")]
    armor = [e for e in armor_contracts if not str(e["effect"]).endswith("-atlas")]
    armor_atlas = [e for e in armor_contracts if str(e["effect"]).endswith("-atlas")]
    weapon = [entry for entry in contracts if entry["effect"] == "weapon-warrior-wr10"]
    weapon_atlas = [
        entry for entry in contracts if entry["effect"] == "weapon-warrior-wr10-atlas"
    ]
    assert (len(armor), len(armor_atlas), len(weapon), len(weapon_atlas)) == (
        60,
        58,
        8,
        12,
    )
    verify_capstone_package(
        package, contracts, ROOT / ".tmp/rank-effect-metallic-source-20260830-02"
    )
    _verify_capstones(package, contracts, capstone_effects)
    _verify_armor_models([
        entry for entry in armor
        if int(str(entry["effect"]).removeprefix("armor-ar")) <= 12
    ])
    _verify_armor_atlases([
        entry for entry in armor_atlas
        if int(str(entry["effect"]).removeprefix("armor-ar").removesuffix("-atlas")) <= 12
    ])
    _verify_weapon_contracts(weapon, weapon_atlas)

    for path, data in package.assets.items():
        if path.suffix.lower() in {".gwo", ".tga"}:
            info = validate_tga_texture(data, path.as_posix())
            assert (info.width, info.height) == (64, 64)
    for path in root.rglob("*.json"):
        assert path.stat().st_size < 20 * 1024, f"oversized JSON: {path}"
    for path in (ROOT / "tools" / "rank_effect_v2").glob("*.py"):
        assert path.stat().st_size < 20 * 1024, f"oversized source: {path}"
    print("PASS role-aware AR10--AR14 plus Warrior-WR10 package")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Build the AR9-derived animated AR11 bridge package shard."""

from __future__ import annotations

from pathlib import Path

from erebus_lion.model_codec import expand_xof_mszip
from rank_effect_packages.catalog import GENDERS
from rank_effect_packages.errors import RankEffectError
from xmodel_sculpt.binary_x import parse_tokens
from xmodel_sculpt.mesh import discover_meshes
from xmodel_sculpt.sculpt import sculpt_xof_mszip

from .ar11_atlas import (
    author_ar11_canonical,
    author_ar11_private,
)
from .ar11_bridge import (
    HALO_VERTICES,
    WING_CHANGED_VERTICES,
    Ar11HaloTransform,
    Ar11WingTransform,
    validate_ar11_halo,
    validate_ar11_wings,
)
from .ar11_outer_material import author_ar11_outer_material
from .armor_contracts import record_atlas, record_model
from .armor_ranks import (
    ARMOR_CLONE_SOURCE_RANK,
    AR11_ROLE_ATLASES,
    slot_roles_for_rank,
)
from .package_io import PackageShard, regular


def _single_mesh(encoded: bytes, label: str):
    expanded = expand_xof_mszip(encoded, label)
    meshes = discover_meshes(expanded, parse_tokens(expanded))
    if len(meshes) != 1:
        raise RankEffectError(f"Role-aware armor JCS must contain one mesh: {label}")
    return meshes[0]


def build_ar11_bridge(
    client: Path,
    shard: PackageShard,
    asset_root: str,
    contracts: list[dict[str, object]],
    rewrite,
) -> None:
    """Author one asset root of the animated stormsteel AR11 bridge."""

    rank = 11
    directory = client / asset_root / "effect"
    roles = (
        ("animated-core", "female_body_effect_0010.tga", "halo"),
        ("animated-butterfly", "female_body_effect_0011.tga", "wings"),
        ("animated-rune", "female_body_effect_0010.tga", "rune"),
        ("outer-wing", "female_body_effect_0011.tga", "outer_wings"),
    )
    private_by_role: dict[str, Path] = {}
    for role, source_name, suffix in roles:
        source = regular(directory / source_name, f"native AR11 {role} atlas donor")
        atlas = AR11_ROLE_ATLASES[role]
        authored = author_ar11_private(source, role)
        result = authored.recolour
        target = Path(asset_root) / "effect" / (
            f"reborn_body_effect_{rank:04d}_v2_{suffix}.tga"
        )
        shard.add(target, result.encoded)
        private_by_role[role] = target
        entry = record_atlas(
            contracts,
            rank=rank,
            asset_root=asset_root,
            role=role,
            source_rank=ARMOR_CLONE_SOURCE_RANK,
            source=source,
            result=result,
            target=target,
            additive_glow=False,
            preserve_luma=True,
            palette=atlas.palette,
            luma_gain=atlas.luma_gain,
            maximum_channel=atlas.maximum_channel,
        )
        entry.update(authored.contract_metadata())

    for gender in GENDERS:
        source_stem = f"{gender}_body_effect_{ARMOR_CLONE_SOURCE_RANK:04d}"
        target_stem = f"{gender}_body_effect_{rank:04d}"
        canonical_source = regular(
            directory / f"{source_stem}.gwo", "native AR9 canonical atlas"
        )
        canonical_authored = author_ar11_canonical(canonical_source)
        canonical_result = canonical_authored.recolour
        canonical = Path(asset_root) / "effect" / f"{target_stem}.gwo"
        shard.add(canonical, canonical_result.encoded)
        entry = record_atlas(
            contracts,
            rank=rank,
            asset_root=asset_root,
            gender=gender,
            role="canonical-composite",
            source_rank=ARMOR_CLONE_SOURCE_RANK,
            source=canonical_source,
            result=canonical_result,
            target=canonical,
            additive_glow=False,
            preserve_luma=True,
            palette=AR11_ROLE_ATLASES["animated-butterfly"].palette,
        )
        entry.update(canonical_authored.contract_metadata())

        models: list[Path] = []
        slot_mappings = (
            {
                b"female_body_effect_0010.tga": private_by_role[
                    "animated-core"
                ].name.encode("ascii")
            },
            {
                b"female_body_effect_0011.tga": private_by_role[
                    "animated-butterfly"
                ].name.encode("ascii"),
                b"11.tga": private_by_role["outer-wing"].name.encode("ascii"),
            },
            {
                b"female_body_effect_0010.tga": private_by_role[
                    "animated-rune"
                ].name.encode("ascii")
            },
        )
        for slot, role in enumerate(slot_roles_for_rank(rank)):
            source_path = directory / f"{source_stem}_{slot}.jcs"
            source = regular(source_path, "native AR9-family AR11 JCS donor")
            authored = source
            outer_material = None
            changed_vertices = 0
            if slot in (0, 1):
                if slot == 1:
                    outer_material = author_ar11_outer_material(
                        source, label=str(source_path)
                    )
                    authored = outer_material.encoded
                transform = Ar11HaloTransform() if slot == 0 else Ar11WingTransform()
                sculpt = sculpt_xof_mszip(authored, transform, label=str(source_path))
                authored = sculpt.encoded
                changed_vertices = sculpt.changed_vertices
                source_mesh = _single_mesh(source, f"{source_path}:source")
                output_vertices = tuple(
                    _single_mesh(authored, f"{source_path}:AR11").vertices
                )
                if slot == 0:
                    if changed_vertices != HALO_VERTICES:
                        raise RankEffectError("AR11 halo did not scale every vertex")
                    validate_ar11_halo(source_mesh, output_vertices)
                else:
                    if changed_vertices != WING_CHANGED_VERTICES:
                        raise RankEffectError("AR11 wing band changed unexpectedly")
                    validate_ar11_wings(source_mesh, output_vertices)
            output = rewrite(authored, slot_mappings[slot], str(source_path))
            target = Path(asset_root) / "effect" / f"{target_stem}_{slot}.jcs"
            shard.add(target, output)
            models.append(target)
            entry = record_model(
                contracts,
                rank=rank,
                asset_root=asset_root,
                gender=gender,
                slot=slot,
                role=role,
                source_rank=ARMOR_CLONE_SOURCE_RANK,
                source_path=source_path,
                target=target,
                source=source,
                output=output,
                sculpted=slot in (0, 1),
                changed_vertices=changed_vertices,
            )
            if outer_material is not None:
                entry.update(outer_material.contract_metadata())
        shard.effects.append(
            {
                "kind": "armor",
                "rank": rank,
                "asset_root": asset_root,
                "gender": gender,
                "class": None,
                "models": [path.as_posix() for path in models],
                "canonical_texture": canonical.as_posix(),
                "private_textures": [
                    private_by_role[role].as_posix()
                    for role in slot_roles_for_rank(rank)
                ]
                + [private_by_role["outer-wing"].as_posix()],
            }
        )

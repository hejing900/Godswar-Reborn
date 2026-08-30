"""Shared role-contract recording for authored armor models."""

from __future__ import annotations

from pathlib import Path

from rank_effect_packages.baseline import sha256_bytes
from rank_effect_packages.formats import structural_fingerprint

from .armor_ranks import ARMOR_RANK_DESIGNS, AtlasPalette
from .atlas import RecolourResult
from .models import audit_model


def _audit_dict(value) -> dict[str, object]:
    return {
        "vertices": value.vertices,
        "faces": value.faces,
        "material_face_counts": list(value.material_face_counts),
        "uv_bounds": [round(number, 6) for number in value.uv_bounds],
        "animation_keys": value.animation_keys,
        "texture_references": list(value.texture_references),
        "bounds": [[round(number, 7) for number in vector] for vector in value.bounds],
        "centroid": [round(number, 7) for number in value.centroid],
    }


def record_atlas(
    contracts: list[dict[str, object]],
    *,
    rank: int,
    asset_root: str,
    role: str,
    source_rank: int,
    source: bytes,
    result: RecolourResult,
    target: Path,
    additive_glow: bool,
    preserve_luma: bool,
    gender: str | None = None,
    palette: AtlasPalette | None = None,
    luma_gain: float = 1.0,
    maximum_channel: int = 255,
) -> dict[str, object]:
    design = ARMOR_RANK_DESIGNS[rank]
    selected = palette or design.palette
    entry: dict[str, object] = {
        "effect": f"armor-ar{rank}-atlas",
        "design": design.name,
        "asset_root": asset_root,
        **({"gender": gender} if gender is not None else {}),
        "role": role,
        "source_rank": source_rank,
        "target": target.as_posix(),
        "source_sha256": sha256_bytes(source),
        "output_sha256": sha256_bytes(result.encoded),
        "changed_pixels": result.changed_pixels,
        "outside_region_changes": result.outside_region_changes,
        "alpha_changes": result.alpha_changes,
        "additive_glow": additive_glow,
        "preserve_luma": preserve_luma,
        "luma_gain": luma_gain,
        "maximum_channel": maximum_channel,
        "region": list(selected.region),
        "palette": {
            "shadow": list(selected.shadow),
            "middle": list(selected.middle),
            "highlight": list(selected.highlight),
            "strength": selected.strength,
        },
    }
    contracts.append(entry)
    return entry


def record_model(
    contracts: list[dict[str, object]],
    *,
    rank: int,
    asset_root: str,
    gender: str,
    slot: int,
    role: str,
    source_rank: int,
    source_path: Path,
    target: Path,
    source: bytes,
    output: bytes,
    sculpted: bool,
    changed_vertices: int,
) -> dict[str, object]:
    design = ARMOR_RANK_DESIGNS[rank]
    entry: dict[str, object] = {
        "effect": f"armor-ar{rank}",
        "design": design.name,
        "intent": design.intent,
        "asset_root": asset_root,
        "gender": gender,
        "slot": slot,
        "role": role,
        "source_rank": source_rank,
        "sculpted": sculpted,
        "changed_vertices": changed_vertices,
        "source_sha256": sha256_bytes(source),
        "output_sha256": sha256_bytes(output),
        "source_structural_sha256": structural_fingerprint(source, str(source_path)),
        "output_structural_sha256": structural_fingerprint(output, str(target)),
        "source": _audit_dict(audit_model(source, str(source_path))),
        "output": _audit_dict(audit_model(output, str(target))),
    }
    contracts.append(entry)
    return entry

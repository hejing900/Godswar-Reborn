"""Author the raw private texture for the native-UV AR5 slot-2 flame."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib

from rank_effect_packages.errors import RankEffectError
from rank_effect_packages.formats import validate_tga_texture

from .armor_ranks import RoleAtlasDesign
from .atlas import RecolourResult
from .capstone_flame_atlas import (
    FLAME_COPIED_PIXELS,
    FLAME_RECOLOURED_PIXELS,
    FLAME_SOURCE_TEXELS,
    NATIVE_AR5_FLAME_CROP_BGRA_SHA256,
    NATIVE_AR5_FLAME_CROP_BGR_SHA256,
    NATIVE_AR5_FLAME_GWO_SHA256,
    NATIVE_AR5_FLAME_RAW_SHA256,
    TINTED_AR5_FLAME_CROP_BGRA_SHA256,
    TINTED_AR5_FLAME_CROP_BGR_SHA256,
    TINTED_AR5_FLAME_RAW_SHA256,
    decode_native_ar5_flame,
    recolour_native_ar5_flame,
)


PRIVATE_FLAME_SOURCE_TEXELS = FLAME_SOURCE_TEXELS
PRIVATE_FLAME_TARGET_TEXELS = FLAME_SOURCE_TEXELS
PRIVATE_FLAME_COPIED_PIXELS = FLAME_COPIED_PIXELS
PRIVATE_FLAME_RECOLOURED_PIXELS = FLAME_RECOLOURED_PIXELS


@dataclass(frozen=True, slots=True)
class AuthoredCapstonePrivateFlame:
    """Tinted raw AR5 atlas with exact native-UV and alpha evidence."""

    recolour: RecolourResult
    rank: int
    source_sha256: str
    raw_source_sha256: str
    source_crop_bgra_sha256: str
    source_crop_bgr_sha256: str
    tinted_crop_bgra_sha256: str
    tinted_crop_bgr_sha256: str
    output_sha256: str
    source_recoloured_pixels: int
    sampled_pixels: int
    outside_footprint_changes: int
    alpha_changes: int
    palette: tuple[tuple[float, float, float], ...]
    strength: float
    luma_gain: float
    maximum_channel: int

    @property
    def encoded(self) -> bytes:
        return self.recolour.encoded

    @property
    def copied_pixels(self) -> int:
        """Compatibility count for the canonical/private sampled footprint."""

        return self.sampled_pixels

    @property
    def target_changed_pixels(self) -> int:
        """Compatibility count; no relocation target exists in this path."""

        return self.source_recoloured_pixels

    def contract_metadata(self) -> dict[str, object]:
        footprint = list(PRIVATE_FLAME_SOURCE_TEXELS)
        return {
            "texture_family": "native-ar5-private-slot2-animated-flame",
            "texture_source": "native-ar5-canonical-gwo",
            "runtime_binding": "jcs-declared-private-tga",
            "atlas_authority": "runtime-required-jcs-material-tga",
            "native_source_gwo_sha256": self.source_sha256,
            "decoded_raw_source_sha256": self.raw_source_sha256,
            "output_sha256": self.output_sha256,
            "source_crop_bgra_sha256": self.source_crop_bgra_sha256,
            "source_crop_bgr_sha256": self.source_crop_bgr_sha256,
            "tinted_crop_bgra_sha256": self.tinted_crop_bgra_sha256,
            "tinted_crop_bgr_sha256": self.tinted_crop_bgr_sha256,
            "layout": {
                "width": 64,
                "height": 64,
                "image_type": 2,
                "bits_per_pixel": 32,
                "descriptor": 8,
                "rle_decoded": True,
                "identifier_free": True,
                "footer_preserved": True,
                "outside_footprint_preserved": True,
                "alpha_all_255": True,
                "alpha_changes": self.alpha_changes,
            },
            "sampling": {
                "source_bilinear_texels": footprint,
                "target_bilinear_texels": footprint,
                "method": "native-uv-no-remap",
                "uv_translation": [0.0, 0.0],
                "scale": [1.0, 1.0],
                "native_uv_preserved": True,
                "sampled_pixels": self.sampled_pixels,
                "recoloured_pixels": self.source_recoloured_pixels,
                "outside_footprint_changes": self.outside_footprint_changes,
                "canonical_private_sampled_bgr_identical": True,
            },
            "palette_role": "animated-flame",
            "palette": {
                "shadow": list(self.palette[0]),
                "middle": list(self.palette[1]),
                "highlight": list(self.palette[2]),
                "strength": self.strength,
                "luma_gain": self.luma_gain,
                "maximum_channel": self.maximum_channel,
            },
        }


def _payload(
    data: bytes,
    rectangle: tuple[int, int, int, int],
    channels: int,
) -> bytes:
    minimum_x, maximum_x, minimum_y, maximum_y = rectangle
    values = bytearray()
    for y in range(minimum_y, maximum_y + 1):
        for x in range(minimum_x, maximum_x + 1):
            offset = 18 + ((63 - y) * 64 + x) * 4
            values.extend(data[offset : offset + channels])
    return bytes(values)


def _outside_changes(before: bytes, after: bytes) -> int:
    footprint = {
        (x, y)
        for y in range(PRIVATE_FLAME_SOURCE_TEXELS[2], PRIVATE_FLAME_SOURCE_TEXELS[3] + 1)
        for x in range(PRIVATE_FLAME_SOURCE_TEXELS[0], PRIVATE_FLAME_SOURCE_TEXELS[1] + 1)
    }
    changes = 0
    for y in range(64):
        for x in range(64):
            if (x, y) in footprint:
                continue
            offset = 18 + ((63 - y) * 64 + x) * 4
            changes += before[offset : offset + 4] != after[offset : offset + 4]
    return changes


def author_capstone_private_flame(
    source: bytes,
    *,
    rank: int,
    design: RoleAtlasDesign,
) -> AuthoredCapstonePrivateFlame:
    """Decode the native AR5 GWO and tint only slot 2's sampled footprint."""

    raw = decode_native_ar5_flame(source)
    tinted = recolour_native_ar5_flame(source, rank=rank, design=design)
    encoded = tinted.encoded
    source_info = validate_tga_texture(source, "native AR5 animated-flame GWO")
    output_info = validate_tga_texture(encoded, f"AR{rank} private animated flame")
    payload_end = 18 + 64 * 64 * 4
    source_crop_bgra = _payload(raw, PRIVATE_FLAME_SOURCE_TEXELS, 4)
    source_crop_bgr = _payload(raw, PRIVATE_FLAME_SOURCE_TEXELS, 3)
    tinted_crop_bgra = _payload(encoded, PRIVATE_FLAME_SOURCE_TEXELS, 4)
    tinted_crop_bgr = _payload(encoded, PRIVATE_FLAME_SOURCE_TEXELS, 3)
    outside_changes = _outside_changes(raw, encoded)
    alpha_changes = sum(
        raw[offset + 3] != encoded[offset + 3]
        for offset in range(18, payload_end, 4)
    )
    if (
        hashlib.sha256(source).hexdigest() != NATIVE_AR5_FLAME_GWO_SHA256
        or source_info.image_type != 10
        or output_info.image_type != 2
        or (output_info.width, output_info.height, output_info.bits_per_pixel)
        != (64, 64, 32)
        or output_info.descriptor != 8
        or output_info.suffix_bytes != 26
        or encoded[0] != 0
        or encoded[1] != 0
        or encoded[:2] != raw[:2]
        or encoded[3:18] != raw[3:18]
        or encoded[payload_end:] != raw[payload_end:]
        or len(encoded) != len(raw)
        or hashlib.sha256(encoded).hexdigest() != TINTED_AR5_FLAME_RAW_SHA256[rank]
        or hashlib.sha256(source_crop_bgra).hexdigest()
        != NATIVE_AR5_FLAME_CROP_BGRA_SHA256
        or hashlib.sha256(source_crop_bgr).hexdigest()
        != NATIVE_AR5_FLAME_CROP_BGR_SHA256
        or hashlib.sha256(tinted_crop_bgra).hexdigest()
        != TINTED_AR5_FLAME_CROP_BGRA_SHA256[rank]
        or hashlib.sha256(tinted_crop_bgr).hexdigest()
        != TINTED_AR5_FLAME_CROP_BGR_SHA256[rank]
        or outside_changes != 0
        or alpha_changes != 0
        or set(encoded[21:payload_end:4]) != {255}
    ):
        raise RankEffectError("Private native-UV animated-flame contract changed")

    palette = design.palette
    colours = (palette.shadow, palette.middle, palette.highlight)
    return AuthoredCapstonePrivateFlame(
        recolour=tinted,
        rank=rank,
        source_sha256=hashlib.sha256(source).hexdigest(),
        raw_source_sha256=hashlib.sha256(raw).hexdigest(),
        source_crop_bgra_sha256=hashlib.sha256(source_crop_bgra).hexdigest(),
        source_crop_bgr_sha256=hashlib.sha256(source_crop_bgr).hexdigest(),
        tinted_crop_bgra_sha256=hashlib.sha256(tinted_crop_bgra).hexdigest(),
        tinted_crop_bgr_sha256=hashlib.sha256(tinted_crop_bgr).hexdigest(),
        output_sha256=hashlib.sha256(encoded).hexdigest(),
        source_recoloured_pixels=tinted.changed_pixels,
        sampled_pixels=PRIVATE_FLAME_COPIED_PIXELS,
        outside_footprint_changes=outside_changes,
        alpha_changes=alpha_changes,
        palette=colours,
        strength=palette.strength,
        luma_gain=design.luma_gain,
        maximum_channel=design.maximum_channel,
    )


__all__ = [
    "AuthoredCapstonePrivateFlame",
    "PRIVATE_FLAME_COPIED_PIXELS",
    "PRIVATE_FLAME_RECOLOURED_PIXELS",
    "PRIVATE_FLAME_SOURCE_TEXELS",
    "PRIVATE_FLAME_TARGET_TEXELS",
    "author_capstone_private_flame",
]

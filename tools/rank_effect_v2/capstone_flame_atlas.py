"""Author the native-UV AR5 slot-2 flame texture for AR13/AR14."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math

from rank_effect_packages.errors import RankEffectError
from rank_effect_packages.formats import validate_tga_texture

from .armor_ranks import RoleAtlasDesign
from .atlas import RecolourResult, Region, raw_truecolour_tga, recolour_luminance


NATIVE_AR5_FLAME_GWO_SHA256 = (
    "bd5d62ef65acd1187b5c04e372bede92fcac5e5a92ab853a84cc298637e6a912"
)
NATIVE_AR5_FLAME_RAW_SHA256 = (
    "8c71cd1ab6f0d7ce2681d2954ebdd7a768833b053d8fa6b42a2947c18611a446"
)
NATIVE_AR5_FLAME_TEXTURE_SHA256 = NATIVE_AR5_FLAME_GWO_SHA256
NATIVE_AR5_FLAME_CROP_BGRA_SHA256 = (
    "5afaf724a08b2a29d63f4c379dca3d8bbefef3b00b06171dd9ba82e6a097ba48"
)
NATIVE_AR5_FLAME_CROP_BGR_SHA256 = (
    "a8f89ef5462d0741dd0cb2e47e3edf68104a6fa80dc4652aeef0988d7f2761df"
)
NATIVE_AR9_ACTIVE_MASK_SHA256 = (
    "98ea34775fbc31c4f144b2d9bf4ec534643df853211a2e1137e360d909bd2a10"
)
NATIVE_AR9_FLAME_PREIMAGE_BGR_SHA256 = {
    13: "e7ae790c1d9b7e7af6c47a223237f77ad041194df8d7ed78b9b5a4d9ec457a49",
    14: "b37e5e8e4bc06c441a957d89cfd0ca981a98379fdd2bb561efbd0bb173b63d43",
}
TINTED_AR5_FLAME_RAW_SHA256 = {
    13: "f1f4139f71f159c08df6187b9386e92e10e4d51b3e3e76d57ba26c494203e2da",
    14: "8d5bed89e0337afbf0e9ccf9ee19c743170d3473eb9b9b201fbec6f96cce8b7f",
}
TINTED_AR5_FLAME_CROP_BGRA_SHA256 = {
    13: "469cf6317f2eeaedb89bfc344910d8ac24847860c7bb7d44e807a87b74da1780",
    14: "d1c39004030ce0062b58a7627760f9801067c424dc90012b463ac69da239efb7",
}
TINTED_AR5_FLAME_CROP_BGR_SHA256 = {
    13: "b8bf4f25ace7caa83e41623571b8d0b3fb97dab67d2426b08d8b65e0cc1f1f2e",
    14: "90910cb3e990d614d49b6c2ff447189ac9e52f2b9903524a9b0bd0dedcf085ab",
}
CAPSTONE_FLAME_OUTPUT_SHA256 = {
    13: "52ce75b40f339f157e22347d9dc49c0b8981a2ecc8d60b1a90d23ed88b9090f6",
    14: "c9efd5d5367b1670f4a4f74a86ce8b2caa9ea17eb50c848fb68c6e9d9b4d8349",
}

FLAME_SOURCE_TEXELS = (0, 11, 0, 32)
FLAME_TARGET_TEXELS = FLAME_SOURCE_TEXELS
FLAME_COPIED_PIXELS = 12 * 33
FLAME_SOURCE_ACTIVE_PIXELS = 278
FLAME_RECOLOURED_PIXELS = 255
FLAME_TARGET_CHANGED_PIXELS = 296
AR9_WING_ORBIT_MIN_BILINEAR_X = 20
FLAME_WING_ORBIT_GAP_COLUMNS = 8


@dataclass(frozen=True, slots=True)
class _Layout:
    width: int
    height: int
    bytes_per_pixel: int
    top_origin: bool
    right_origin: bool
    payload_end: int


@dataclass(frozen=True, slots=True)
class AuthoredCapstoneFlameAtlas:
    """AR9 canonical atlas with the native-UV animated flame footprint."""

    recolour: RecolourResult
    rank: int
    canonical_input_sha256: str
    flame_source_sha256: str
    flame_raw_source_sha256: str
    source_crop_bgra_sha256: str
    tinted_crop_bgr_sha256: str
    output_sha256: str
    source_recoloured_pixels: int
    copied_pixels: int
    target_changed_pixels: int
    prior_target_nonzero_pixels: int
    output_nonzero_pixels: int
    palette: tuple[tuple[float, float, float], ...]
    strength: float
    luma_gain: float
    maximum_channel: int

    @property
    def encoded(self) -> bytes:
        return self.recolour.encoded

    def contract_metadata(self) -> dict[str, object]:
        footprint = list(FLAME_SOURCE_TEXELS)
        return {
            "runtime_binding": "rank-canonical-gwo",
            "canonical_family": "native-ar9-with-native-uv-ar5-slot2-flame",
            "flame_geometry_family": "native-ar5-slot2-animated-flame",
            "flame_texture_source": "native-ar5-canonical-gwo",
            "ar5_canonical_gwo_used_as_texture_donor_only": True,
            "canonical_input_sha256": self.canonical_input_sha256,
            "canonical_output_sha256": self.output_sha256,
            "native_ar9_input_mask_sha256": NATIVE_AR9_ACTIVE_MASK_SHA256,
            "native_flame_gwo_sha256": self.flame_source_sha256,
            "native_flame_raw_sha256": self.flame_raw_source_sha256,
            "native_flame_crop_bgra_sha256": self.source_crop_bgra_sha256,
            "tinted_flame_crop_bgr_sha256": self.tinted_crop_bgr_sha256,
            "atlas_layout": {
                "width": 64,
                "height": 64,
                "bits_per_pixel": 24,
                "header_preserved": True,
                "footer_preserved": True,
                "untouched_pixels_preserved": 4096 - self.copied_pixels,
            },
            "packing": {
                "method": "same-native-uv-footprint",
                "source_bilinear_texels": footprint,
                "target_bilinear_texels": footprint,
                "uv_translation": [0.0, 0.0],
                "scale": [1.0, 1.0],
                "native_uv_preserved": True,
                "copied_pixels": self.copied_pixels,
                "target_changed_pixels": self.target_changed_pixels,
                "source_recoloured_pixels": self.source_recoloured_pixels,
                "source_alpha": "all-255; safely omitted by 24-bit canonical",
                "prior_target_nonzero_pixels": self.prior_target_nonzero_pixels,
            },
            "collision_proof": {
                "flame_max_bilinear_x": FLAME_SOURCE_TEXELS[1],
                "wing_orbit_min_bilinear_x": AR9_WING_ORBIT_MIN_BILINEAR_X,
                "separating_texel_columns": FLAME_WING_ORBIT_GAP_COLUMNS,
                "disjoint": FLAME_SOURCE_TEXELS[1] < AR9_WING_ORBIT_MIN_BILINEAR_X,
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
            "output_nonzero_pixels": self.output_nonzero_pixels,
        }


def _layout(data: bytes, label: str, bits: int, descriptor: int) -> _Layout:
    info = validate_tga_texture(data, label)
    if (
        data[0] != 0
        or data[1] != 0
        or info.image_type != 2
        or (info.width, info.height, info.bits_per_pixel) != (64, 64, bits)
        or info.descriptor != descriptor
        or info.suffix_bytes != 26
    ):
        raise RankEffectError(f"Unexpected animated-flame atlas layout: {label}")
    bytes_per_pixel = bits // 8
    return _Layout(
        64,
        64,
        bytes_per_pixel,
        bool(info.descriptor & 0x20),
        bool(info.descriptor & 0x10),
        18 + 4096 * bytes_per_pixel,
    )


def _offset(layout: _Layout, x: int, y: int) -> int:
    source_y = y if layout.top_origin else layout.height - 1 - y
    source_x = layout.width - 1 - x if layout.right_origin else x
    return 18 + (source_y * layout.width + source_x) * layout.bytes_per_pixel


def _coordinates(rectangle: tuple[int, int, int, int]):
    minimum_x, maximum_x, minimum_y, maximum_y = rectangle
    for y in range(minimum_y, maximum_y + 1):
        for x in range(minimum_x, maximum_x + 1):
            yield x, y


def _payload(
    data: bytes,
    layout: _Layout,
    rectangle: tuple[int, int, int, int],
    channels: int,
) -> bytes:
    return b"".join(
        data[offset : offset + channels]
        for x, y in _coordinates(rectangle)
        for offset in (_offset(layout, x, y),)
    )


def _active_mask_sha256(data: bytes, layout: _Layout) -> str:
    mask = bytes(
        int(max(data[offset : offset + 3]) > 0)
        for offset in range(18, layout.payload_end, layout.bytes_per_pixel)
    )
    return hashlib.sha256(mask).hexdigest()


def _nonzero_pixels(data: bytes, layout: _Layout) -> int:
    return sum(
        max(data[offset : offset + 3]) > 0
        for offset in range(18, layout.payload_end, layout.bytes_per_pixel)
    )


def _verify_untouched(
    before: bytes,
    after: bytes,
    layout: _Layout,
    changed_rectangle: tuple[int, int, int, int],
) -> None:
    target = set(_coordinates(changed_rectangle))
    for y in range(layout.height):
        for x in range(layout.width):
            if (x, y) in target:
                continue
            offset = _offset(layout, x, y)
            end = offset + layout.bytes_per_pixel
            if before[offset:end] != after[offset:end]:
                raise RankEffectError("Animated flame changed an unrelated atlas pixel")


def _validate_design(rank: int, design: RoleAtlasDesign) -> None:
    if rank not in (13, 14) or not isinstance(design, RoleAtlasDesign):
        raise RankEffectError(f"Animated-flame role design is invalid for AR{rank}")
    palette = design.palette
    colours = (palette.shadow, palette.middle, palette.highlight)
    if (
        palette.region != (0.0, 1.0, 0.0, 1.0)
        or any(
            len(colour) != 3
            or any(not math.isfinite(value) or not 0.0 <= value <= 1.0 for value in colour)
            for colour in colours
        )
        or not math.isfinite(palette.strength)
        or not 0.0 <= palette.strength <= 1.0
        or not math.isfinite(design.luma_gain)
        or not isinstance(design.maximum_channel, int)
    ):
        raise RankEffectError("Animated-flame palette is invalid")


def decode_native_ar5_flame(source: bytes) -> bytes:
    """Decode and pin the stock AR5 canonical GWO used by slot 2."""

    info = validate_tga_texture(source, "native AR5 flame GWO")
    if (
        hashlib.sha256(source).hexdigest() != NATIVE_AR5_FLAME_GWO_SHA256
        or source[0] != 0
        or source[1] != 0
        or info.image_type != 10
        or (info.width, info.height, info.bits_per_pixel) != (64, 64, 32)
        or info.descriptor != 8
        or info.suffix_bytes != 26
    ):
        raise RankEffectError("Native AR5 animated-flame GWO changed")
    raw = raw_truecolour_tga(source, "native AR5 flame GWO")
    layout = _layout(raw, "decoded native AR5 flame GWO", 32, 8)
    crop_bgra = _payload(raw, layout, FLAME_SOURCE_TEXELS, 4)
    crop_bgr = _payload(raw, layout, FLAME_SOURCE_TEXELS, 3)
    alpha = raw[21 : layout.payload_end : 4]
    crop_nonzero = sum(
        max(crop_bgra[index : index + 3]) > 0
        for index in range(0, len(crop_bgra), 4)
    )
    if (
        hashlib.sha256(raw).hexdigest() != NATIVE_AR5_FLAME_RAW_SHA256
        or len(crop_bgra) != FLAME_COPIED_PIXELS * 4
        or hashlib.sha256(crop_bgra).hexdigest()
        != NATIVE_AR5_FLAME_CROP_BGRA_SHA256
        or hashlib.sha256(crop_bgr).hexdigest() != NATIVE_AR5_FLAME_CROP_BGR_SHA256
        or set(alpha) != {255}
        or crop_nonzero != FLAME_SOURCE_ACTIVE_PIXELS
    ):
        raise RankEffectError("Decoded AR5 animated-flame texture contract changed")
    return raw


def recolour_native_ar5_flame(
    source: bytes,
    *,
    rank: int,
    design: RoleAtlasDesign,
) -> RecolourResult:
    """Decode and recolour only the slot-2 native-UV sampling footprint."""

    _validate_design(rank, design)
    raw = decode_native_ar5_flame(source)
    layout = _layout(raw, "decoded native AR5 animated flame", 32, 8)
    palette = design.palette
    tinted = recolour_luminance(
        raw,
        Region(0.0, 11 / 63, 0.0, 32 / 63),
        palette.shadow,
        palette.middle,
        palette.highlight,
        strength=palette.strength,
        preserve_luma=True,
        luma_gain=design.luma_gain,
        maximum_channel=design.maximum_channel,
    )
    tinted_layout = _layout(tinted.encoded, "tinted AR5 animated flame", 32, 8)
    crop_bgra = _payload(tinted.encoded, tinted_layout, FLAME_SOURCE_TEXELS, 4)
    crop_bgr = _payload(tinted.encoded, tinted_layout, FLAME_SOURCE_TEXELS, 3)
    if (
        tinted.changed_pixels != FLAME_RECOLOURED_PIXELS
        or tinted.outside_region_changes != 0
        or tinted.alpha_changes != 0
        or len(tinted.encoded) != len(raw)
        or tinted.encoded[:18] != raw[:18]
        or tinted.encoded[layout.payload_end :] != raw[layout.payload_end :]
        or tinted.encoded[21 : layout.payload_end : 4] != raw[21 : layout.payload_end : 4]
        or hashlib.sha256(tinted.encoded).hexdigest()
        != TINTED_AR5_FLAME_RAW_SHA256[rank]
        or hashlib.sha256(crop_bgra).hexdigest()
        != TINTED_AR5_FLAME_CROP_BGRA_SHA256[rank]
        or hashlib.sha256(crop_bgr).hexdigest()
        != TINTED_AR5_FLAME_CROP_BGR_SHA256[rank]
    ):
        raise RankEffectError("AR5 animated-flame recolour contract changed")
    _verify_untouched(raw, tinted.encoded, layout, FLAME_SOURCE_TEXELS)
    return tinted


def author_capstone_flame_atlas(
    canonical: bytes,
    flame_texture: bytes,
    *,
    rank: int,
    design: RoleAtlasDesign,
) -> AuthoredCapstoneFlameAtlas:
    """Copy the tinted native slot-2 footprint into the same AR9 UV cell."""

    tinted = recolour_native_ar5_flame(flame_texture, rank=rank, design=design)
    canonical_layout = _layout(canonical, f"AR{rank} canonical", 24, 0)
    tinted_layout = _layout(tinted.encoded, "tinted AR5 animated flame", 32, 8)
    canonical_sha256 = hashlib.sha256(canonical).hexdigest()
    source_sha256 = hashlib.sha256(flame_texture).hexdigest()
    if _active_mask_sha256(canonical, canonical_layout) != NATIVE_AR9_ACTIVE_MASK_SHA256:
        raise RankEffectError("Capstone canonical is not the approved AR9 mask family")
    target_before = _payload(canonical, canonical_layout, FLAME_TARGET_TEXELS, 3)
    if (
        hashlib.sha256(target_before).hexdigest()
        != NATIVE_AR9_FLAME_PREIMAGE_BGR_SHA256[rank]
    ):
        raise RankEffectError("AR9 canonical animated-flame preimage changed")
    tinted_bgr = _payload(tinted.encoded, tinted_layout, FLAME_SOURCE_TEXELS, 3)

    output = bytearray(canonical)
    target_changed = 0
    for x, y in _coordinates(FLAME_SOURCE_TEXELS):
        source_offset = _offset(tinted_layout, x, y)
        target_offset = _offset(canonical_layout, x, y)
        replacement = tinted.encoded[source_offset : source_offset + 3]
        target_changed += output[target_offset : target_offset + 3] != replacement
        output[target_offset : target_offset + 3] = replacement
    encoded = bytes(output)
    if (
        target_changed != FLAME_TARGET_CHANGED_PIXELS
        or len(encoded) != len(canonical)
        or encoded[:18] != canonical[:18]
        or encoded[canonical_layout.payload_end :]
        != canonical[canonical_layout.payload_end :]
        or _payload(encoded, canonical_layout, FLAME_TARGET_TEXELS, 3)
        != tinted_bgr
        or hashlib.sha256(encoded).hexdigest() != CAPSTONE_FLAME_OUTPUT_SHA256[rank]
    ):
        raise RankEffectError("AR9 native-UV flame packing contract changed")
    _verify_untouched(canonical, encoded, canonical_layout, FLAME_TARGET_TEXELS)

    palette = design.palette
    colours = (palette.shadow, palette.middle, palette.highlight)
    result = RecolourResult(encoded, target_changed, 0, 0)
    return AuthoredCapstoneFlameAtlas(
        recolour=result,
        rank=rank,
        canonical_input_sha256=canonical_sha256,
        flame_source_sha256=source_sha256,
        flame_raw_source_sha256=NATIVE_AR5_FLAME_RAW_SHA256,
        source_crop_bgra_sha256=NATIVE_AR5_FLAME_CROP_BGRA_SHA256,
        tinted_crop_bgr_sha256=hashlib.sha256(tinted_bgr).hexdigest(),
        output_sha256=hashlib.sha256(encoded).hexdigest(),
        source_recoloured_pixels=tinted.changed_pixels,
        copied_pixels=FLAME_COPIED_PIXELS,
        target_changed_pixels=target_changed,
        prior_target_nonzero_pixels=sum(
            max(target_before[index : index + 3]) > 0
            for index in range(0, len(target_before), 3)
        ),
        output_nonzero_pixels=_nonzero_pixels(encoded, canonical_layout),
        palette=colours,
        strength=palette.strength,
        luma_gain=design.luma_gain,
        maximum_channel=design.maximum_channel,
    )


__all__ = [
    "AR9_WING_ORBIT_MIN_BILINEAR_X",
    "AuthoredCapstoneFlameAtlas",
    "CAPSTONE_FLAME_OUTPUT_SHA256",
    "FLAME_COPIED_PIXELS",
    "FLAME_RECOLOURED_PIXELS",
    "FLAME_SOURCE_TEXELS",
    "FLAME_TARGET_TEXELS",
    "FLAME_TARGET_CHANGED_PIXELS",
    "FLAME_WING_ORBIT_GAP_COLUMNS",
    "NATIVE_AR5_FLAME_CROP_BGRA_SHA256",
    "NATIVE_AR5_FLAME_CROP_BGR_SHA256",
    "NATIVE_AR5_FLAME_GWO_SHA256",
    "NATIVE_AR5_FLAME_RAW_SHA256",
    "NATIVE_AR5_FLAME_TEXTURE_SHA256",
    "NATIVE_AR9_ACTIVE_MASK_SHA256",
    "NATIVE_AR9_FLAME_PREIMAGE_BGR_SHA256",
    "TINTED_AR5_FLAME_CROP_BGRA_SHA256",
    "TINTED_AR5_FLAME_CROP_BGR_SHA256",
    "TINTED_AR5_FLAME_RAW_SHA256",
    "author_capstone_flame_atlas",
    "decode_native_ar5_flame",
    "recolour_native_ar5_flame",
]

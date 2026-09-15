"""Conservative recolouring of stock 64x64 TGA effect atlases."""

from __future__ import annotations

from dataclasses import dataclass
import math
import struct

from rank_effect_packages.errors import RankEffectError
from rank_effect_packages.formats import validate_tga_texture


Rgb = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class Region:
    minimum_u: float
    maximum_u: float
    minimum_v: float
    maximum_v: float

    def contains(self, u: float, v: float) -> bool:
        return (
            self.minimum_u <= u <= self.maximum_u
            and self.minimum_v <= v <= self.maximum_v
        )


@dataclass(frozen=True, slots=True)
class RecolourResult:
    encoded: bytes
    changed_pixels: int
    outside_region_changes: int
    alpha_changes: int


def raw_truecolour_tga(source: bytes, label: str) -> bytes:
    """Return an equivalent identifier-free raw TGA for raw or RLE input."""

    info = validate_tga_texture(source, label)
    if source[0] != 0 or source[1] != 0:
        raise RankEffectError(f"Effect atlas must not use an identifier/map: {label}")
    if info.image_type == 2:
        return source
    if info.image_type != 10:
        raise RankEffectError(f"Effect atlas is not true-colour RLE: {label}")

    bytes_per_pixel = info.bits_per_pixel // 8
    total_pixels = info.width * info.height
    position = 18
    decoded = bytearray()
    while len(decoded) // bytes_per_pixel < total_pixels:
        if position >= len(source):
            raise RankEffectError(f"Truncated RLE packet stream: {label}")
        packet = source[position]
        position += 1
        count = (packet & 0x7F) + 1
        if len(decoded) // bytes_per_pixel + count > total_pixels:
            raise RankEffectError(f"RLE packet overruns atlas: {label}")
        if packet & 0x80:
            pixel = source[position : position + bytes_per_pixel]
            if len(pixel) != bytes_per_pixel:
                raise RankEffectError(f"Truncated RLE pixel: {label}")
            position += bytes_per_pixel
            decoded.extend(pixel * count)
        else:
            size = count * bytes_per_pixel
            payload = source[position : position + size]
            if len(payload) != size:
                raise RankEffectError(f"Truncated raw RLE packet: {label}")
            position += size
            decoded.extend(payload)

    header = bytearray(source[:18])
    header[2] = 2
    output = bytes(header) + bytes(decoded) + source[position:]
    result = validate_tga_texture(output, f"{label}:raw")
    if (
        result.image_type != 2
        or result.width != info.width
        or result.height != info.height
        or result.bits_per_pixel != info.bits_per_pixel
        or result.descriptor != info.descriptor
    ):
        raise RankEffectError(f"Decoded TGA layout changed: {label}")
    return output


def _mix(left: Rgb, right: Rgb, amount: float) -> Rgb:
    return tuple(a + (b - a) * amount for a, b in zip(left, right))  # type: ignore[return-value]


def _palette(value: float, shadow: Rgb, middle: Rgb, highlight: Rgb) -> Rgb:
    if value <= 0.55:
        return _mix(shadow, middle, value / 0.55)
    return _mix(middle, highlight, (value - 0.55) / 0.45)


def recolour_luminance(
    source: bytes,
    region: Region,
    shadow: Rgb,
    middle: Rgb,
    highlight: Rgb,
    *,
    strength: float = 0.88,
    additive_glow: bool = False,
    preserve_luma: bool = False,
    luma_gain: float = 1.0,
    maximum_channel: int = 255,
) -> RecolourResult:
    """Tint sampled detail while retaining stock luminance and exact alpha.

    ``additive_glow`` uses a bounded exposure lift and normalised tint for the
    legacy armor renderer. This retains detail without multiplying already-dim
    source pixels by a dark palette stop a second time.

    ``preserve_luma`` replaces hue while retaining each source pixel's
    Rec. 709 luminance.  It is intended for an exact silhouette clone where an
    exposure change would make the effect appear larger or obscure the model.
    ``luma_gain`` and ``maximum_channel`` provide a bounded role hierarchy for
    small private effects without invoking the additive exposure curve.
    """

    info = validate_tga_texture(source, "role-aware stock atlas")
    if info.width != 64 or info.height != 64:
        raise RankEffectError("Rank-effect prototype requires a 64x64 stock atlas")
    if not 0.0 <= strength <= 1.0:
        raise RankEffectError("Recolour strength must be within 0..1")
    if additive_glow and preserve_luma:
        raise RankEffectError("Additive glow and luma preservation are exclusive")
    if not preserve_luma and not math.isclose(luma_gain, 1.0):
        raise RankEffectError("Luma gain requires luma-preserving recolouring")
    if not 0.5 <= luma_gain <= 1.25:
        raise RankEffectError("Luma gain is outside the reviewed 0.5..1.25 range")
    if not isinstance(maximum_channel, int) or not 1 <= maximum_channel <= 255:
        raise RankEffectError("Maximum output channel must be an integer within 1..255")
    header = source[:18]
    if header[0] != 0 or header[1] != 0 or header[2] != 2:
        raise RankEffectError("Only raw, identifier-free true-colour TGA is supported")
    bytes_per_pixel = info.bits_per_pixel // 8
    payload_end = 18 + info.width * info.height * bytes_per_pixel
    target = bytearray(source)
    top_origin = bool(header[17] & 0x20)
    right_origin = bool(header[17] & 0x10)
    changed = 0
    alpha_changes = 0

    for y in range(info.height):
        source_y = y if top_origin else info.height - 1 - y
        v = y / (info.height - 1)
        for x in range(info.width):
            source_x = info.width - 1 - x if right_origin else x
            u = x / (info.width - 1)
            if not region.contains(u, v):
                continue
            offset = 18 + (source_y * info.width + source_x) * bytes_per_pixel
            blue, green, red = target[offset : offset + 3]
            alpha = target[offset + 3] if bytes_per_pixel == 4 else 255
            value = max(red, green, blue) / 255.0
            if value <= 0.015 or alpha == 0:
                continue
            palette_position = value if additive_glow or preserve_luma else math.sqrt(value)
            colour = _palette(palette_position, shadow, middle, highlight)
            output_value = value
            if additive_glow:
                peak = max(colour)
                if peak <= 0.0:
                    raise RankEffectError("Additive glow cannot use a black palette")
                colour = tuple(channel / peak for channel in colour)  # type: ignore[assignment]
                lifted = value**0.76
                output_value = 4.0 * lifted / (lifted + 3.0)
            if preserve_luma:
                source_luma = (
                    0.2126 * red + 0.7152 * green + 0.0722 * blue
                ) / 255.0
                tint_luma = (
                    0.2126 * colour[0]
                    + 0.7152 * colour[1]
                    + 0.0722 * colour[2]
                )
                if tint_luma <= 0.0:
                    raise RankEffectError("Luma preservation cannot use a black palette")
                output_value = source_luma * luma_gain / tint_luma
            desired = tuple(round(255.0 * channel * output_value) for channel in colour)
            result = tuple(
                max(0, min(maximum_channel, round(old + (new - old) * strength)))
                for old, new in zip((red, green, blue), desired)
            )
            replacement = bytes((result[2], result[1], result[0]))
            if replacement != target[offset : offset + 3]:
                changed += 1
                target[offset : offset + 3] = replacement
            if bytes_per_pixel == 4 and target[offset + 3] != alpha:
                alpha_changes += 1

    if bytes(target[payload_end:]) != source[payload_end:]:
        raise RankEffectError("TGA footer or trailing metadata changed")
    return RecolourResult(bytes(target), changed, 0, alpha_changes)

"""Pack bounded sources into existing cells without changing neighboring art."""
from __future__ import annotations

import io
import json
from pathlib import Path
import textwrap

import PIL
from PIL import Image, ImageDraw

from level5_forge_icons.common import InstallError, Sprite, SpriteSpec
from level5_forge_icons.tga_atlas import make_desired_pixels, patch_atlas, validate_generated_atlas
from .catalog import json_bytes, parse_baseline, read_baselines, read_catalog, sha256

PILLOW_VERSION = "12.0.0"


def png_bytes(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, "PNG", compress_level=9)
    return output.getvalue()


def resize_source(data: bytes, label: str) -> Image.Image:
    with Image.open(io.BytesIO(data)) as opened:
        if (opened.mode not in ("RGB", "RGBA") or opened.width != opened.height
                or not 36 <= opened.width <= 4096):
            raise InstallError(f"Expected square RGB/RGBA artwork, 36..4096px: {label}")
        image = opened.convert("RGBA")
    if not image.getchannel("A").getbbox():
        raise InstallError(f"Artwork has no visible pixels: {label}")
    # Premultiplied alpha avoids black fringes; retain the artist's framing.
    return image.convert("RGBa").resize((36, 36), Image.Resampling.LANCZOS).convert("RGBA")


def make_preview(entries: list[dict], icons: dict[str, Image.Image]) -> Image.Image:
    columns, tile_width, tile_height = 5, 232, 224
    rows = (len(entries) + columns - 1) // columns
    sheet = Image.new("RGBA", (columns * tile_width, rows * tile_height + 30), (22, 26, 35, 255))
    draw = ImageDraw.Draw(sheet)
    draw.text((10, 8), "Holy Stones and Spirits | 4x preview + actual 36px size", fill="white")
    for index, entry in enumerate(entries):
        x = index % columns * tile_width + 10
        y = index // columns * tile_height + 34
        icon = icons[entry["slug"]]
        sheet.alpha_composite(icon.resize((144, 144), Image.Resampling.NEAREST), (x, y))
        sheet.alpha_composite(icon, (x + 167, y + 108))
        label = f"{entry['item_id']}  {entry['name']}"
        draw.multiline_text((x, y + 153), "\n".join(textwrap.wrap(label, 30)), fill="white", spacing=4)
    return sheet


def pack(root: Path) -> dict[Path, bytes]:
    if PIL.__version__ != PILLOW_VERSION:
        raise InstallError(f"Reproducible artwork packing requires Pillow=={PILLOW_VERSION}")
    entries = read_catalog(root)
    baseline_data = read_baselines(root)
    generation_bytes = (root / "generation.json").read_bytes()
    generation = json.loads(generation_bytes)
    generated_entries = generation.get("entries", [])
    by_slug = {e.get("slug"): e for e in generated_entries}
    if len(by_slug) != len(generated_entries) or set(by_slug) != {e["slug"] for e in entries}:
        raise InstallError("Generation provenance must contain the exact 27 unique artwork slugs")
    output = root / "generated"
    outputs: dict[Path, bytes] = {}
    icons: dict[str, Image.Image] = {}
    sprites: dict[str, list[Sprite]] = {name: [] for name in baseline_data}
    source_records = []
    for entry in entries:
        slug = entry["slug"]
        data = (root / "source" / f"{slug}.png").read_bytes()
        source_hash = sha256(data)
        if by_slug[slug].get("source_sha256") != source_hash:
            raise InstallError(f"Generated source SHA256 differs from its provenance: {slug}")
        icon = resize_source(data, slug)
        icons[slug] = icon
        filename = f"{slug}-36.png"
        prepared = png_bytes(icon)
        outputs[output / filename] = prepared
        sprites[entry["atlas"]].append(Sprite(
            SpriteSpec(filename, entry["x"], entry["y"]), icon.tobytes("raw", "BGRA"), sha256(prepared)))
        source_records.append({"slug": slug, "source_sha256": source_hash, "icon_sha256": sha256(prepared)})
    for name, data in baseline_data.items():
        base = parse_baseline(data, name)
        desired, _ = make_desired_pixels(base, tuple(sprites[name]))
        encoded = patch_atlas(base, desired)
        decoded = validate_generated_atlas(base, encoded, desired, name)
        # Independent decoder also verifies pixel orientation and alpha.
        with Image.open(io.BytesIO(encoded)) as reopened:
            if reopened.convert("RGBA").tobytes("raw", "BGRA", 0, -1) != decoded.pixels:
                raise InstallError(f"Independent TGA decode differs: {name}")
        outputs[output / name] = encoded
    strip = Image.new("RGBA", (36 * len(entries), 36))
    for index, entry in enumerate(entries):
        strip.paste(icons[entry["slug"]], (index * 36, 0))
    outputs[output / "icons-native.png"] = png_bytes(strip)
    outputs[output / "preview.png"] = png_bytes(make_preview(entries, icons))
    # The mounted Zephyr display reads the middle 20px of its stone cell.
    outputs[output / "zephyr-socket-20.png"] = png_bytes(icons["zephyr-holy-stone"].crop((8, 8, 28, 28)))
    release = {
        "schema_version": 1, "pillow_version": PILLOW_VERSION,
        "resampling": "whole square, premultiplied-alpha Lanczos to 36px; no added padding",
        "manifest_sha256": sha256((root / "manifest.json").read_bytes()),
        "generation_sha256": sha256(generation_bytes), "sources": source_records,
        "outputs": {path.name: {"bytes": len(data), "sha256": sha256(data)} for path, data in outputs.items()},
    }
    outputs[output / "release.json"] = json_bytes(release)
    return outputs

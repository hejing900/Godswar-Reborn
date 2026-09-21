"""Shared deterministic packing and validation for dedicated item icon atlases."""
from __future__ import annotations

import json
from pathlib import Path

from holy_stone_icons.catalog import json_bytes, sha256
from level5_forge_icons.common import InstallError
from level5_forge_icons.png_assets import read_png_rgba
from level5_forge_icons.tga_atlas import display_pixel_index, parse_tga


def pack_catalog(root: Path, entries: list[dict], atlas_name: str, title: str) -> dict[Path, bytes]:
    # Publication verification intentionally uses only the standard library;
    # Pillow is needed solely when preparing new artwork.
    import PIL
    from PIL import Image, ImageDraw
    from holy_stone_icons.packing import PILLOW_VERSION, png_bytes, resize_source
    from PrepareHolySuitWareIcons import encode_native, native_format

    if PIL.__version__ != PILLOW_VERSION:
        raise InstallError(f"Reproducible artwork packing requires Pillow=={PILLOW_VERSION}")
    template, format_record, _ = native_format(root / "source", None)
    generation_bytes = (root / "generation.json").read_bytes()
    records = json.loads(generation_bytes).get("entries", [])
    by_slug = {entry.get("slug"): entry for entry in records}
    if len(by_slug) != len(records) or set(by_slug) != {e["slug"] for e in entries}:
        raise InstallError("Generation provenance must cover the exact artwork slugs")
    atlas = Image.new("RGBA", (1024, 1024))
    strip = Image.new("RGBA", (36 * len(entries), 36))
    preview = Image.new("RGBA", (1040, ((len(entries) + 3) // 4) * 265 + 30), (22, 26, 35, 255))
    draw = ImageDraw.Draw(preview)
    draw.text((12, 8), title + " | 5x preview + native 36px size", fill="white")
    output = root / "generated"
    outputs, sources = {}, []
    for index, entry in enumerate(entries):
        slug = entry["slug"]
        data = (root / "source" / f"{slug}.png").read_bytes()
        if by_slug[slug].get("source_sha256") != sha256(data):
            raise InstallError(f"Artwork source differs from its generation provenance: {slug}")
        icon = resize_source(data, slug)
        prepared = png_bytes(icon)
        outputs[output / f"{slug}-36.png"] = prepared
        atlas.paste(icon, (entry["x"], entry["y"]))
        strip.paste(icon, (index * 36, 0))
        x, y = index % 4 * 260 + 12, index // 4 * 265 + 36
        preview.alpha_composite(icon.resize((180, 180), Image.Resampling.NEAREST), (x, y))
        preview.alpha_composite(icon, (x + 204, y + 144))
        draw.text((x, y + 192), entry["name"], fill="white")
        draw.text((x, y + 211), f"Item {entry['item_id']}", fill=(178, 185, 201))
        sources.append({"slug": slug, "source_sha256": sha256(data),
                        "icon_sha256": sha256(prepared)})
    outputs[output / atlas_name] = encode_native(atlas, template)
    outputs[output / "icons-native.png"] = png_bytes(strip)
    outputs[output / "preview.png"] = png_bytes(preview)
    release = {"schema_version": 1, "pillow_version": PILLOW_VERSION,
               "resampling": "whole square, premultiplied-alpha Lanczos to 36px; no added padding",
               "manifest_sha256": sha256((root / "manifest.json").read_bytes()),
               "generation_sha256": sha256(generation_bytes),
               "native_format_sha256": format_record["sha256"], "sources": sources,
               "outputs": {path.name: {"bytes": len(data), "sha256": sha256(data)}
                           for path, data in outputs.items()}}
    outputs[output / "release.json"] = json_bytes(release)
    return outputs


def verify_catalog_release(root: Path, entries: list[dict], atlas_name: str) -> bytes:
    release = json.loads((root / "generated/release.json").read_bytes())
    generation = (root / "generation.json").read_bytes()
    format_bytes = (root / "source/native-tga-format.bin").read_bytes()
    if (release.get("schema_version") != 1
            or release.get("manifest_sha256") != sha256((root / "manifest.json").read_bytes())
            or release.get("generation_sha256") != sha256(generation)
            or release.get("native_format_sha256") != sha256(format_bytes)):
        raise InstallError("Prepared item artwork release has stale provenance")
    sources = release.get("sources", [])
    generated = json.loads(generation).get("entries", [])
    source_map = {e["slug"]: e for e in sources}
    generated_map = {e["slug"]: e for e in generated}
    slugs = {e["slug"] for e in entries}
    if (len(source_map) != len(sources) or len(generated_map) != len(generated)
            or set(source_map) != slugs or set(generated_map) != slugs):
        raise InstallError("Prepared item artwork release must contain the exact unique sources")
    outputs = release.get("outputs", {})
    if set(outputs) != {atlas_name, "preview.png", "icons-native.png"} | {s + "-36.png" for s in slugs}:
        raise InstallError("Prepared item artwork output inventory differs from the expected release")
    for name, record in outputs.items():
        data = (root / "generated" / name).read_bytes()
        if len(data) != record["bytes"] or sha256(data) != record["sha256"]:
            raise InstallError(f"Prepared item artwork output changed: {name}")
    atlas_bytes = (root / "generated" / atlas_name).read_bytes()
    atlas = parse_tga(atlas_bytes, atlas_name)
    if atlas.prefix + atlas.extension != format_bytes:
        raise InstallError("Prepared item artwork atlas changed native container metadata")
    expected = bytearray(1024 * 1024 * 4)
    for entry in entries:
        slug = entry["slug"]
        source_hash = sha256((root / "source" / (slug + ".png")).read_bytes())
        if (source_hash != source_map[slug]["source_sha256"]
                or source_hash != generated_map[slug]["source_sha256"]):
            raise InstallError(f"Item artwork source changed: {slug}")
        filename = slug + "-36.png"
        if source_map[slug]["icon_sha256"] != outputs[filename]["sha256"]:
            raise InstallError(f"Item artwork icon identity changed: {slug}")
        width, height, rgba = read_png_rgba(root / "generated" / filename)
        if (width, height) != (36, 36):
            raise InstallError(f"Expected native 36px item artwork icon: {slug}")
        for y in range(36):
            for x in range(36):
                source = (y * 36 + x) * 4
                target = display_pixel_index(atlas, entry["x"] + x, entry["y"] + y) * 4
                r, g, b, a = rgba[source:source + 4]
                expected[target:target + 4] = bytes((b, g, r, a))
    if atlas.pixels != bytes(expected):
        raise InstallError("Item artwork atlas pixels differ from the exact icons and transparent background")
    return atlas_bytes

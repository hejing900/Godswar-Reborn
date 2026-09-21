"""Pack Bloodfang's original portrait into its exclusively owned native cell.

The pet roster and summoned HUD use Icon2.gwo. Only species 46's two
PetInfo.IconPos fields and that atlas's 36x36 cell may change. Source artwork
is supplied externally; this module only resizes and packs its pixels.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from .portrait_pixels import decode, resample_bgra
from holy_suit_tiers.text import Document, PatchError
from holy_suit_tiers.transaction import Change, contained
from level5_forge_icons.common import InstallError
from level5_forge_icons.tga_atlas import (
    display_pixel_index, parse_tga, patch_atlas, validate_generated_atlas,
)

LOCALES = ('en_us', 'zh_cn')
ATLAS = 'Icon2.gwo'
POSITION = (396, 864)
ICON_POS = '396,864'
PREVIOUS_ICON_POS = '864,900'
SIZE = 36
EMPTY_CELL_SHA256 = '523862a510945f2c2fd57aab7df19831a15603bd4a0d99c2515a79a90b3813f9'
ATTRIBUTES = re.compile(r'''([\w:]+)\s*=\s*["']([^"']*)["']''')
PAIRS = re.compile(r'(?<![\d.])(?=(\d{1,4})\s*,\s*(\d{1,4})(?![\d.]))')


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class Reference:
    path: str
    source: str
    x: int
    y: int
    width: int = SIZE
    height: int = SIZE

    def overlaps(self, position=POSITION) -> bool:
        x, y = position
        return (self.x < x + SIZE and self.x + self.width > x and
                self.y < y + SIZE and self.y + self.height > y)


def _scan_text(path: Path) -> str:
    raw = path.read_bytes()
    if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
        return raw.decode('utf-16', errors='strict')
    # XML/Lua coordinate syntax is ASCII. Latin1 preserves every ASCII byte
    # even when a legacy file has GB2312 comments or a misleading declaration.
    return raw.decode('latin1')


def _dimensions(value: str) -> tuple[int, int]:
    try:
        left, top, right, bottom = (int(part.strip()) for part in value.split(','))
    except (ValueError, TypeError):
        return SIZE, SIZE
    return max(SIZE, right - left), max(SIZE, bottom - top)


def scan_references(client: Path) -> tuple[list[Reference], int]:
    """Inspect all locale XML/Lua, conservatively including comments.

    Icon/IconPos coordinates are considered occupied regardless of atlas;
    explicit UI TexturePos/BtnTopPos are included for Icon2 and honor their
    display rectangle. All literal Lua coordinate pairs are included even
    when their texture is selected dynamically. Numeric equipment stat lists
    are not texture coordinates and are intentionally not interpreted as such.
    """
    references = []
    count = 0
    directory = contained(client, client / 'Localization')
    for path in sorted(directory.rglob('*')):
        if path.suffix.lower() not in ('.xml', '.lua'):
            continue
        contained(client, path)
        count += 1
        text = _scan_text(path)
        if path.suffix.lower() == '.lua':
            values = [('Lua literal', text, SIZE, SIZE)]
        else:
            values = []
            for match in re.finditer(r'<[^<>]+>', text):
                tag = match.group()
                attrs = dict(ATTRIBUTES.findall(tag))
                own = (path.name == 'Pet.xml' and path.parent.name == 'Sys' and
                       re.match(r'<PetInfo\s', tag) and
                       attrs.get('Name') in ('Pet46_0', 'Pet46_1'))
                for name, value in attrs.items():
                    key = name.lower()
                    if key in ('icon', 'iconpos') and not own:
                        values.append((name, value, SIZE, SIZE))
                    elif key in ('texturepos', 'btntoppos'):
                        texture = attrs.get('Texture' if key == 'texturepos' else 'BtnTopTexture', '')
                        if texture.replace('\\', '/').split('/')[-1].lower() == ATLAS.lower():
                            rectangle = attrs.get('Rectangle' if key == 'texturepos' else 'BtnTopRect', '')
                            values.append((name, value, *_dimensions(rectangle)))
        for source, value, width, height in values:
            for match in PAIRS.finditer(value):
                x, y = map(int, match.groups())
                if x < 1024 and y < 1024:
                    references.append(Reference(str(path.relative_to(client)), source,
                                                x, y, width, height))
    return references, count


def normalized_sprite(png: bytes, expected_sha256: str) -> bytes:
    """Return display-order BGRA; no art is generated or recolored here."""
    if sha256(png) != expected_sha256.lower():
        raise PatchError('Original portrait source hash changed')
    width, rgba = decode(png)
    return resample_bgra(width, rgba)


def cell_pixels(atlas) -> bytes:
    x, y = POSITION
    return b''.join(atlas.pixels[index * 4:index * 4 + 4]
                   for row in range(SIZE) for col in range(SIZE)
                   for index in [display_pixel_index(atlas, x + col, y + row)])


def pack(atlas_data: bytes, sprite: bytes, *, allowed_predecessors=frozenset()) -> bytes:
    if len(sprite) != SIZE * SIZE * 4:
        raise PatchError('Portrait sprite must contain exactly 36x36 BGRA pixels')
    try:
        atlas = parse_tga(atlas_data, ATLAS)
        existing = cell_pixels(atlas)
        if existing == sprite:
            return atlas_data
        if sha256(existing) not in {EMPTY_CELL_SHA256, *allowed_predecessors}:
            raise PatchError('Bloodfang portrait cell is occupied by unknown pixels')
        x, y = POSITION
        desired = {display_pixel_index(atlas, x + col, y + row):
                   sprite[(row * SIZE + col) * 4:(row * SIZE + col + 1) * 4]
                   for row in range(SIZE) for col in range(SIZE)}
        output = patch_atlas(atlas, desired)
        validate_generated_atlas(atlas, output, desired, ATLAS)
        return output
    except InstallError as error:
        raise PatchError(str(error)) from error


def pet_icons(doc: Document) -> str:
    tree = ET.fromstring(doc.text)
    if tree.tag != 'PetModel':
        raise PatchError('Unexpected pet model configuration')
    result = doc.text
    for gender in (0, 1):
        name = f'Pet46_{gender}'
        nodes = list(tree.iter(name))
        if len(nodes) != 1 or nodes[0] not in tree:
            raise PatchError(f'Missing or ambiguous owned species entry {name}')
        infos = list(nodes[0].iter('PetInfo'))
        if (len(infos) != 1 or infos[0].get('Name') != name or
                infos[0].get('IconPos') not in (PREVIOUS_ICON_POS, ICON_POS)):
            raise PatchError(f'Unknown Bloodfang portrait binding: {name}')
        blocks = list(re.finditer(r'<' + name + r'\b[^>]*>.*?</' + name + r'\s*>', result, re.S))
        if len(blocks) != 1:
            raise PatchError(f'Ambiguous Bloodfang text block: {name}')
        block = blocks[0]
        changed, count = re.subn(r'(<PetInfo\b[^>]*\bIconPos\s*=\s*["\'])(?:864,900|396,864)(["\'])',
                                lambda match: match[1] + ICON_POS + match[2], block.group())
        if count != 1:
            raise PatchError(f'Expected one Bloodfang portrait coordinate: {name}')
        result = result[:block.start()] + changed + result[block.end():]
    ET.fromstring(result)
    return result


def atlas_changes(client: Path, png_path: Path, expected_sha256: str,
                  *, allowed_predecessors=frozenset()) -> tuple[list[Change], dict]:
    client = client.resolve()
    references, count = scan_references(client)
    collisions = [ref for ref in references if ref.overlaps()]
    if collisions:
        raise PatchError('Portrait cell is referenced by another resource: ' +
                         '; '.join(f'{ref.path}:{ref.source}={ref.x},{ref.y}' for ref in collisions[:8]))
    sprite = normalized_sprite(png_path.read_bytes(), expected_sha256)
    changes = []
    for locale in LOCALES:
        path = contained(client, client / 'Localization' / locale / 'UI/Texture' / ATLAS)
        before = path.read_bytes()
        changes.append(Change(path, before, pack(before, sprite,
                                                allowed_predecessors=allowed_predecessors)))
    return changes, {'atlas': ATLAS, 'icon_pos': ICON_POS, 'sprite_sha256': sha256(sprite),
                     'source_sha256': expected_sha256, 'resource_files_scanned': count,
                     'coordinate_references_scanned': len(references), 'other_pixels_preserved': True}


def build_plan(client: Path, png_path: Path, expected_sha256: str,
               *, allowed_predecessors=frozenset()) -> tuple[list[Change], dict]:
    """Return four transactional changes; caller uses the standard installer.

    PatchClientBloodfang.install(client, None, changes) provides exact backups,
    pre-write stale-input guards, readback, and rollback for the whole plan.
    For a simultaneous model revision, use atlas_changes and pet_icons within
    that patch's existing Pet.xml change rather than scheduling a second write.
    """
    changes, report = atlas_changes(client, png_path, expected_sha256,
                                    allowed_predecessors=allowed_predecessors)
    for locale in LOCALES:
        path = contained(client.resolve(), client.resolve() / 'Localization' / locale / 'Settings/Sys/Pet.xml')
        doc = Document.read(path)
        changes.append(Change(path, path.read_bytes(), doc.encode(pet_icons(doc))))
    return changes, report

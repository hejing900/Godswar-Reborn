"""Lossless client text edits: preserve encoding, BOM and all unowned text."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import xml.etree.ElementTree as ET


class PatchError(RuntimeError):
    pass


@dataclass(frozen=True)
class Document:
    text: str
    encoding: str
    bom: bytes
    newline: str

    @classmethod
    def read(cls, path: Path) -> "Document":
        raw = path.read_bytes()
        if not raw or len(raw) > 4_000_000:
            raise PatchError(f"Unsupported client text size: {path}")
        if raw.startswith(b"\xff\xfe"):
            encoding, bom = "utf-16-le", b"\xff\xfe"
        elif raw.startswith(b"\xef\xbb\xbf"):
            encoding, bom = "utf-8", b"\xef\xbb\xbf"
        elif raw.startswith(b"\xfe\xff"):
            raise PatchError(f"Unsupported UTF-16BE client text: {path}")
        else:
            encoding, bom = "utf-8", b""
        try:
            text = raw[len(bom):].decode(encoding, errors="strict")
        except UnicodeError as error:
            raise PatchError(f"Invalid {encoding} text: {path}") from error
        if "\x00" in text:
            raise PatchError(f"Unsupported NUL in client text: {path}")
        # Existing patches legitimately use mixed CRLF/LF in Lua files. Keep
        # every old separator (including legacy CRCRLF); new rows use the
        # file's predominant separator.
        crlf = text.count("\r\n")
        newline = "\r\n" if crlf >= text.count("\n") - crlf else "\n"
        return cls(text, encoding, bom, newline)

    def encode(self, text: str) -> bytes:
        return self.bom + text.encode(self.encoding, errors="strict")


def unique(pattern: str, text: str, label: str, flags: int = re.MULTILINE) -> re.Match[str]:
    found = list(re.finditer(pattern, text, flags))
    if len(found) != 1:
        raise PatchError(f"Expected one {label}; found {len(found)}")
    return found[0]


def replace_one(text: str, pattern: str, replacement: str, label: str) -> str:
    match = unique(pattern, text, label)
    return text[:match.start()] + replacement + text[match.end():]


def append_lines(text: str, rows: list[str], newline: str) -> str:
    if not rows:
        return text
    final = text.endswith("\n")
    return text + ("" if final else newline) + newline.join(rows) + (newline if final else "")


def replace_rows(text: str, values: dict[str, str], newline: str,
                 new_keys: frozenset[str] = frozenset(), *,
                 previous_values: dict[str, str] | None = None) -> str:
    missing: list[str] = []
    for key, value in values.items():
        matches = list(re.finditer(r"^" + re.escape(key) + r"\t[^\r\n]*", text, re.MULTILINE))
        malformed = re.search(r"^" + re.escape(key) + r"(?:[ ]|\r?$)", text, re.MULTILINE)
        if malformed or len(matches) > 1:
            raise PatchError(f"Duplicate or malformed text key: {key}")
        row = key + "\t" + value
        if not matches:
            if key not in new_keys:
                raise PatchError(f"Missing existing text key: {key}")
            missing.append(row)
        else:
            match = matches[0]
            previous = None if previous_values is None else previous_values.get(key)
            if (key in new_keys and match.group() != row and
                    (previous is None or match.group() != key + "\t" + previous)):
                raise PatchError(f"New text key is occupied by unrelated content: {key}")
            text = text[:match.start()] + row + text[match.end():]
    return append_lines(text, missing, newline)


def xml_nodes(text: str) -> list[ET.Element]:
    try:
        return list(ET.fromstring(text))
    except ET.ParseError as error:
        raise PatchError(f"Malformed client XML: {error}") from error


def element(text: str, tag: str) -> tuple[re.Match[str], ET.Element]:
    match = unique(r"<" + re.escape(tag) + r"\b[^<>]*/>", text, f"XML element {tag}")
    try:
        node = ET.fromstring(match.group())
    except ET.ParseError as error:
        raise PatchError(f"Malformed XML element {tag}") from error
    return match, node


def set_attributes(text: str, tag: str, attributes: dict[str, str]) -> str:
    match, node = element(text, tag)
    updated = match.group()
    for key, value in attributes.items():
        if key not in node.attrib:
            raise PatchError(f"Missing {key} attribute on {tag}")
        updated = replace_one(updated, r"\b" + re.escape(key) + r'="[^"]*"',
                              f'{key}="{value}"', f"{tag}.{key}")
    return text[:match.start()] + updated + text[match.end():]


def add_xml(text: str, tag: str, attributes: dict[str, str], root: str, newline: str) -> str:
    matches = list(re.finditer(r"<" + re.escape(tag) + r"\b[^<>]*/>", text))
    if matches:
        _, node = element(text, tag)
        if node.attrib != attributes:
            raise PatchError(f"New XML element is occupied by unrelated content: {tag}")
        return text
    # No XML reserialization: only insert the owned row before its root close.
    row = "    <" + tag + " " + " ".join(f'{k}="{v}"' for k, v in attributes.items()) + "/>" + newline
    close = unique(r"^[ \t]*</" + re.escape(root) + r">", text, f"{root} closing element")
    return text[:close.start()] + row + text[close.start():]


def managed_block(text: str, key: str, body: str, newline: str, *, xml: bool = False,
                  previous_bodies: tuple[str, ...] = ()) -> str:
    start = f"<!-- Reborn {key}: BEGIN -->" if xml else f"-- Reborn {key}: BEGIN"
    end = f"<!-- Reborn {key}: END -->" if xml else f"-- Reborn {key}: END"
    block = start + newline + body.replace("\n", newline) + newline + end
    if start in text or end in text:
        match = unique(re.escape(start) + r"[\s\S]*?" + re.escape(end), text, key)
        if text.count(start) != 1 or text.count(end) != 1:
            raise PatchError(f"Duplicate managed block: {key}")
        if match.group() != block:
            previous_blocks = {start + newline + previous.replace("\n", newline) + newline + end
                               for previous in previous_bodies}
            if match.group() not in previous_blocks:
                raise PatchError(f"Managed block differs from authored content: {key}")
            return text[:match.start()] + block + text[match.end():]
        return text
    return append_lines(text, [block], newline)

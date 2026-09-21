"""Keep new Holy Suit materials in the native consumable item section."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from .text import PatchError, element


def add_beside_predecessor(text: str, tag: str, attributes: dict[str, str],
                          predecessor_tag: str, newline: str) -> str:
    """Create or relocate one exact owned row beside its existing native peer.

    The original Divinium installer put the row directly under the XML root.
    This is syntactically valid but the native consumable loader only visits
    the root's Item sections. Accept that exact orphan as a forward migration.
    """
    root = ET.fromstring(text)
    nodes = list(root.iter())
    parents = {child: parent for parent in nodes for child in parent}
    predecessors = [node for node in nodes if node.tag == predecessor_tag]
    if len(predecessors) != 1:
        raise PatchError(f"Expected one native predecessor {predecessor_tag}")
    predecessor = predecessors[0]
    destination = parents.get(predecessor)
    if destination is None:
        raise PatchError("Holy Suit predecessor has no container")
    if root.tag == "ItemBaseAttribute" and (
            destination.tag != "Item" or parents.get(destination) is not root):
        raise PatchError("Holy Suit predecessor is outside the native consumable Item section")
    existing = [node for node in nodes if node.get("ID") == attributes["ID"]]
    if len(existing) > 1 or any(node.tag != tag for node in existing):
        raise PatchError(f"Material item ID{attributes['ID']} is already allocated")
    if existing:
        node = existing[0]
        if node.attrib != attributes:
            raise PatchError(f"New XML element is occupied by unrelated content: {tag}")
        if parents.get(node) is destination:
            return text
        if parents.get(node) is not root or destination is root:
            raise PatchError(f"Material {tag} is in an unreviewed container")
        match, _ = element(text, tag)
        row = match.group()
        text = text[:match.start()] + text[match.end():]
    else:
        row = "<" + tag + " " + " ".join(f'{key}="{value}"' for key, value in attributes.items()) + "/>"
    anchor, _ = element(text, predecessor_tag)
    line_start = text.rfind("\n", 0, anchor.start()) + 1
    prefix = text[line_start:anchor.start()]
    indent = prefix if re.fullmatch(r"[ \t]*", prefix) else ""
    text = text[:anchor.end()] + newline + indent + row + text[anchor.end():]
    # Check the exact relationship the native section loader needs, not just
    # overall XML well-formedness. Leave every unowned node/attribute intact.
    checked = ET.fromstring(text)
    checked_parents = {child: parent for parent in checked.iter() for child in parent}
    actual = next(node for node in checked.iter() if node.tag == tag)
    peer = next(node for node in checked.iter() if node.tag == predecessor_tag)
    if checked_parents[actual] is not checked_parents[peer]:
        raise PatchError("Native Holy Suit material container verification failed")
    return text

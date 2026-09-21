"""Exact owned model-node upgrades without rewriting unrelated XML bytes."""
import copy
import math
import re
import xml.etree.ElementTree as ET

from holy_suit_tiers.text import PatchError

V2_PORTRAIT = '864,900'
V3_PORTRAIT = '396,864'
V2_PROFILE = dict(NameHeight='3.2', Range='1.0f', Shadow='1.2f',
                  Scale0='0.8f', ScaleOther='0.9f', AabbMaxX='2.81',
                  AabbMaxY='3.44', AabbMaxZ='1.10', AabbMinX='-2.81',
                  AabbMinY='0', AabbMinZ='-1.78')
V3_PROFILE = dict(NameHeight='3.2', Range='1.0f', Shadow='1.2f',
                  Scale0='0.8f', ScaleOther='0.9f', AabbMinX='-2.98',
                  AabbMaxX='2.97', AabbMinY='-0.14', AabbMaxY='3.86',
                  AabbMinZ='-2.17', AabbMaxZ='2.49')
V4_PROFILE = dict(NameHeight='2.2', Range='1.0f', Shadow='0.8f',
                  Scale0='0.35f', ScaleOther='0.385f', AabbMinX='-9.6',
                  AabbMaxX='9.9', AabbMinY='-2.2', AabbMaxY='8.6',
                  AabbMinZ='-9.4', AabbMaxZ='6.3')


def nodes(profile, portrait=V3_PORTRAIT):
    if not isinstance(profile, dict) or set(profile) != set(V2_PROFILE):
        raise PatchError('Reviewed Bloodfang model profile is not frozen')
    try:
        numbers = {k: float(v.removesuffix('f')) for k, v in profile.items()}
    except (ValueError, AttributeError) as error:
        raise PatchError('Invalid reviewed Bloodfang model profile') from error
    if (not all(math.isfinite(v) for v in numbers.values())
            or any(numbers[k] <= 0 for k in ('Scale0', 'ScaleOther', 'Range', 'Shadow', 'NameHeight'))
            or any(numbers['AabbMin' + axis] >= numbers['AabbMax' + axis] for axis in 'XYZ')):
        raise PatchError('Invalid reviewed Bloodfang bounds or presentation scale')
    common = {k: v for k, v in profile.items() if k not in ('Scale0', 'ScaleOther')}
    result = []
    for gender in (0, 1):
        node = ET.Element(f'Pet46_{gender}')
        ET.SubElement(node, 'PetInfo', Name=node.tag, IconPos=portrait)
        for index, samsara in enumerate((0, 8, 20, 90), 1):
            ET.SubElement(node, 'PetModel', Samsara=str(samsara),
                FileName='Bloodfang_male_001.jcs', TextureName='Bloodfang_male_001.gwo',
                # Match stock XML literally. Native loading strips one leading
                # character before concatenating the executable directory.
                unitefile=rf'\\Characters\\PetUniteEffect\\e_he_000{index}_all.gwm',
                **common, Scale=profile['Scale0' if samsara == 0 else 'ScaleOther'],
                Zbuffer='1', Zwrite='1', AlphaComFun='4', AlphaRefVal='0',
                CullingMode='2', SrcBlendFactor='1', DestBlendFactor='0', ConstBlendValue='-1')
        result.append(node)
    return result


def legacy_nodes(profile, portrait):
    """Exact v2-v4 definitions, including their broken single separators."""
    result = nodes(profile, portrait)
    for node in result:
        for row in node.findall('PetModel'):
            row.set('unitefile', row.get('unitefile').replace('\\\\', '\\'))
    return result


def signature(node):
    # Whitespace formatting is not ownership, but extra text/comments are.
    return (node.tag, node.attrib, (node.text or '').strip(),
            [(signature(child), (child.tail or '').strip()) for child in node])


def replace_attributes(fragment, before, after):
    rows = list(re.finditer(r'<(?:PetInfo|PetModel)\b[^<>]*/\s*>', fragment))
    if len(rows) != len(before):
        raise PatchError('Ambiguous owned Bloodfang model rows')
    for match, old, new in reversed(list(zip(rows, before, after, strict=True))):
        if old.tag != new.tag or set(old.attrib) != set(new.attrib):
            raise PatchError('Unsupported owned Bloodfang model shape change')
        row = match.group()
        for key, value in new.attrib.items():
            if old.attrib[key] == value:
                continue
            pattern = r'(?P<key>\b' + re.escape(key) + r'\s*=\s*)(?P<q>[\"\x27])(?P<value>.*?)(?P=q)'
            found = list(re.finditer(pattern, row))
            if len(found) != 1:
                raise PatchError(f'Ambiguous owned model attribute {key}')
            attr = found[0]
            row = row[:attr.start('value')] + value + row[attr.end('value'):]
        fragment = fragment[:match.start()] + row + fragment[match.end():]
    return fragment


def update(doc, profile):
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    tree = ET.fromstring(doc.text, parser=parser)
    if tree.tag != 'PetModel':
        raise PatchError('Unexpected Pet.xml root')
    targets = nodes(profile)
    predecessors = [legacy_nodes(V2_PROFILE, V2_PORTRAIT),
                    legacy_nodes(V2_PROFILE, V3_PORTRAIT),
                    legacy_nodes(V3_PROFILE, V3_PORTRAIT),
                    legacy_nodes(V4_PROFILE, V3_PORTRAIT),
                    nodes(V4_PROFILE, V3_PORTRAIT)]  # v5 repaired merge paths.
    located = [[n for n in tree.iter(target.tag)] for target in targets]
    if not any(located):
        close = list(re.finditer(r'</PetModel\s*>', doc.text))
        if len(close) != 1:
            raise PatchError('Ambiguous Pet.xml root closing tag')
        fragments = []
        for node in targets:
            item = copy.deepcopy(node)
            ET.indent(item, space='    ', level=1)
            fragments.append(ET.tostring(item, encoding='unicode').replace('\n', doc.newline))
        offset = close[0].start()
        return doc.text[:offset] + doc.newline.join(fragments) + doc.newline + doc.text[offset:]
    if any(len(matches) != 1 or matches[0] not in tree for matches in located):
        raise PatchError('Bloodfang model nodes are partial, duplicated, or misplaced')
    current = [matches[0] for matches in located]
    variants = [targets, *predecessors]
    if not any([signature(n) for n in current] == [signature(n) for n in variant] for variant in variants):
        raise PatchError('Bloodfang model nodes are occupied, modified, or a mixed release')
    if [signature(n) for n in current] == [signature(n) for n in targets]:
        return doc.text
    text = doc.text
    for old, target in zip(current, targets, strict=True):
        spans = list(re.finditer(r'<' + old.tag + r'\b[^<>]*>.*?</' + old.tag + r'\s*>', text, re.S))
        if len(spans) != 1:
            raise PatchError('Ambiguous owned Bloodfang node span')
        span = spans[0]
        updated = replace_attributes(span.group(), list(old), list(target))
        text = text[:span.start()] + updated + text[span.end():]
    ET.fromstring(text)
    return text

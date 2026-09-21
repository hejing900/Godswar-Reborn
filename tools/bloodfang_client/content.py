"""Lossless, collision-checked Bloodfang species additions to native client data."""
from pathlib import Path
import copy
import re
import xml.etree.ElementTree as ET

from holy_suit_tiers.text import Document, PatchError, replace_rows
from bloodfang_client import model_config, release

MODEL = 'Bloodfang_male_001.jcs'
TEXTURE = 'Bloodfang_male_001.gwo'
PORTRAIT = model_config.V3_PORTRAIT
APTITUDES = (1, 2, 3, 4, 5, 7, 8, 9, 10, 12, 14)
BASE_SKILLS = ','.join(str(i) for i in range(400, 2700, 100))
AUTO_SKILLS = '600,700,900,1400,1500,1700,1800,1900'
EGG = dict(ID='10194', Type='consume item',
           Texture='./Localization/en_us/UI/Texture/Icon2.gwo', Icon='108,972',
           Random='0', Distribution='0,0', Money='0', Overlap='1', Use='1',
           Skill='4740', ItemType='6', Values='46')
JADE = dict(ID='11096', Type='consume item',
            Texture='./Localization/en_us/UI/Texture/Icon2.gwo', Icon='396,756',
            Random='0', Distribution='0,0', Money='0', Overlap='99')


def structure(node):
    return node.tag, node.attrib, [structure(child) for child in node]


def append_nodes(doc, parent_tag, additions, *, parent_index=0):
    tree = ET.fromstring(doc.text)
    parents = [p for p in tree.iter(parent_tag) if len(p)]
    if len(parents) <= parent_index:
        raise PatchError(f'Missing native parent {parent_tag}')
    parent = parents[parent_index]
    missing = []
    for node in additions:
        matches = list(tree.iter(node.tag))
        if matches:
            if len(matches) != 1 or matches[0] not in parent or structure(matches[0]) != structure(node):
                raise PatchError(f'Bloodfang entry {node.tag} is occupied or modified')
        else:
            missing.append(node)
    if not missing:
        return doc.text
    # Confect has a same-named root and child; the first closing tag belongs
    # to the child, while iteration visits the root first.
    closings = list(re.finditer(r'</' + re.escape(parent_tag) + r'\s*>', doc.text))
    closing_index = 0 if parent_tag == 'Confect' and parent_index == 1 else parent_index
    if len(closings) != len(parents):
        raise PatchError(f'Ambiguous native parent {parent_tag}')
    offset = closings[closing_index].start()
    fragments = []
    for node in missing:
        item = copy.deepcopy(node)
        ET.indent(item, space='    ', level=1)
        fragments.append(ET.tostring(item, encoding='unicode').replace('\n', doc.newline))
    result = doc.text[:offset] + doc.newline.join(fragments) + doc.newline + doc.text[offset:]
    ET.fromstring(result)
    return result


def models():
    return model_config.nodes(release.MODEL_PROFILE, PORTRAIT)


def confect(doc):
    food = ET.Element('Bloodfang', Type='46', Food='2')
    species = ET.Element('Bloodfang', Type='46')
    for index, aptitude in enumerate(APTITUDES, 1):
        ET.SubElement(species, f'Bloodfang{index}', Type='46', Aptitude=str(aptitude),
            Trait_Start='0,0,0,0,0,0', Trait_Genius='0,0,0,0,0,0', Quality='0',
            Samsara='0', Genius='0', StartSkill='6400', AutoSkill=AUTO_SKILLS,
            AllowSkill=BASE_SKILLS + ',6400', Num='3', Procreate='0', Life='1200')
    # The same native species element name occurs under food and aptitude.
    # Distinct names avoid ambiguity while the Type attribute owns identity.
    food.tag = 'BloodfangFood'
    text = append_nodes(doc, 'Confect', [food], parent_index=1)
    return append_nodes(Document(text, doc.encoding, doc.bom, doc.newline), 'Aptitude', [species])


def items(doc):
    tree = ET.fromstring(doc.text)
    anchor = [n for n in tree.iter() if n.get('ID') == '10193']
    if len(anchor) != 1 or anchor[0].get('Values') != '44':
        raise PatchError('Native egg prerequisite differs')
    parents = {c:p for p in tree.iter() for c in p}
    parent = parents[anchor[0]]
    rows = [ET.Element('Pet10194', EGG), ET.Element('Pet11096', JADE)]
    for row in rows:
        collisions = [n for n in tree.iter() if n.get('ID') == row.get('ID')]
        if any(n.tag != row.tag for n in collisions):
            raise PatchError('Bloodfang item ID already occupied')
    return append_nodes(doc, parent.tag, rows)


def xml(doc, name):
    tree = ET.fromstring(doc.text)
    if name in ('Pet_Confect.xml', 'Pet_Alter.xml'):
        allowed = {'BloodfangFood', 'Bloodfang', 'Type46'} | {f'Bloodfang{i}' for i in range(1,12)}
        if any((n.get('Type') == '46' or n.get('PetType') == '46') and n.tag not in allowed for n in tree.iter()):
            raise PatchError('Species46 already occupied')
    if name == 'Pet.xml':
        return model_config.update(doc, release.MODEL_PROFILE)
    if name == 'Pet_Confect.xml': return confect(doc)
    if name == 'Pet_Alter.xml':
        return append_nodes(doc, 'typePoint', [ET.Element('Type46', PetType='46', Values='2.6001')])
    if name == 'ItemBaseAttribute.xml': return items(doc)
    raise PatchError('Unexpected XML resource')


def labels(doc, kind):
    values = {
        'pet': {'Pet46_0':'Bloodfang', 'Pet46_1':'Bloodfang'},
        'name': {'Pet10194':'Bloodfang Egg', 'Pet11096':'Magic Jade: Bloodfang'},
        'description': {
            'Pet10194':'Hatch a small vampiric dragon with Vampiric I. Restores 6% of damage inflicted as HP on each damaged target.',
            'Pet11096':'Take this Magic Jade to the Pet Administrator to change your pet into Bloodfang. Existing stats and learned skills are preserved.'}}
    selected = values[kind]
    return replace_rows(doc.text, selected, doc.newline, new_keys=frozenset(selected))


def lua(doc, base=False):
    if base:
        line = 'PETTYPE46 = "Bloodfang"'
        matches = re.findall(r'^PETTYPE46\s*=.*$', doc.text, re.M)
        if matches:
            if len(matches) != 1 or matches[0].strip() != line:
                raise PatchError('PETTYPE46 is occupied')
            return doc.text
        # The installed Chinese label list stops at44 although its menus
        # already branch through45. Preserve that locale's existing text.
        anchors = list(re.finditer(r'^PETTYPE45[^\r\n]*', doc.text, re.M))
        if not anchors:
            anchors = list(re.finditer(r'^PETTYPE44[^\r\n]*', doc.text, re.M))
        if len(anchors) != 1: raise PatchError('Missing unique final native pet label')
        end = anchors[0].end()
        return doc.text[:end] + doc.newline + line + doc.text[end:]
    pattern = r'(?P<indent>[ \t]*)elseif value == 45 then\s*\n(?P<body>[ \t]*\w+:SetText\(PETTYPE45\);)'
    matches = list(re.finditer(pattern, doc.text))
    if len(matches) != 1: raise PatchError('Missing native species-name branch')
    match = matches[0]
    addition = match.group().replace('== 45', '== 46').replace('PETTYPE45', 'PETTYPE46')
    if 'PETTYPE46' in doc.text:
        if doc.text.count('PETTYPE46') != 1 or addition not in doc.text:
            raise PatchError('Species46 Lua branch differs')
        return doc.text
    return doc.text[:match.end()] + doc.newline + addition + doc.text[match.end():]

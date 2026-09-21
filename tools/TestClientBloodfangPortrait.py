#!/usr/bin/env python3
"""Hermetic atlas ownership, image packing, and transaction tests."""
import binascii
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib

import PatchClientBloodfang as installer
from bloodfang_client import portrait as subject
from bloodfang_client.portrait_pixels import decode, resample_bgra
from holy_suit_tiers.text import Document, PatchError
from holy_suit_tiers.transaction import atomic_write
from level5_forge_icons.tga_atlas import display_pixel_index, parse_tga, patch_atlas


def png(width=36, channels=4, pixel=None):
    pixel = pixel or (b'\xc0\x12\x38\xff' if channels == 4 else b'\xc0\x12\x38')
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', binascii.crc32(kind + data) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' +
            chunk(b'IHDR', struct.pack('>IIBBBBB', width, width, 8, 6 if channels == 4 else 2, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress((b'\x00' + pixel * width) * width)) + chunk(b'IEND', b''))


def atlas():
    header = struct.pack('<BBBHHBHHHHBB', 0, 0, 10, 0, 0, 0, 0, 0, 1024, 1024, 32, 8)
    stream = (b'\xff' + b'\x00' * 4) * (1024 * 1024 // 128)
    extension = struct.pack('<H', 495) + bytes(493)
    data = header + stream + extension + struct.pack('<II', len(header + stream), 0) + b'TRUEVISION-XFILE.\x00'
    parsed = parse_tga(data, 'fixture')
    # One unrelated existing portrait pixel must survive every installation.
    return patch_atlas(parsed, {display_pixel_index(parsed, 864, 900): b'\xff\x80\x00\xff'})


PET_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<PetModel><!--Preserve original spacing and comments-->
  <Pet12_1><PetInfo Name="Pet12_1" IconPos="864,900"/><PetModel FileName="Dragon_male_001.jcs"/></Pet12_1>
  <Pet46_0><PetInfo Name="Pet46_0" IconPos="864,900"/><PetModel FileName="Bloodfang_male_001.jcs"/></Pet46_0>
  <Pet46_1><PetInfo Name="Pet46_1" IconPos="864,900"/><PetModel FileName="Bloodfang_male_001.jcs"/></Pet46_1>
</PetModel>'''


class BloodfangPortraitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.native = atlas()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='bloodfang-portrait-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.client = self.root / 'client'
        self.art = self.root / 'portrait.png'
        self.art.write_bytes(png())
        self.art_hash = subject.sha256(self.art.read_bytes())
        self.before = {}
        for locale in subject.LOCALES:
            base = self.client / 'Localization' / locale
            self.write(base / 'UI/Texture/Icon2.gwo', self.native)
            text = PET_XML.replace('\n', '\r\n')
            data = b'\xef\xbb\xbf' + text.encode() if locale == 'en_us' else b'\xff\xfe' + text.encode('utf-16-le')
            self.write(base / 'Settings/Sys/Pet.xml', data)

    def write(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self.before[path] = data

    def plan(self):
        return subject.build_plan(self.client, self.art, self.art_hash)

    def test_pack_preserves_all_other_pixels_and_tga_metadata(self):
        sprite = subject.normalized_sprite(self.art.read_bytes(), self.art_hash)
        old = parse_tga(self.native, 'old')
        result = subject.pack(self.native, sprite)
        new = parse_tga(result, 'new')
        expected = bytearray(old.pixels)
        for y in range(36):
            for x in range(36):
                index = display_pixel_index(old, 396 + x, 864 + y)
                offset = (y * 36 + x) * 4
                expected[index * 4:index * 4 + 4] = sprite[offset:offset + 4]
        self.assertEqual(bytes(expected), new.pixels)
        self.assertEqual(old.prefix, new.prefix)
        self.assertEqual(old.extension, new.extension)
        self.assertEqual(old.footer[4:], new.footer[4:])
        self.assertEqual(result, subject.pack(result, sprite))

    def test_all_four_changes_preserve_text_encoding_and_other_pet(self):
        changes, report = self.plan()
        self.assertEqual(4, len(changes))
        self.assertEqual('396,864', report['icon_pos'])
        self.assertTrue(report['other_pixels_preserved'])
        for change in changes:
            change.path.write_bytes(change.after)
            if change.path.name == 'Pet.xml':
                doc = Document.read(change.path)
                self.assertIn('<Pet12_1><PetInfo Name="Pet12_1" IconPos="864,900"/>', doc.text)
                self.assertEqual(2, doc.text.count('IconPos="396,864"'))
                self.assertEqual(self.before[change.path][:2], change.after[:2])
                self.assertEqual(self.before[change.path].count(b'\r\n'), change.after.count(b'\r\n'))
        self.assertTrue(all(not change.changed for change in self.plan()[0]))

    def test_unknown_or_invisible_nonzero_cell_is_not_overwritten(self):
        parsed = parse_tga(self.native, 'base')
        sprite = subject.normalized_sprite(self.art.read_bytes(), self.art_hash)
        index = display_pixel_index(parsed, 396, 864)
        for pixel in (b'\x01\x02\x03\xff', b'\x01\x00\x00\x00'):
            with self.assertRaises(PatchError):
                subject.pack(patch_atlas(parsed, {index: pixel}), sprite)

    def test_only_reviewed_predecessor_sprite_can_be_replaced(self):
        original = subject.normalized_sprite(self.art.read_bytes(), self.art_hash)
        current = subject.pack(self.native, original)
        successor = b'\x01\x02\x03\xff' * (36 * 36)
        with self.assertRaises(PatchError):
            subject.pack(current, successor)
        updated = subject.pack(current, successor, allowed_predecessors=frozenset({subject.sha256(original)}))
        self.assertEqual(successor, subject.cell_pixels(parse_tga(updated, 'updated')))

    def test_colliding_xml_and_lua_coordinates_rejected(self):
        path = self.client / 'Localization/en_us/Settings/Sys/Collision.xml'
        for text in ('<Other IconPos="396,864"/>', '<Other Texture="elsewhere.gwo" Icon="396,864"/>',
                     '<Button BtnTopTexture="./Icon2.gwo" BtnTopPos="380,850" BtnTopRect="0,0,50,50"/>'):
            self.write(path, text.encode())
            with self.assertRaises(PatchError):
                self.plan()
        path.unlink()
        self.write(self.client / 'Localization/third/UI/script.lua', b'icon:SetTexturePos(396, 864)')
        with self.assertRaises(PatchError):
            self.plan()

    def test_unrelated_stat_vectors_and_other_ui_atlases_are_not_icon_references(self):
        self.write(self.client / 'Localization/en_us/Settings/Sys/Stats.xml',
                   b'<Item Strength="396,864" Texture="./main.gwo" TexturePos="396,864"/>')
        self.plan()

    def test_invalid_owned_binding_fails_closed(self):
        path = self.client / 'Localization/en_us/Settings/Sys/Pet.xml'
        doc = Document.read(path)
        path.write_bytes(doc.encode(doc.text.replace('Name="Pet46_0" IconPos="864,900"',
                                                     'Name="Pet46_0" IconPos="1,2"')))
        with self.assertRaises(PatchError):
            self.plan()

    def test_source_hash_crc_transparency_and_rgb_support(self):
        with self.assertRaises(PatchError):
            subject.normalized_sprite(self.art.read_bytes(), '0' * 64)
        bad = bytearray(self.art.read_bytes()); bad[-1] ^= 1
        with self.assertRaises(PatchError):
            subject.normalized_sprite(bytes(bad), subject.sha256(bad))
        transparent = png(pixel=b'\0\0\0\0')
        with self.assertRaises(PatchError):
            subject.normalized_sprite(transparent, subject.sha256(transparent))
        self.assertEqual(subject.normalized_sprite(png(), subject.sha256(png())),
                         subject.normalized_sprite(png(channels=3), subject.sha256(png(channels=3))))

    def test_area_downsample_uses_premultiplied_alpha_without_color_fringe(self):
        source = b'\xff\x00\x00\xff' + b'\x00\x00\xff\x00'
        rgba = source * 36 * 72
        self.assertEqual(b'\x00\x00\xff\x80' * (36 * 36), resample_bgra(72, rgba))
        width, decoded = decode(png(width=72))
        self.assertEqual(72, width)
        self.assertEqual(b'\x38\x12\xc0\xff' * (36 * 36), resample_bgra(width, decoded))

    @patch.object(installer, 'assert_client_closed')
    def test_transaction_rolls_back_both_atlases_and_xml(self, closed):
        changes, _ = self.plan()
        def fail(path, data):
            if path == changes[-1].path and data == changes[-1].after:
                raise OSError('injected final XML failure')
            atomic_write(path, data)
        with patch.object(installer, 'atomic_write', side_effect=fail):
            with self.assertRaises(OSError):
                installer.install(self.client, None, changes)
        self.assertTrue(closed.called)
        for path, before in self.before.items():
            self.assertEqual(before, path.read_bytes())

    @patch.object(installer, 'assert_client_closed')
    def test_stale_atlas_prevents_all_writes(self, _):
        changes, _ = self.plan()
        changes[1].path.write_bytes(changes[1].before + b'Concurrent change')
        with self.assertRaises(PatchError):
            installer.install(self.client, None, changes)
        self.assertEqual(changes[0].before, changes[0].path.read_bytes())
        self.assertEqual(changes[2].before, changes[2].path.read_bytes())


if __name__ == '__main__':
    unittest.main()

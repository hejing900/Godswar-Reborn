"""Regression checks for the original palette's strict native TGA encoding."""
from pathlib import Path
import struct
import tempfile
import unittest

from native_export import atlas


class OriginalPaletteTextureTests(unittest.TestCase):
    def test_rle_packets_stop_at_scanlines_and_preserve_every_pixel(self):
        # Twelve materials exercise the partially-filled second palette row.
        # The old exporter joined its trailing color with all following rows.
        colors=[(0,0,0),(1,0,0),(0,1,0),(0,0,1),(1,1,0),(1,0,1),
                (0,1,1),(1,1,1),(1,0,0),(0,1,0),(0,0,1),(1,1,1)]
        materials=[{'name':str(i),'base_color':[*color,1]} for i,color in enumerate(colors)]
        with tempfile.TemporaryDirectory(prefix='bloodfang-texture-') as temp:
            destination=Path(temp)/'original.gwo'
            coordinates=atlas(materials,destination)
            data=destination.read_bytes()
        self.assertEqual((256,256,32,40),struct.unpack_from('<HHBB',data,12))
        self.assertEqual(10,data[2])
        cursor=18;pixels=[]
        while len(pixels)<256*256:
            packet=data[cursor];cursor+=1;count=(packet&127)+1
            self.assertLessEqual(count,256-len(pixels)%256,
                                 'TGA packet crosses a scanline; D3DX rejects this texture')
            if packet&128:
                color=data[cursor:cursor+4];cursor+=4;pixels.extend([color]*count)
            else:
                pixels.extend(data[i:i+4] for i in range(cursor,cursor+count*4,4));cursor+=count*4
        self.assertEqual(len(data),cursor)
        for index,pixel in enumerate(pixels):
            color=colors[min((index//256//32)*8+(index%256//32),11)]
            self.assertEqual(bytes([color[2]*255,color[1]*255,color[0]*255,255]),pixel)
        self.assertEqual(12,len(coordinates))
        self.assertEqual((.0625,.0625),coordinates[0])
        self.assertEqual((.4375,.1875),coordinates[11])


if __name__=='__main__':unittest.main()

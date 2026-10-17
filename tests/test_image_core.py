import io
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import image_core

try:
    from PIL import Image
except ImportError:
    Image = None


def sample(w, h, mode="RGBA"):
    random.seed(7)
    im = Image.new("RGBA", (w, h))
    im.putdata([(random.randrange(256), random.randrange(256), random.randrange(256), random.randrange(256))
                for _ in range(w * h)])
    return im.convert(mode)


def reference(data):
    return Image.open(io.BytesIO(data)).convert("RGBA").tobytes()


@unittest.skipIf(Image is None, "Pillow is needed to make test files")
class Decoders(unittest.TestCase):
    def check(self, data, name=""):
        w, h, rgba = image_core.decode(data, name)
        self.assertEqual(rgba, reference(data))
        self.assertEqual(len(rgba), w * h * 4)

    def save(self, im, fmt, **kw):
        b = io.BytesIO()
        im.save(b, fmt, **kw)
        return b.getvalue()

    def test_dds(self):
        for fmt in ("DXT1", "DXT3", "DXT5"):
            self.check(self.save(sample(70, 45), "DDS", pixel_format=fmt))

    def test_dds_uncompressed(self):
        self.check(self.save(sample(33, 17), "DDS"))

    def test_tga(self):
        for mode in ("RGBA", "RGB", "L"):
            for rle in (False, True):
                data = self.save(sample(37, 21, mode), "TGA", compression="tga_rle" if rle else None)
                self.check(data, "x.tga")

    def test_bmp(self):
        for mode in ("RGB", "RGBA", "L", "P"):
            self.check(self.save(sample(37, 21, mode), "BMP"))

    def test_png_roundtrip(self):
        w, h, rgba = image_core.decode(self.save(sample(20, 10), "DDS", pixel_format="DXT5"))
        back = Image.open(io.BytesIO(image_core.png_bytes(w, h, rgba))).convert("RGBA")
        self.assertEqual(back.tobytes(), rgba)

    def test_bad_input(self):
        with self.assertRaises(image_core.ImageError):
            image_core.decode(b"DDS " + os.urandom(200))


if __name__ == "__main__":
    unittest.main()

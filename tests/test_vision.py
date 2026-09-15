import io
import unittest

from mac.vision import visual_closeness


class VisionTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(visual_closeness(None), (0.0, 0.0, 0.0))
        self.assertEqual(visual_closeness(b""), (0.0, 0.0, 0.0))

    def test_strips_from_jpeg(self):
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            self.skipTest("Pillow not installed")
        img = Image.new("RGB", (96, 64), (20, 20, 20))
        draw = ImageDraw.Draw(img)
        # Strong vertical edges on the left third only.
        for x in range(0, 32, 2):
            draw.line([(x, 0), (x, 63)], fill=(255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        left, front, right = visual_closeness(buf.getvalue())
        self.assertGreater(left, front)
        self.assertGreater(left, right)

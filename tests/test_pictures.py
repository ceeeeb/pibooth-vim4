# -*- coding: utf-8 -*-

"""Tests of the text and resize code paths that use the Pillow API."""

import os
import unittest

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')

from PIL import Image  # noqa: E402

from pibooth import fonts, pictures  # noqa: E402
from pibooth.camera.base import BaseCamera  # noqa: E402
from pibooth.pictures.factory import PilPictureFactory  # noqa: E402

TEXT = 'Joyeux anniversaire'
FONT = fonts.get_filename('Amatic-Bold')


class FontFitTest(unittest.TestCase):

    @staticmethod
    def _fits(font, size, width, height):
        _, _, right, bottom = font.font_variant(size=size).getbbox(TEXT)
        return right <= width and bottom <= height

    def test_font_size_matches_the_rectangle(self):
        # The search returns the first size that overflows (inherited from
        # upstream): the size below fits, the size above does not.
        for width, height in ((600, 80), (200, 300), (1200, 40)):
            with self.subTest(size=(width, height)):
                font = fonts.get_pil_font(TEXT, FONT, width, height)
                self.assertTrue(self._fits(font, font.size - 1, width, height))
                self.assertFalse(self._fits(font, font.size + 1, width, height))


class PictureFactoryTest(unittest.TestCase):

    def _build(self, align):
        capture = Image.new('RGB', (1200, 800), (40, 120, 200))
        factory = PilPictureFactory(1800, 1200, capture, capture)
        factory.add_text(TEXT, FONT, (255, 255, 255), align)
        factory.add_text('5 octobre 2026', FONT, (255, 255, 255), align)
        return factory.build()

    def test_picture_with_texts_is_built(self):
        for align in (PilPictureFactory.LEFT, PilPictureFactory.CENTER, PilPictureFactory.RIGHT):
            with self.subTest(align=align):
                picture = self._build(align)
                self.assertEqual(picture.size, (1800, 1200))

    def test_texts_are_drawn(self):
        picture = self._build(PilPictureFactory.CENTER)
        whites = dict((color, count) for count, color in picture.getcolors(1 << 24)).get((255, 255, 255), 0)
        self.assertGreater(whites, 100)


class OverlayTest(unittest.TestCase):

    def test_countdown_text_is_centered(self):
        camera = BaseCamera.__new__(BaseCamera)
        overlay = camera.build_overlay((400, 300), '3', 255)
        left, top, right, bottom = overlay.getbbox()
        self.assertEqual(overlay.size, (400, 300))
        self.assertAlmostEqual((left + right) / 2, 200, delta=20)


class ResizeTest(unittest.TestCase):

    def test_pygame_image_is_resized(self):
        image = pictures.get_pygame_image('camera.png', (64, 64))
        self.assertLessEqual(image.get_width(), 64)
        self.assertLessEqual(image.get_height(), 64)


if __name__ == '__main__':
    unittest.main()

# -*- coding: utf-8 -*-

"""Tests of the picture flying to the printer queue when printing."""

import os
import unittest
from unittest import mock

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')

import pygame  # noqa: E402
from PIL import Image  # noqa: E402

from pibooth.view.flight import ease_in_out, flight_point, flight_scale  # noqa: E402
from pibooth.view.window import PiWindow  # noqa: E402


class FlightTest(unittest.TestCase):

    def test_flight_starts_and_ends_on_the_given_points(self):
        self.assertEqual(flight_point((1200, 450), (30, 870), 180, 0), (1200, 450))
        self.assertEqual(flight_point((1200, 450), (30, 870), 180, 1), (30, 870))

    def test_flight_rises_above_the_start(self):
        _, y = flight_point((1200, 450), (30, 870), 180, 0.3)
        self.assertLess(y, 450)

    def test_picture_shrinks_to_the_icon_size(self):
        self.assertEqual(flight_scale(800, 40, 0), 1)
        self.assertAlmostEqual(flight_scale(800, 40, 1), 40 / 800)

    def test_ease_keeps_the_bounds(self):
        self.assertEqual((ease_in_out(0), ease_in_out(1)), (0, 1))


class AnimatePrintTest(unittest.TestCase):

    def setUp(self):
        self.window = PiWindow('test', size=(800, 480))
        self.window.PRINT_FLIGHT_DURATION = 0.05

    def test_picture_lands_on_the_printer_queue_icon(self):
        self.window._update_foreground(Image.new('RGB', (600, 400), (200, 30, 30)), PiWindow.RIGHT)
        frames, landed = [], []
        smoothscale = pygame.transform.smoothscale
        blit = self.window.surface.blit

        def scale(surface, size):
            frames.append(smoothscale(surface, size))
            return frames[-1]

        def record(image, dest, *args):
            if frames and image is frames[-1]:
                landed.append(pygame.Rect(dest) if isinstance(dest, pygame.Rect)
                              else pygame.Rect(dest, image.get_size()))
            return blit(image, dest, *args)

        with mock.patch.object(pygame.transform, 'smoothscale', scale), \
                mock.patch.object(self.window, 'surface', wraps=self.window.surface) as surface:
            surface.blit.side_effect = record
            self.window.animate_print()
        self.assertGreater(len(landed), 1)
        self.assertLessEqual(max(landed[-1].size), self.window._print_queue_side() + 1)
        expected = self.window._print_queue_center()
        self.assertLessEqual(abs(landed[-1].centerx - expected[0]), 1)
        self.assertLessEqual(abs(landed[-1].centery - expected[1]), 1)

    def test_nothing_happens_without_a_displayed_picture(self):
        with mock.patch.object(pygame.display, 'update') as update:
            self.window.animate_print()
        update.assert_not_called()


if __name__ == '__main__':
    unittest.main()

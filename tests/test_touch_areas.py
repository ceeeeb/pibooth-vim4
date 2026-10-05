# -*- coding: utf-8 -*-

"""Tests of the screen areas that take a picture or print on a touch."""

import os
import unittest
from unittest import mock

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')

import pygame  # noqa: E402

from pibooth.booth import PiApplication  # noqa: E402

SCREEN = (1600, 900)
PRINT_BUTTON = pygame.Rect(560, 650, 160, 160)  # In the left half, as on the wait screen


def tap(x, y):
    return pygame.event.Event(pygame.FINGERUP, x=x / SCREEN[0], y=y / SCREEN[1], finger_id=0, touch_id=0)


class TouchAreasTest(unittest.TestCase):

    def setUp(self):
        self.app = PiApplication.__new__(PiApplication)
        self.app._window = mock.Mock(display_size=SCREEN)
        self.app._window.get_rect.return_value = pygame.Rect((0, 0), SCREEN)
        self.app._window.get_print_button_rect.return_value = PRINT_BUTTON
        self.app._config = mock.Mock()
        self.app._config.getboolean.return_value = False  # touch_flip

    def test_tapping_the_print_button_prints_only(self):
        events = [tap(*PRINT_BUTTON.center)]
        self.assertIsNotNone(self.app.find_print_event(events))
        self.assertIsNone(self.app.find_capture_event(events))

    def test_tapping_the_left_half_takes_a_picture(self):
        events = [tap(200, 300)]
        self.assertIsNotNone(self.app.find_capture_event(events))
        self.assertIsNone(self.app.find_print_event(events))

    def test_left_half_takes_a_picture_without_print_button(self):
        self.app._window.get_print_button_rect.return_value = None
        self.assertIsNotNone(self.app.find_capture_event([tap(*PRINT_BUTTON.center)]))


if __name__ == '__main__':
    unittest.main()

# -*- coding: utf-8 -*-

"""Tests of the board independent GPIO layer."""

import unittest

from pibooth import hardware
from pibooth.hardware import mock
from pibooth.hardware.base import GpioError


class BoardTest(unittest.TestCase):

    def test_pin_is_the_line_when_no_table(self):
        board = hardware.Board('a raspberry pi', mock)
        self.assertEqual(board._line(11), 11)

    def test_pin_is_translated_into_a_line(self):
        board = hardware.Board('a khadas vim4', mock, {36: '464'})
        self.assertEqual(board._line(36), '464')

    def test_unusable_pin_is_rejected(self):
        board = hardware.Board('a khadas vim4', mock, {36: '464'})
        with self.assertRaises(GpioError):
            board._line(11)


class PinoutsTest(unittest.TestCase):

    def test_vim4_is_detected(self):
        board = self._find_board_of('Khadas VIM4')
        self.assertEqual(board._backend.__name__, 'pibooth.hardware.chardev')
        self.assertEqual(board._line(37), '465')

    def test_raspberry_pi_needs_no_table(self):
        board = self._find_board_of('Raspberry Pi 4 Model B Rev 1.1')
        self.assertEqual(board._backend.__name__, 'pibooth.hardware.rpi')
        self.assertEqual(board._line(11), 11)

    def test_unknown_board_falls_back_to_mock(self):
        board = self._find_board_of('Some Random SBC')
        self.assertEqual(board._backend.__name__, 'pibooth.hardware.mock')

    @staticmethod
    def _find_board_of(model):
        original = hardware.get_board_model
        hardware.get_board_model = lambda: model
        try:
            return hardware.find_board()
        finally:
            hardware.get_board_model = original


class LedGroupTest(unittest.TestCase):

    def setUp(self):
        self.leds = hardware.LedGroup(capture=mock.Led(16), printer=mock.Led(15))

    def test_leds_are_reachable_by_name(self):
        self.assertEqual(self.leds.capture.pin, 16)

    def test_blink_drives_every_led(self):
        self.leds.blink(on_time=0.1, off_time=0.1)
        self.assertTrue(all(led.is_blinking for led in self.leds))

    def test_off_stops_every_led(self):
        self.leds.blink()
        self.leds.off()
        self.assertFalse(any(led.is_blinking for led in self.leds))


class ButtonGroupTest(unittest.TestCase):

    def test_value_reports_every_button(self):
        buttons = hardware.ButtonGroup(capture=mock.Button(11), printer=mock.Button(32))
        self.assertEqual(buttons.value, (0, 0))


if __name__ == '__main__':
    unittest.main()

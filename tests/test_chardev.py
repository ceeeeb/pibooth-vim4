# -*- coding: utf-8 -*-

"""Tests of the character device backend, without any GPIO hardware."""

import time
import threading
import unittest

from pibooth.hardware import chardev


class FakeLgpio(object):

    """Records what the backend writes on the GPIO lines."""

    def __init__(self):
        self.writes = []

    def gpio_write(self, handle, offset, value):
        self.writes.append(value)


def make_led(active_high=True):
    """Return a LED bound to a fake chip, bypassing the GPIO claim."""
    led = object.__new__(chardev.Led)
    led._lgpio = FakeLgpio()
    led._handle = 0
    led._offset = 12
    led._active_high = active_high
    led._blinking = None
    led._lock = threading.Lock()
    return led


class BlinkTest(unittest.TestCase):

    def test_bounded_blinking_stops_by_itself(self):
        led = make_led()
        led.blink(on_time=0.01, off_time=0.01, n=3)
        time.sleep(0.3)
        self.assertEqual(led._lgpio.writes, [1, 0, 1, 0, 1, 0])
        self.assertFalse(led.is_blinking)

    def test_endless_blinking_keeps_running(self):
        led = make_led()
        led.blink(on_time=0.01, off_time=0.01)
        time.sleep(0.1)
        self.assertTrue(led.is_blinking)
        led.off()
        self.assertFalse(led.is_blinking)
        self.assertEqual(led._lgpio.writes[-1], 0)

    def test_switching_on_interrupts_the_sequence(self):
        led = make_led()
        led.blink(on_time=10, off_time=10)
        led.on()
        self.assertFalse(led.is_blinking)
        self.assertEqual(led._lgpio.writes[-1], 1)

    def test_active_low_led_writes_inverted_levels(self):
        led = make_led(active_high=False)
        led.on()
        led.off()
        self.assertEqual(led._lgpio.writes, [0, 1])


if __name__ == '__main__':
    unittest.main()

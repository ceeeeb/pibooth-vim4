# -*- coding: utf-8 -*-

"""Fake GPIO devices, used when pibooth runs on a machine without GPIO."""

from pibooth.hardware.base import BaseButton, BaseLed


class Button(BaseButton):

    """A button that is never pressed."""

    def __init__(self, pin, pull_up=True, hold_time=0.2):
        self.pin = pin
        self._callback = None

    @property
    def value(self):
        return 0

    @property
    def when_held(self):
        return self._callback

    @when_held.setter
    def when_held(self, callback):
        self._callback = callback

    def close(self):
        pass


class Led(BaseLed):

    """A LED that lights up nothing."""

    def __init__(self, pin, active_high=True):
        self.pin = pin
        self._blinking = False

    def on(self):
        self._blinking = False

    def off(self):
        self._blinking = False

    def blink(self, on_time=1, off_time=1, n=None):
        self._blinking = n is None

    @property
    def is_blinking(self):
        return self._blinking

    def close(self):
        pass

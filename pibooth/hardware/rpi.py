# -*- coding: utf-8 -*-

"""GPIO access through :py:mod:`gpiozero`, dedicated to the Raspberry Pi.

The pins are addressed with the physical header numbering (BOARD), which
gpiozero already knows for every Raspberry Pi model.
"""

from pibooth.hardware.base import BaseButton, BaseLed, GpioError


def _board(pin):
    return "BOARD{}".format(pin)


class Button(BaseButton):

    """A push button connected to a Raspberry Pi header pin."""

    def __init__(self, pin, pull_up=True, hold_time=0.2):
        from gpiozero import Button as GpiozeroButton
        try:
            self._button = GpiozeroButton(_board(pin), pull_up=pull_up, hold_time=hold_time)
        except Exception as ex:
            raise GpioError("Can not use pin {} as button: {}".format(pin, ex))

    @property
    def value(self):
        return int(self._button.value)

    @property
    def hold_repeat(self):
        return self._button.hold_repeat

    @hold_repeat.setter
    def hold_repeat(self, repeat):
        self._button.hold_repeat = repeat

    @property
    def when_held(self):
        return self._button.when_held

    @when_held.setter
    def when_held(self, callback):
        self._button.when_held = callback

    def close(self):
        self._button.close()


class Led(BaseLed):

    """A LED connected to a Raspberry Pi header pin."""

    def __init__(self, pin, active_high=True):
        from gpiozero import LED as GpiozeroLed
        try:
            self._led = GpiozeroLed(_board(pin), active_high=active_high)
        except Exception as ex:
            raise GpioError("Can not use pin {} as LED: {}".format(pin, ex))

    def on(self):
        self._led.on()

    def off(self):
        self._led.off()

    def blink(self, on_time=1, off_time=1):
        self._led.blink(on_time=on_time, off_time=off_time)

    @property
    def is_blinking(self):
        return getattr(self._led, '_blink_thread', None) is not None

    def close(self):
        self._led.close()

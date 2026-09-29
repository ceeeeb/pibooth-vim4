# -*- coding: utf-8 -*-

"""GPIO access through the Linux character devices ``/dev/gpiochipN``.

This backend only relies on the standard kernel interfaces, which makes it
usable on any Linux single board computer, contrary to :py:mod:`gpiozero`
which is dedicated to the Raspberry Pi.
"""

import os
import glob
import time
import threading

from pibooth.utils import LOGGER
from pibooth.hardware.base import BaseButton, BaseLed, GpioError

# Period between two reads of a button state
POLLING_PERIOD = 0.02

SYSFS_LEGACY_CHIPS = '/sys/class/gpio/gpiochip*'
SYSFS_CHARDEV_CHIPS = '/sys/bus/gpio/devices/gpiochip*'


def _read_attribute(directory, name):
    with open(os.path.join(directory, name)) as fp:
        return fp.read().strip()


def _controller_of(sysfs_path, depth):
    """Return the device directory of the GPIO controller owning `sysfs_path`.

    The same controller is exposed twice by the kernel, at a different depth in
    the device tree, which is why the number of parent directories to climb
    depends on the sysfs interface being walked.
    """
    path = os.path.realpath(sysfs_path)
    for _ in range(depth):
        path = os.path.dirname(path)
    return path


def _chardev_indexes():
    """Return the ``/dev/gpiochipN`` index of each GPIO controller."""
    indexes = {}
    for path in glob.glob(SYSFS_CHARDEV_CHIPS):
        minor = int(_read_attribute(path, 'dev').split(':')[1])
        indexes[_controller_of(path, 1)] = minor
    return indexes


def _global_ranges():
    """Yield the (base, size, controller) of each range of global GPIO numbers."""
    for path in glob.glob(SYSFS_LEGACY_CHIPS):
        yield (int(_read_attribute(path, 'base')),
               int(_read_attribute(path, 'ngpio')),
               _controller_of(path, 2))


def resolve_line(spec):
    """Convert a pinout table value into a ``(chip, offset)`` tuple.

    The value is either an explicit ``chip:offset`` pair, or the global GPIO
    number documented by the board vendor, which is looked up in sysfs.
    """
    spec = str(spec).strip()
    if ':' in spec:
        chip, offset = spec.split(':', 1)
        return int(chip), int(offset)

    number = int(spec)
    indexes = _chardev_indexes()
    for base, size, controller in _global_ranges():
        if base <= number < base + size:
            if controller not in indexes:
                raise GpioError("No character device for the GPIO controller of line {}".format(number))
            return indexes[controller], number - base

    raise GpioError("GPIO {} is out of the ranges published by the kernel, declare it as "
                    "'chip:offset' in the pinout table".format(number))


def _open_chip(chip):
    import lgpio
    try:
        return lgpio.gpiochip_open(chip)
    except Exception as ex:
        raise GpioError("Can not open /dev/gpiochip{}: {}".format(chip, ex))


class Button(BaseButton):

    """A push button read by polling its GPIO line.

    Edge detection is deliberately not used: polling gives the debouncing and
    the hold detection for free, at a negligible cost for the few buttons of a
    photo booth.
    """

    def __init__(self, line, pull_up=True, hold_time=0.2):
        import lgpio
        chip, self._offset = resolve_line(line)
        self._lgpio = lgpio
        self._hold_time = hold_time
        self._pressed_level = 0 if pull_up else 1
        self._handle = _open_chip(chip)
        self._claim_input(pull_up)

        self._callback = None
        self._held_notified = False
        self._pressed_since = None
        self._running = True
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()

    def _claim_input(self, pull_up):
        """Claim the line as an input, falling back to a floating input when
        the driver has no internal pull resistor (external one required).
        """
        flags = self._lgpio.SET_PULL_UP if pull_up else self._lgpio.SET_PULL_DOWN
        try:
            self._lgpio.gpio_claim_input(self._handle, self._offset, flags)
        except Exception:
            LOGGER.warning("GPIO line %s has no internal pull resistor, an external "
                           "one is required on this button", self._offset)
            try:
                self._lgpio.gpio_claim_input(self._handle, self._offset)
            except Exception as ex:
                raise GpioError("Can not claim GPIO line {} as input: {}".format(self._offset, ex))

    def _poll(self):
        while self._running:
            try:
                if self.value:
                    if self._pressed_since is None:
                        self._pressed_since = time.time()
                    elif not self._held_notified and time.time() - self._pressed_since >= self._hold_time:
                        self._held_notified = True
                        if self._callback:
                            self._callback()
                        if self.hold_repeat:  # the callback may have changed it
                            self._pressed_since, self._held_notified = time.time(), False
                else:
                    self._pressed_since = None
                    self._held_notified = False
            except Exception as ex:
                LOGGER.debug("Can not read GPIO line %s: %s", self._offset, ex)
            time.sleep(POLLING_PERIOD)

    @property
    def value(self):
        return int(self._lgpio.gpio_read(self._handle, self._offset) == self._pressed_level)

    @property
    def when_held(self):
        return self._callback

    @when_held.setter
    def when_held(self, callback):
        self._callback = callback

    def close(self):
        self._running = False
        self._thread.join(timeout=1)
        self._lgpio.gpiochip_close(self._handle)


class Led(BaseLed):

    """A LED driven by a GPIO output line."""

    def __init__(self, line, active_high=True):
        import lgpio
        chip, self._offset = resolve_line(line)
        self._lgpio = lgpio
        self._active_high = active_high
        self._handle = _open_chip(chip)
        try:
            lgpio.gpio_claim_output(self._handle, self._offset, 0 if active_high else 1)
        except Exception as ex:
            raise GpioError("Can not claim GPIO line {} as output: {}".format(self._offset, ex))

        self._blinking = None  # (thread, stop event) while a sequence is running
        self._lock = threading.Lock()

    def _write(self, lit):
        self._lgpio.gpio_write(self._handle, self._offset, int(lit == self._active_high))

    def _stop_blinking(self):
        with self._lock:
            current, self._blinking = self._blinking, None
        if current:
            thread, stop = current
            stop.set()
            if thread is not threading.current_thread():
                thread.join(timeout=1)

    def _blink(self, stop, on_time, off_time, n):
        cycles = 0
        while n is None or cycles < n:
            self._write(True)
            if stop.wait(on_time):
                return
            self._write(False)
            if stop.wait(off_time):
                return
            cycles += 1

        # The sequence ended on its own, the LED is no longer blinking
        with self._lock:
            if self._blinking and self._blinking[1] is stop:
                self._blinking = None

    def on(self):
        self._stop_blinking()
        self._write(True)

    def off(self):
        self._stop_blinking()
        self._write(False)

    def blink(self, on_time=1, off_time=1, n=None):
        self._stop_blinking()
        stop = threading.Event()
        thread = threading.Thread(target=self._blink, args=(stop, on_time, off_time, n), daemon=True)
        with self._lock:
            self._blinking = (thread, stop)
        thread.start()

    @property
    def is_blinking(self):
        return self._blinking is not None

    def close(self):
        self._stop_blinking()
        self._write(False)
        self._lgpio.gpiochip_close(self._handle)

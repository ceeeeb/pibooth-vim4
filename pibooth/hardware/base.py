# -*- coding: utf-8 -*-

"""Hardware independent interfaces for the GPIO devices used by pibooth."""


class GpioError(Exception):

    """Raised when a GPIO line can not be found, claimed or driven."""


class BaseButton(object):

    """A push button connected to a GPIO input line.

    :attr hold_repeat: when True, the 'when_held' callback is fired again every
                       'hold_time' seconds while the button stays pressed
    """

    hold_repeat = False

    @property
    def value(self):
        """Return 1 when the button is pressed, 0 otherwise."""
        raise NotImplementedError

    @property
    def when_held(self):
        """Return the callback fired when the button is held down."""
        raise NotImplementedError

    @when_held.setter
    def when_held(self, callback):
        raise NotImplementedError

    def close(self):
        """Release the GPIO line."""
        raise NotImplementedError


class BaseLed(object):

    """A LED connected to a GPIO output line."""

    def on(self):
        """Switch the LED on, stopping any blinking sequence."""
        raise NotImplementedError

    def off(self):
        """Switch the LED off, stopping any blinking sequence."""
        raise NotImplementedError

    def blink(self, on_time=1, off_time=1, n=None):
        """Blink the LED n times, or until :py:meth:`on` or :py:meth:`off` is
        called when n is None.
        """
        raise NotImplementedError

    @property
    def is_blinking(self):
        """Return True when a blinking sequence is running."""
        raise NotImplementedError

    def close(self):
        """Release the GPIO line."""
        raise NotImplementedError

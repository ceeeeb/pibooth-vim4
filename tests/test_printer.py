# -*- coding: utf-8 -*-

"""Tests of the printer when the CUPS server is not reachable."""

import unittest
from unittest import mock

from pibooth import printer


class UnreachableCupsTest(unittest.TestCase):

    def setUp(self):
        cups = mock.Mock()
        cups.Connection.side_effect = RuntimeError('failed to connect to server')
        patcher = mock.patch.object(printer, 'cups', cups)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_starts_without_printing_support(self):
        with self.assertLogs('pibooth', 'WARNING') as logs:
            device = printer.Printer('default')
        self.assertFalse(device.is_installed())
        self.assertFalse(device.is_ready())
        self.assertIn('can not connect to the CUPS server', logs.output[0])

    def test_tasks_are_empty(self):
        device = printer.Printer('default')
        self.assertEqual(device.get_all_tasks(), {})
        device.quit()


class PrinterEventTest(unittest.TestCase):

    def test_event_error_does_not_raise(self):
        device = printer.Printer.__new__(printer.Printer)
        with mock.patch.object(printer.pygame.event, 'post', side_effect=RuntimeError('no display')):
            with self.assertLogs('pibooth', 'WARNING'):
                device._on_event(mock.Mock(title='Job completed'))


if __name__ == '__main__':
    unittest.main()

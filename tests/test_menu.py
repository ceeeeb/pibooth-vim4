# -*- coding: utf-8 -*-

"""Tests of the printer queue entry of the settings menu."""

import unittest
from unittest import mock

from pibooth.config import menu


class PrinterQueueTest(unittest.TestCase):

    def setUp(self):
        self.printer = mock.Mock()
        self.printer.get_all_tasks.return_value = {1: {}, 2: {}}
        self.menu = menu.PiConfigMenu.__new__(menu.PiConfigMenu)
        self.menu.app = mock.Mock(printer=self.printer)
        self.label = mock.Mock()

    def test_tasks_are_counted(self):
        self.assertTrue(menu._printer_tasks(self.printer).endswith('   2'))

    def test_unreachable_cups_is_shown_as_unknown(self):
        self.printer.get_all_tasks.side_effect = RuntimeError('server gone')
        with self.assertLogs('pibooth', 'WARNING'):
            self.assertTrue(menu._printer_tasks(self.printer).endswith('   ?'))

    def test_cancel_refreshes_the_label(self):
        self.printer.cancel_all_tasks.side_effect = lambda: self.printer.get_all_tasks.configure_mock(return_value={})
        self.menu._on_printer_cancel(self.label)
        self.printer.cancel_all_tasks.assert_called_once_with()
        self.assertTrue(self.label.set_title.call_args[0][0].endswith('   0'))

    def test_cancel_failure_does_not_raise(self):
        self.printer.cancel_all_tasks.side_effect = RuntimeError('printer disabled')
        with self.assertLogs('pibooth', 'WARNING'):
            self.menu._on_printer_cancel(self.label)
        self.assertTrue(self.label.set_title.call_args[0][0].endswith('   2'))


if __name__ == '__main__':
    unittest.main()

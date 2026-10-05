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


class BackButtonTest(unittest.TestCase):

    def setUp(self):
        import os
        import tempfile
        import pygame
        from pibooth.config.parser import PiConfigParser
        os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
        pygame.init()
        surface = pygame.display.set_mode((800, 480))
        directory = tempfile.mkdtemp()
        self.addCleanup(__import__('shutil').rmtree, directory)
        window = mock.Mock(surface=surface, display_size=(800, 480))
        window.get_rect.return_value = surface.get_rect()
        printer = mock.Mock()
        printer.is_installed.return_value = True
        printer.get_all_tasks.return_value = {}
        from pibooth.counters import Counters
        app = mock.Mock(printer=printer, count=Counters(os.path.join(directory, 'counters.json'), taken=0))
        plugins = mock.Mock()
        plugins.list_external_plugins.return_value = []
        config = PiConfigParser(os.path.join(directory, 'pibooth.cfg'), plugins)
        self.menu = menu.PiConfigMenu(plugins, config, app, window)

    @staticmethod
    def _button(parent, title):
        return [w for w in parent.get_widgets() if w.get_title().strip().lower() == title.lower()][0]

    @staticmethod
    def _submenus(parent):
        return [s for s in parent._submenus]

    def test_every_submenu_has_a_back_button(self):
        for submenu in self._submenus(self.menu._main_menu):
            with self.subTest(submenu=submenu.get_title()):
                self.assertTrue(self._button(submenu, 'Back'))
                for child in self._submenus(submenu):
                    self.assertTrue(self._button(child, 'Back'), child.get_title())

    def test_back_leaves_the_printer_queue(self):
        main = self.menu._main_menu
        main.enable()
        printer = [s for s in self._submenus(main) if s.get_title().lower() == 'printer'][0]
        queue = self._submenus(printer)[0]
        self._button(main, 'Printer').apply()
        self._button(printer, 'Printer queue').apply()
        self.assertIs(main.get_current(), queue)
        self._button(queue, 'Back').apply()
        self.assertIs(main.get_current(), printer)

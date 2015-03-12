
# install_window.py
#
# Copyright (C) 2015 Kano Computing Ltd.
# License: http://www.gnu.org/licenses/gpl-2.0.txt GNU GPL v2
#
# Installer main window
#

import os
import time
from gi.repository import Gtk
from threading import Thread

from kano.gtk3.apply_styles import apply_styling_to_screen
from kano.gtk3.kano_dialog import KanoDialog

from kano_updater.ui.paths import CSS_PATH
from kano_updater.commands.install import install
from kano_updater.ui.progress import GtkProgress
from kano_updater.ui.views.install import Install
from kano_updater.ui.views.restart import Restart


class InstallWindow(Gtk.Window):
    CSS_FILE = os.path.join(CSS_PATH, 'updater.css')

    def __init__(self):
        # Apply styling to window
        apply_styling_to_screen(self.CSS_FILE)

        Gtk.Window.__init__(self)
        self.fullscreen()
        self.set_keep_above(True)

        self.set_icon_name('kano-updater')
        self.set_title(_('Updater'))

        self._install_screen = Install()
        self.add(self._install_screen)

        self._evt = self.connect('key-press-event', self._done_install)

        self.show_all()

        # self.connect('delete-event', self.close_window)

        self._start_install()

    def _start_install(self):
        progress = GtkProgress(self)
        install_thread = Thread(target=install, args=(progress,))
        # FIXME: What to do when the gui is killed and the thread is still running?
        install_thread.daemon = True
        install_thread.start()

    def _done_install(self, *args):
        self.disconnect(self._evt)
        for child in self.get_children():
            self.remove(child)

        reboot_screen = Restart()
        self.add(reboot_screen)

        self.show_all()

    def close_window(self, widget=None, event=None):
        Gtk.main_quit()

    def update_progress(self, percent, msg, sub_msg=''):
        self._install_screen.update_progress(percent, msg, sub_msg)

        # FIXME Progress to next with the done
        if percent == 100 and sub_msg in [_('Update completed'),
                                          _('No updates to download')]:

            self._done_install()

    def error(self, msg):
        error = KanoDialog(
            _('Error updating'), msg,
            {
                'CLOSE': {
                    'return_value': True,
                    'color': 'red'
                }
            },
            parent_window=self)
        error.run()
        # FIXME: This close doesn't work for some reason
        self.close_window()


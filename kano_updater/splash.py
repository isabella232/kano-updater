#
# splash.py
#
# Copyright (C) 2015 Kano Computing Ltd.
# License: http://www.gnu.org/licenses/gpl-2.0.txt GNU GPL v2
#
# configure boot splash

import os
from paths import INTERRUPTED_SPLASH_PATH


def set_splash_interrupted():
    # This command may not exist yet, so ignore errors
    os.system('kano-boot-splash-cli set {}'.format(INTERRUPTED_SPLASH_PATH))


def clear_splash():
    # This command may not exist yet, so ignore errors
    os.system('kano-boot-splash-cli clear')

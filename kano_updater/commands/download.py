#
# Managing downloads of apt and pip packages for the upgrade
#
# Copyright (C) 2014 Kano Computing Ltd.
# License: http://www.gnu.org/licenses/gpl-2.0.txt GNU GPL v2
#

import pip

from kano.network import is_internet

from kano_updater.paths import PIP_PACKAGES_LIST
from kano_updater.status import UpdaterStatus
from kano_updater.apt_wrapper import apt_handle


class DownloadError(Exception):
    pass


def download(progress=None):
    if not is_internet():
        raise DownloadError("Must have internet to download the updates")

    status = UpdaterStatus()

    if status.state == 'downloading-update':
        # TODO: check whether the process is still going
        raise DownloadError("The download is already running")

    if status.state == 'updates-downloaded':
        return

    _cache_pip_packages()
    _cache_deb_packages()

    status.state = 'updates-downloaded'
    status.save()


def _cache_pip_packages():
    """
        Downloads all updatable python modules and caches them in pip's
        internal pacakge cache.
    """

    # The `--no-install` parameter has been deprecated in pip. However, the
    # version of pip in wheezy doesn't yet support the new approach which is
    # supposed to provide the same behaviour.
    pip.main(['install', '--upgrade', '--no-install', '-r', PIP_PACKAGES_LIST])


def _cache_deb_packages():
    apt_handle.update()
    apt_handle.cache_updates()

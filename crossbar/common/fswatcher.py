#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#
#  Unless a separate license agreement exists between you and Crossbar.io GmbH (e.g.
#  you have purchased a commercial license), the license terms below apply.
#
#  Should you enter into a separate license agreement after having received a copy of
#  this software, then the terms of such license agreement replace the terms below at
#  the time at which such license agreement becomes effective.
#
#  In case a separate license agreement ends, and such agreement ends without being
#  replaced by another separate license agreement, the license terms below apply
#  from the time at which said agreement ends.
#
#  LICENSE TERMS
#
#  This program is free software: you can redistribute it and/or modify it under the
#  terms of the GNU Affero General Public License, version 3, as published by the
#  Free Software Foundation. This program is distributed in the hope that it will be
#  useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  See the GNU Affero General Public License Version 3 for more details.
#
#  You should have received a copy of the GNU Affero General Public license along
#  with this program. If not, see <http://www.gnu.org/licenses/agpl-3.0.en.html>.
#
#####################################################################################

from __future__ import absolute_import

import os
from txaio import make_logger

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    HAS_FS_WATCHER = False
else:
    HAS_FS_WATCHER = True

__all__ = ('FilesystemWatcher', 'HAS_FS_WATCHER')


if HAS_FS_WATCHER:

    class FilesystemWatcher:

        """
        Watches a directories for file system changes.
        """

        log = make_logger()

        def __init__(self, working_dir='.', watched_dirs=['.']):
            """

            :param watched_dirs: Directories to watch for changes.
            :type watched_dirs: list of str
            """
            self._working_dir = working_dir
            self._watched_dirs = watched_dirs
            self._started = False
            self._observer = Observer()
            self._handler = FileSystemEventHandler()
            for path in watched_dirs:
                path = os.path.abspath(os.path.join(working_dir, path))
                self._observer.schedule(self._handler, path, recursive=True)

        def start(self, callback):
            """
            Start watching.
            """
            if not self._started:
                def on_any_event(evt):
                    event = {
                        u'type': evt.event_type,
                        u'abs_path': os.path.abspath(evt.src_path),
                        u'rel_path': os.path.relpath(evt.src_path, self._working_dir),
                        u'is_directory': evt.is_directory,
                    }

                    from twisted.internet import reactor
                    reactor.callFromThread(callback, event)

                self._handler.on_any_event = on_any_event
                self._observer.start()

        def stop(self):
            """
            Stop watching.
            """
            if self._started:
                self._observer.stop()
                self._observer.join()
                self._started = False

        def is_started(self):
            """
            Check if the watcher is running.
            """
            return self._started

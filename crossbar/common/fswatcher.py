#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

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
                        'type': evt.event_type,
                        'abs_path': os.path.abspath(evt.src_path),
                        'rel_path': os.path.relpath(evt.src_path, self._working_dir),
                        'is_directory': evt.is_directory,
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

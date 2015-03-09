#####################################################################################
#
#  Copyright (C) Tavendo GmbH
#
#  Unless a separate license agreement exists between you and Tavendo GmbH (e.g. you
#  have purchased a commercial license), the license terms below apply.
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
import pyinotify

__all__ = ('DirWatcher',)


class _EventHandler(pyinotify.ProcessEvent):

    def __init__(self, callback, notify_once):
        pyinotify.ProcessEvent.__init__(self)
        self._callback = callback
        self._notify_once = notify_once
        self._notifications = 0

    def process_IN_CREATE(self, event):
        if not self._notify_once or self._notifications == 0:
            self._callback({'type': 'create', 'path': event.pathname})
            self._notifications += 1

    def process_IN_MODIFY(self, event):
        if not self._notify_once or self._notifications == 0:
            self._callback({'type': 'modify', 'path': event.pathname})
            self._notifications += 1

    def process_IN_DELETE(self, event):
        if not self._notify_once or self._notifications == 0:
            self._callback({'type': 'delete', 'path': event.pathname})
            self._notifications += 1


class DirWatcher:

    """
    Watches a directory for file system changes.
    """

    def __init__(self, dirs=['.'], recurse=True, asynch=True, timeout=200, notify_once=False):
        """
        Directory change watcher.

        After creation, you will call `loop()` providing a callback that fires whenever
        changes are detected. If running `asynch == True`, you can `stop()` the loop,
        even when no change events happen (which is generally, desirable).

        To use this class with Twisted, you should `deferToThread` the call to `loop()`.

        :param dir: Directory to watch.
        :type dir: str
        :param recurse: Watch all subdirectories also - recursively.
        :type recurse: bool
        :param asynch: Iff `True`, use IOCP looping, which can be interrupted by
           calling `stop()`.
        :type asynch: bool
        :param timeout: Iff `asynch == True`, the timeout in ms for the event loop.
        :type timeout: int
        """
        self._dirs = dirs
        self._recurse = recurse
        self._asynch = asynch
        self._timeout = timeout
        self._notify_once = notify_once
        self._stopped = False
        self._wm = pyinotify.WatchManager()
        self._mask = pyinotify.IN_CREATE | pyinotify.IN_MODIFY | pyinotify.IN_DELETE

    def stop(self):
        """
        Stop watching.

        The behavior depends on the setting of `asynch`. If `asynch == False`, the
        watching will only stop upon detecting the next change. If `asynch == True`,
        the watching will stop on the next timeout or change - whichever comes first.

        In all cases, calling `stop()` returns immediately (won't block).
        """
        self._stopped = True

    def loop(self, callback):
        """
        Enter watching.

        :param callback: The callback fired when a change is detected.
        :type callback: callable
        """
        if self._asynch:
            self._loop_asynchronous(callback)
        else:
            self._loop_synchronous(callback)

    def _loop_synchronous(self, callback):
        handler = _EventHandler(callback, self._notify_once)
        notifier = pyinotify.Notifier(self._wm, handler)

        # add directories to watch
        for directory in self._dirs:
            self._wm.add_watch(os.path.abspath(directory), self._mask, rec=self._recurse)

        notifier.loop()

    def _loop_asynchronous(self, callback):
        handler = _EventHandler(callback, self._notify_once)
        notifier = pyinotify.Notifier(self._wm, handler, timeout=self._timeout)

        # add directories to watch
        for directory in self._dirs:
            self._wm.add_watch(os.path.abspath(directory), self._mask, rec=self._recurse)

        while not self._stopped:
            notifier.process_events()

            # loop in case more events appear while we are processing
            while notifier.check_events():
                notifier.read_events()
                notifier.process_events()


if __name__ == '__main__':
    dw = DirWatcher(asynch=True, timeout=1000)
#   dw = DirWatcher(asynch = False)

    def log(r):
        print(r)
    dw.loop(log)

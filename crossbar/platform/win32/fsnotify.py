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

import os
import os.path

import pywintypes

import win32file
import win32con
import win32event

import ntsecuritycon


class DirWatcher:

    """
    Watches a directory for file system changes.

    See also:
      * http://msdn.microsoft.com/en-us/library/windows/desktop/aa365465%28v=vs.85%29.aspx
      * http://www.themacaque.com/?p=859
      * http://timgolden.me.uk/python/win32_how_do_i/watch_directory_for_changes.html
    """

    _ACTIONS = {1: 'CREATE',
                2: 'DELETE',
                3: 'MODIFY',
                4: 'MOVEFROM',
                5: 'MOVETO'}

    def __init__(self, dir='.', recurse=True, asynch=True, timeout=200):
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

        self._dir = os.path.abspath(dir)
        self._recurse = recurse
        self._stopped = False
        self._asynch = asynch
        self._timeout = timeout

        # listening filter
        self._filter = win32con.FILE_NOTIFY_CHANGE_FILE_NAME | \
            win32con.FILE_NOTIFY_CHANGE_DIR_NAME | \
            win32con.FILE_NOTIFY_CHANGE_ATTRIBUTES | \
            win32con.FILE_NOTIFY_CHANGE_SIZE | \
            win32con.FILE_NOTIFY_CHANGE_LAST_WRITE | \
            win32con.FILE_NOTIFY_CHANGE_SECURITY | \
            0

        fflags = win32con.FILE_FLAG_BACKUP_SEMANTICS
        if self._asynch:
            fflags |= win32con.FILE_FLAG_OVERLAPPED

        # base directory object watched
        self._hdir = win32file.CreateFile(self._dir,
                                          ntsecuritycon.FILE_LIST_DIRECTORY,
                                          win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE | win32con.FILE_SHARE_DELETE,
                                          None,
                                          win32con.OPEN_EXISTING,
                                          fflags,
                                          None)

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
        while not self._stopped:
            # This will block until notification.
            results = win32file.ReadDirectoryChangesW(self._hdir,
                                                      8192,
                                                      self._recurse,
                                                      self._filter,
                                                      None,
                                                      None)
            r = [(DirWatcher._ACTIONS.get(x[0], "UNKNOWN"), x[1]) for x in results]
            if len(r) > 0:
                callback(r)

    def _loop_asynchronous(self, callback):
        buf = win32file.AllocateReadBuffer(8192)
        overlapped = pywintypes.OVERLAPPED()
        overlapped.hEvent = win32event.CreateEvent(None, 0, 0, None)

        while not self._stopped:

            win32file.ReadDirectoryChangesW(self._hdir,
                                            buf,
                                            self._recurse,
                                            self._filter,
                                            overlapped)

            #
            # This will block until notification OR timeout.
            #
            rc = win32event.WaitForSingleObject(overlapped.hEvent, self._timeout)
            if rc == win32event.WAIT_OBJECT_0:
                # got event: determine data length ..
                n = win32file.GetOverlappedResult(self._hdir, overlapped, True)
                if n:
                    # retrieve data
                    results = win32file.FILE_NOTIFY_INFORMATION(buf, n)
                    r = [(DirWatcher._ACTIONS.get(x[0], "UNKNOWN"), x[1]) for x in results]
                    if len(r) > 0:
                        callback(r)
                else:
                    # directory handled was closed
                    self._stopped = True
            else:
                # timeout
                pass


if __name__ == '__main__':
    dw = DirWatcher(asynch=False)

    def log(r):
        print(r)
    dw.loop(log)

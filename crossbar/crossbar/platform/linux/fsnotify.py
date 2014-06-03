###############################################################################
##
##  Copyright (C) 2014 Tavendo GmbH
##
##  This program is free software: you can redistribute it and/or modify
##  it under the terms of the GNU Affero General Public License, version 3,
##  as published by the Free Software Foundation.
##
##  This program is distributed in the hope that it will be useful,
##  but WITHOUT ANY WARRANTY; without even the implied warranty of
##  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
##  GNU Affero General Public License for more details.
##
##  You should have received a copy of the GNU Affero General Public License
##  along with this program. If not, see <http://www.gnu.org/licenses/>.
##
###############################################################################

class DirWatcher:
   """
   Watches a directory for file system changes.
   """

   def __init__(self, dir = '.', recurse = True, asynch = True, timeout = 200):
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
      raise Exception("not implemented")
   

   def stop(self):
      """
      Stop watching.

      The behavior depends on the setting of `asynch`. If `asynch == False`, the
      watching will only stop upon detecting the next change. If `asynch == True`,
      the watching will stop on the next timeout or change - whichever comes first.

      In all cases, calling `stop()` returns immediately (won't block).
      """
      raise Exception("not implemented")


   def loop(self, callback):
      """
      Enter watching.

      :param callback: The callback fired when a change is detected.
      :type callback: callable
      """
      raise Exception("not implemented")

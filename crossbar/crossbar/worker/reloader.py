###############################################################################
##
##  Copyright (C) 2014 Tavendo GmbH
##
##  Licensed under the Apache License, Version 2.0 (the "License");
##  you may not use this file except in compliance with the License.
##  You may obtain a copy of the License at
##
##      http://www.apache.org/licenses/LICENSE-2.0
##
##  Unless required by applicable law or agreed to in writing, software
##  distributed under the License is distributed on an "AS IS" BASIS,
##  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
##  See the License for the specific language governing permissions and
##  limitations under the License.
##
###############################################################################

from __future__ import absolute_import

__all__ = ['TrackingModuleReloader']

import sys

try:
   reload
except NameError:
   # Python 3
   from imp import reload


class TrackingModuleReloader:
   """
   A tracking module reloader.

   This will track modules loaded _after_ a snapshot (point in time), and
   later allow to force reload of exactly those modules that have been (first)
   loaded after that point in time.
   """

   def __init__(self, silence = False):
      """
      Ctor.

      :param silence: Disable any log messages.
      :type silence: bool
      """
      self._silence = silence
      self.snapshot()


   def snapshot(self):
      """
      Establish a snapshot - that is, remember which modules are currently
      loaded. Later, when reload() is called, only modules imported later
      will be (forcefully) reloaded.
      """
      self._old_modules = sys.modules.copy()


   def reload(self):
      """
      Trigger reloading of all modules imported later than the last snapshot
      established.

      :returns int -- Number of modules reloaded.
      """
      current_modules = sys.modules
      maybe_dirty_modules = set(current_modules.keys()) - set(self._old_modules.keys())
      if len(maybe_dirty_modules):
         if not self._silence:
            print("Reloading {} possibly changed modules".format(len(maybe_dirty_modules)))
         for module in maybe_dirty_modules:
            print("Reloading module {}".format(module))
            reload(current_modules[module])
      else:
         if not self._silence:
            print("No modules to reload")
      return len(maybe_dirty_modules)

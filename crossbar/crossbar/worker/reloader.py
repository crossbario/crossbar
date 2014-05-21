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

import os
import sys

try:
   reload
except NameError:
   # Python 3
   from imp import reload



def get_module_path_and_mtime(m):
   """
   Given a Python module, returns a pair (source file, source file mtime).

   :param m: A Python module instance.
   :type m: obj
   """
   res = (None, None)
   if m and hasattr(m, '__file__') and (m.__file__.endswith('.py') or m.__file__.endswith('.pyc')):
      f = m.__file__
      if f.endswith('.pyc'):
         f = f[:-1]
      try:
         mtime = os.stat(f)[8]
      except:
         res = (f, None)
      else:
         res = (f, mtime)
   return res



class TrackingModuleReloader:
   """
   A tracking module reloader.

   This will track modules loaded _after_ a snapshot (point in time), and
   later allow to force reload of exactly those modules that have been (first)
   loaded after that point in time.
   """

   def __init__(self, silence = False, use_mtimes = True):
      """
      Ctor.

      :param silence: Disable any log messages.
      :type silence: bool
      :param use_mtimes: If `True`, try to use file modification times to limit
                         module reloading to actually changed files.
      :type use_mtimes: bool
      """
      self._silence = silence
      self._use_mtimes = use_mtimes
      self.snapshot()


   def snapshot(self):
      """
      Establish a snapshot - that is, remember which modules are currently
      loaded. Later, when reload() is called, only modules imported later
      will be (forcefully) reloaded.
      """
      self._modules = sys.modules.copy()

      ## do mtime tracking ..
      if self._use_mtimes:
         self._module_mtimes = {}
         for mod_name, mod in self._modules.items():
            self._module_mtimes[mod_name] = get_module_path_and_mtime(mod)


   def reload(self):
      """
      Trigger reloading of all modules imported later than the last snapshot
      established.

      :returns int -- Number of modules reloaded.
      """
      current_modules = sys.modules
      maybe_dirty_modules = set(current_modules.keys()) - set(self._modules.keys())
      reload_modules = []

      ## use tracked mtimes to restrict set of actually reloaded modules, while
      ## trying to be conservative (if stuff fails or cannot be determined, opt
      ## for reloading the module -- even if it actually hasn't changed)
      ##
      if self._use_mtimes:
         for mod_name in maybe_dirty_modules:
            m = current_modules[mod_name]

            if mod_name in self._module_mtimes:

               f, new_mtime = get_module_path_and_mtime(m)
               _, old_mtime = self._module_mtimes[mod_name]

               if new_mtime == old_mtime:
                  if not self._silence:
                     print("Module {} unchanged".format(mod_name))
               else:
                  self._module_mtimes[mod_name] = (f, new_mtime)
                  reload_modules.append(mod_name)
                  if not self._silence:
                     print("Change of module {} detected (file {}).".format(mod_name, f))
            else:
               self._module_mtimes[mod_name] = get_module_path_and_mtime(m)
               reload_modules.append(mod_name)
               if not self._silence:
                  print("Tracking new module {}".format(mod_name))
      else:
         reload_modules = maybe_dirty_modules


      if len(reload_modules):
         if not self._silence:
            print("Reloading {} possibly changed modules".format(len(reload_modules)))
         for module in reload_modules:
            print("Reloading module {}".format(module))

            ## this is doing the actual work
            ##
            reload(current_modules[module])
      else:
         if not self._silence:
            print("No modules to reload")

      return reload_modules

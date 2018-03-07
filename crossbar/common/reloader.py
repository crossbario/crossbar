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
import sys

from txaio import make_logger

try:
    reload
except NameError:
    # Python 3
    from imp import reload

__all__ = ('TrackingModuleReloader',)


def get_module_path_and_mtime(m):
    """
    Given a Python module, returns a pair (source file, source file mtime).

    :param m: A Python module instance.
    :type m: obj
    """
    res = (None, None)
    if m and getattr(m, '__file__', None) and (m.__file__.endswith('.py') or m.__file__.endswith('.pyc')):
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

    log = make_logger()

    def __init__(self, use_mtimes=True, snapshot=True):
        """

        :param use_mtimes: If `True`, try to use file modification times to limit
                           module reloading to actually changed files.
        :type use_mtimes: bool
        """
        self._use_mtimes = use_mtimes
        if snapshot:
            self.snapshot()

    def snapshot(self):
        """
        Establish a snapshot - that is, remember which modules are currently
        loaded. Later, when reload() is called, only modules imported later
        will be (forcefully) reloaded.
        """
        self._modules = sys.modules.copy()

        # do mtime tracking ..
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

        # use tracked mtimes to restrict set of actually reloaded modules, while
        # trying to be conservative (if stuff fails or cannot be determined, opt
        # for reloading the module -- even if it actually hasn't changed)
        #
        if self._use_mtimes:
            for mod_name in maybe_dirty_modules:
                m = current_modules[mod_name]

                if mod_name in self._module_mtimes:

                    f, new_mtime = get_module_path_and_mtime(m)
                    _, old_mtime = self._module_mtimes[mod_name]

                    if new_mtime == old_mtime:
                        self.log.debug("Module {mod_name} unchanged", mod_name=mod_name)
                    else:
                        self._module_mtimes[mod_name] = (f, new_mtime)
                        reload_modules.append(mod_name)
                        self.log.debug("Change of module {mod_name} detected (file {f}).", mod_name=mod_name, f=f)
                else:
                    self._module_mtimes[mod_name] = get_module_path_and_mtime(m)
                    reload_modules.append(mod_name)
                    self.log.debug("Tracking new module {mod_name}", mod_name=mod_name)
        else:
            reload_modules = maybe_dirty_modules

        if len(reload_modules):
            self.log.debug("Reloading {modules} possibly changed modules", modules=len(reload_modules))
            for module in reload_modules:
                self.log.debug("Reloading module {module}", module=module)

                # this is doing the actual work
                #
                reload(current_modules[module])
        else:
            self.log.debug("No modules to reload")

        return reload_modules

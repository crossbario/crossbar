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
import sys
import pkg_resources

from twisted.python import log
from twisted.internet.defer import DeferredList, inlineCallbacks

from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.types import PublishOptions, \
    RegisterOptions

from crossbar.common.reloader import TrackingModuleReloader
from crossbar.common.process import NativeProcessSession

from crossbar.common.processinfo import _HAS_PSUTIL
if _HAS_PSUTIL:
    import psutil

__all__ = ('NativeWorkerSession',)


class NativeWorkerSession(NativeProcessSession):

    """
    A native Crossbar.io worker process. The worker will be connected
    to the node's management router running inside the node controller
    via WAMP-over-stdio.
    """

    WORKER_TYPE = 'native'

    def onConnect(self):
        """
        Called when the worker has connected to the node's management router.
        """
        self._uri_prefix = 'crossbar.node.{}.worker.{}'.format(self.config.extra.node, self.config.extra.worker)

        NativeProcessSession.onConnect(self, False)

        self._module_tracker = TrackingModuleReloader(debug=True)

        self.join(self.config.realm)

    @inlineCallbacks
    def onJoin(self, details, publish_ready=True):
        """
        Called when worker process has joined the node's management realm.
        """
        yield NativeProcessSession.onJoin(self, details)

        procs = [
            'get_cpu_affinity',
            'set_cpu_affinity',
            'get_pythonpath',
            'add_pythonpath',
        ]

        dl = []
        for proc in procs:
            uri = '{}.{}'.format(self._uri_prefix, proc)
            if self.debug:
                log.msg("Registering procedure '{}'".format(uri))
            dl.append(self.register(getattr(self, proc), uri, options=RegisterOptions(details_arg='details')))

        regs = yield DeferredList(dl)

        if self.debug:
            log.msg("{} registered {} procedures".format(self.__class__.__name__, len(regs)))

        if publish_ready:
            yield self.publish_ready()

    @inlineCallbacks
    def publish_ready(self):
        # signal that this worker is ready for setup. the actual setup procedure
        # will either be sequenced from the local node configuration file or remotely
        # from a management service
        #
        pub = yield self.publish('crossbar.node.{}.on_worker_ready'.format(self.config.extra.node),
                                 {'type': self.WORKER_TYPE, 'id': self.config.extra.worker, 'pid': os.getpid()},
                                 options=PublishOptions(acknowledge=True))

        if self.debug:
            log.msg("NativeWorker ready event published ({})".format(pub))

    def get_cpu_affinity(self, details=None):
        """
        Get CPU affinity of this process.

        :returns list -- List of CPU IDs the process affinity is set to.
        """
        if self.debug:
            log.msg("{}.get_cpu_affinity".format(self.__class__.__name__))

        if not _HAS_PSUTIL:
            emsg = "ERROR: unable to get CPU affinity - required package 'psutil' is not installed"
            log.msg(emsg)
            raise ApplicationError("crossbar.error.feature_unavailable", emsg)

        try:
            p = psutil.Process(os.getpid())
            current_affinity = p.cpu_affinity()
        except Exception as e:
            emsg = "ERROR: could not get CPU affinity ({})".format(e)
            log.msg(emsg)
            raise ApplicationError("crossbar.error.runtime_error", emsg)
        else:
            res = {'affinity': current_affinity}
            return res

    def set_cpu_affinity(self, cpus, details=None):
        """
        Set CPU affinity of this process.

        :param cpus: List of CPU IDs to set process affinity to.
        :type cpus: list
        """
        if self.debug:
            log.msg("{}.set_cpu_affinity".format(self.__class__.__name__))

        if not _HAS_PSUTIL:
            emsg = "ERROR: unable to set CPU affinity - required package 'psutil' is not installed"
            log.msg(emsg)
            raise ApplicationError("crossbar.error.feature_unavailable", emsg)

        try:
            p = psutil.Process(os.getpid())
            p.cpu_affinity(cpus)
            new_affinity = p.cpu_affinity()
        except Exception as e:
            emsg = "ERROR: could not set CPU affinity ({})".format(e)
            log.msg(emsg)
            raise ApplicationError("crossbar.error.runtime_error", emsg)
        else:

            # publish info to all but the caller ..
            #
            cpu_affinity_set_topic = 'crossbar.node.{}.worker.{}.on_cpu_affinity_set'.format(self.config.extra.node, self.config.extra.worker)
            cpu_affinity_set_info = {
                'affinity': new_affinity,
                'who': details.caller
            }
            self.publish(cpu_affinity_set_topic, cpu_affinity_set_info, options=PublishOptions(exclude=[details.caller]))

            # .. and return info directly to caller
            #
            return cpu_affinity_set_info

    def get_pythonpath(self, details=None):
        """
        Returns the current Python module search paths.

        :returns list -- List of module search paths.
        """
        if self.debug:
            log.msg("{}.get_pythonpath".format(self.__class__.__name__))

        return sys.path

    def add_pythonpath(self, paths, prepend=True, details=None):
        """
        Add paths to Python module search paths.

        :param paths: List of paths. Relative paths will be resolved relative
                      to the node directory.
        :type paths: list
        :param prepend: If `True`, prepend the given paths to the current paths.
                        Otherwise append.
        :type prepend: bool
        """
        if self.debug:
            log.msg("{}.add_pythonpath".format(self.__class__.__name__))

        paths_added = []
        for p in paths:
            # transform all paths (relative to cbdir) into absolute paths
            #
            path_to_add = os.path.abspath(os.path.join(self.config.extra.cbdir, p))
            if os.path.isdir(path_to_add):
                paths_added.append({'requested': p, 'resolved': path_to_add})
            else:
                emsg = "ERROR: cannot add Python search path '{}' - resolved path '{}' is not a directory".format(p, path_to_add)
                log.msg(emsg)
                raise ApplicationError('crossbar.error.invalid_argument', emsg, requested=p, resolved=path_to_add)

        # now extend python module search path
        #
        paths_added_resolved = [p['resolved'] for p in paths_added]
        if prepend:
            sys.path = paths_added_resolved + sys.path
        else:
            sys.path.extend(paths_added_resolved)

        # "It is important to note that the global working_set object is initialized from
        # sys.path when pkg_resources is first imported, but is only updated if you do all
        # future sys.path manipulation via pkg_resources APIs. If you manually modify sys.path,
        # you must invoke the appropriate methods on the working_set instance to keep it in sync."
        #
        # @see: https://pythonhosted.org/setuptools/pkg_resources.html#workingset-objects
        #
        for p in paths_added_resolved:
            pkg_resources.working_set.add_entry(p)

        # publish event "on_pythonpath_add" to all but the caller
        #
        topic = 'crossbar.node.{}.worker.{}.on_pythonpath_add'.format(self.config.extra.node, self.config.extra.worker)
        res = {
            'paths': sys.path,
            'paths_added': paths_added,
            'prepend': prepend,
            'who': details.caller
        }
        self.publish(topic, res, options=PublishOptions(exclude=[details.caller]))

        return res

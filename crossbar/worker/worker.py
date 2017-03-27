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
import pkg_resources
import jinja2
import signal

from twisted.internet.error import ReactorNotRunning
from twisted.internet.defer import DeferredList, inlineCallbacks

from autobahn.util import utcnow
from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.types import PublishOptions, RegisterOptions

from txaio import make_logger

from crossbar.common.reloader import TrackingModuleReloader
from crossbar.common.process import NativeProcessSession
from crossbar.common.profiler import PROFILERS
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

    log = make_logger()

    def onConnect(self):
        """
        Called when the worker has connected to the node's management router.
        """
        self._worker_id = self.config.extra.worker
        self._uri_prefix = u'crossbar.worker.{}'.format(self._worker_id)

        NativeProcessSession.onConnect(self, False)

        self._module_tracker = TrackingModuleReloader()

        self._profiles = {}

        # flag indicating when worker is shutting down
        self._is_shutting_down = False

        # Jinja2 templates for Web (like WS status page et al)
        #
        templates_dir = os.path.abspath(pkg_resources.resource_filename("crossbar", "web/templates"))
        self.log.debug("Using Web templates from {templates_dir}",
                       templates_dir=templates_dir)
        self._templates = jinja2.Environment(loader=jinja2.FileSystemLoader(templates_dir))

        self.join(self.config.realm)

    @inlineCallbacks
    def onJoin(self, details, publish_ready=True):
        """
        Called when worker process has joined the node's management realm.
        """
        yield NativeProcessSession.onJoin(self, details)

        procs = [
            # orderly shutdown worker "from inside"
            'shutdown',

            # CPU affinity for this worker process
            'get_cpu_count',
            'get_cpu_affinity',
            'set_cpu_affinity',

            # PYTHONPATH used for this worker
            'get_pythonpath',
            'add_pythonpath',

            # profiling control
            'get_profilers',
            'start_profiler',
            'get_profile',
        ]

        dl = []
        for proc in procs:
            uri = u'{}.{}'.format(self._uri_prefix, proc)
            self.log.debug("Registering management API procedure {proc}", proc=uri)
            dl.append(self.register(getattr(self, proc), uri, options=RegisterOptions(details_arg='details')))

        regs = yield DeferredList(dl)

        self.log.debug("Registered {cnt} management API procedures", cnt=len(regs))

        # setup SIGTERM handler to orderly shutdown the worker
        def shutdown(sig, frame):
            self.log.warn("Native worker received SIGTERM - shutting down ..")
            self.shutdown()
        signal.signal(signal.SIGTERM, shutdown)

        # the worker is ready for work!
        if publish_ready:
            yield self.publish_ready()

    def onLeave(self, details):
        self.log.debug("Worker-to-controller session detached")
        self.disconnect()

    def onDisconnect(self):
        self.log.debug("Worker-to-controller session disconnected")

        # when the native worker is done, stop the reactor
        try:
            self._reactor.stop()
        except ReactorNotRunning:
            pass

    @inlineCallbacks
    def publish_ready(self):
        # signal that this worker is ready for setup. the actual setup procedure
        # will either be sequenced from the local node configuration file or remotely
        # from a management service
        yield self.publish(
            u'{}.on_worker_ready'.format(self._uri_prefix),
            {
                u'type': self.WORKER_TYPE,
                u'id': self.config.extra.worker,
                u'pid': os.getpid(),
            },
            options=PublishOptions(acknowledge=True)
        )

        self.log.debug("Worker '{worker}' running as PID {pid}",
                       worker=self.config.extra.worker, pid=os.getpid())

    @inlineCallbacks
    def shutdown(self, details=None):
        """
        Registered under: ``crossbar.worker.<worker_id>.shutdown``
        Event published under: ``crossbar.worker.<worker_id>.on_shutdown_requested``
        """
        if self._is_shutting_down:
            # ignore: we are already shutting down ..
            return
            # raise ApplicationError(u'crossbar.error.operation_in_progress', 'cannot shutdown - the worker is already shutting down')
        else:
            self._is_shutting_down = True

        self.log.info("Shutdown of worker requested!")

        # publish management API event
        #
        yield self.publish(
            u'{}.on_shutdown_requested'.format(self._uri_prefix),
            {
                u'who': details.caller if details else None,
                u'when': utcnow()
            },
            options=PublishOptions(exclude=details.caller if details else None, acknowledge=True)
        )

        # we now call self.leave() to initiate the clean, orderly shutdown of the native worker.
        # the call is scheduled to run on the next reactor iteration only, because we want to first
        # return from the WAMP call when this procedure is called from the node controller
        #
        self._reactor.callLater(0, self.leave)

    def get_profilers(self, details=None):
        """
        Registered under: ``crossbar.worker.<worker_id>.get_profilers``

        Returns available profilers.

        :param details: WAMP call details (auto-filled by WAMP).
        :type details: obj
        :returns: A list of profilers.
        :rtype: list of unicode
        """
        return [p.marshal() for p in PROFILERS.items()]

    def start_profiler(self, profiler, runtime=10, async=True, details=None):
        """
        Registered under: ``crossbar.worker.<worker_id>.start_profiler``

        Start a profiler producing a profile which is stored and can be
        queried later.

        :param profiler: The profiler to start, e.g. ``vmprof``.
        :type profiler: unicode
        :param runtime: Profiling duration in seconds.
        :type runtime: float
        :param async: Flag to turn on/off asynchronous mode.
        :type async: bool
        :param details: WAMP call details (auto-filled by WAMP).
        :type details: obj
        :returns: If running in synchronous mode, the profiling result. Else
            a profile ID is returned which later can be used to retrieve the profile.
        :rtype: dict or int
        """
        if profiler not in PROFILERS:
            raise Exception("no such profiler")

        profiler = PROFILERS[profiler]

        self.log.debug("Starting profiler {profiler}, running for {secs} seconds", profiler=profiler, secs=runtime)

        # run the selected profiler, producing a profile. "profile_finished" is a Deferred
        # that will fire with the actual profile recorded
        profile_id, profile_finished = profiler.start(runtime=runtime)

        on_profile_started = u'{}.on_profile_started'.format(self._uri_prefix)
        on_profile_finished = u'{}.on_profile_finished'.format(self._uri_prefix)

        if async:
            publish_options = None
        else:
            publish_options = PublishOptions(exclude=details.caller)

        self.publish(
            on_profile_started,
            {
                u'id': profile_id,
                u'who': details.caller,
                u'profiler': profiler,
                u'runtime': runtime,
                u'async': async,
            },
            options=publish_options
        )

        def on_profile_success(profile_result):
            self._profiles[profile_id] = {
                u'id': profile_id,
                u'profiler': profiler,
                u'runtime': runtime,
                u'profile': profile_result
            }

            self.publish(
                on_profile_finished,
                {
                    u'id': profile_id,
                    u'error': None,
                    u'profile': profile_result
                },
                options=publish_options
            )

            return profile_result

        def on_profile_failed(error):
            self.log.warn('profiling failed: {error}', error=error)

            self.publish(
                on_profile_finished,
                {
                    u'id': profile_id,
                    u'error': u'{0}'.format(error),
                    u'profile': None
                },
                options=publish_options
            )

            return error

        profile_finished.addCallbacks(on_profile_success, on_profile_failed)

        if async:
            # if running in async mode, immediately return the ID under
            # which the profile can be retrieved later (when it is finished)
            return profile_id
        else:
            # if running in sync mode, return only when the profiling was
            # actually finished - and return the complete profile
            return profile_finished

    def get_profile(self, profile_id, details=None):
        """
        Get a profile previously produced by a profiler run.

        This procedure is registered under WAMP URI
        ``crossbar.worker.<worker_id>.get_profile``.

        When no profile with given ID exists, a WAMP error
        ``crossbar.error.no_such_object`` is raised.
        """
        if profile_id in self._profiles:
            return self._profiles[profile_id]
        else:
            raise ApplicationError(u'crossbar.error.no_such_object', 'no profile with ID {} saved'.format(profile_id))

    def get_cpu_count(self, logical=True):
        """
        Returns the CPU core count on the machine this process is running on.

        **Usage:**

        This procedure is registered under

        * ``crossbar.worker.<worker_id>.get_cpu_count``

        **Errors:**

        The procedure may raise the following errors:

        * ``crossbar.error.feature_unavailable`` - the required support packages are not installed

        :param logical: If enabled (default), include logical CPU cores ("Hyperthreading"),
            else only count physical CPU cores.
        :type logical: bool
        :returns: The number of CPU cores.
        :rtype: int
        """
        if not _HAS_PSUTIL:
            emsg = "unable to get CPU count: required package 'psutil' is not installed"
            self.log.warn(emsg)
            raise ApplicationError(u"crossbar.error.feature_unavailable", emsg)

        return psutil.cpu_count(logical=logical)

    def get_cpu_affinity(self, details=None):
        """
        Get CPU affinity of this process.

        **Usage:**

        This procedure is registered under

        * ``crossbar.worker.<worker_id>.get_cpu_affinity``

        **Errors:**

        The procedure may raise the following errors:

        * ``crossbar.error.feature_unavailable`` - the required support packages are not installed
        * ``crossbar.error.runtime_error`` - the CPU affinity could not be determined for some reason

        :returns: List of CPU IDs the process affinity is set to.
        :rtype: list of int
        """
        if not _HAS_PSUTIL:
            emsg = "unable to get CPU affinity: required package 'psutil' is not installed"
            self.log.warn(emsg)
            raise ApplicationError(u"crossbar.error.feature_unavailable", emsg)

        try:
            p = psutil.Process(os.getpid())
            current_affinity = p.cpu_affinity()
        except Exception as e:
            emsg = "Could not get CPU affinity: {}".format(e)
            self.log.failure(emsg)
            raise ApplicationError(u"crossbar.error.runtime_error", emsg)
        else:
            return current_affinity

    def set_cpu_affinity(self, cpus, details=None):
        """
        Set CPU affinity of this process.

        **Usage:**

        This procedure is registered under

        * ``crossbar.worker.<worker_id>.set_cpu_affinity``

        **Errors:**

        The procedure may raise the following errors:

        * ``crossbar.error.feature_unavailable`` - the required support packages are not installed

        **Events:**

        When the CPU affinity has been successfully set, an event is published to

        * ``crossbar.node.{}.worker.{}.on_cpu_affinity_set``

        :param cpus: List of CPU IDs to set process affinity to. Each CPU ID must be
            from the list `[0 .. N_CPUs]`, where N_CPUs can be retrieved via
            ``crossbar.worker.<worker_id>.get_cpu_count``.
        :type cpus: list of int
        """
        if not _HAS_PSUTIL:
            emsg = "Unable to set CPU affinity: required package 'psutil' is not installed"
            self.log.warn(emsg)
            raise ApplicationError(u"crossbar.error.feature_unavailable", emsg)

        try:
            p = psutil.Process(os.getpid())
            p.cpu_affinity(cpus)
            new_affinity = p.cpu_affinity()
        except Exception as e:
            emsg = "Could not set CPU affinity: {}".format(e)
            self.log.failure(emsg)
            raise ApplicationError(u"crossbar.error.runtime_error", emsg)
        else:

            # publish info to all but the caller ..
            #
            cpu_affinity_set_topic = u'{}.on_cpu_affinity_set'.format(self._uri_prefix)
            cpu_affinity_set_info = {
                u'affinity': new_affinity,
                u'who': details.caller
            }
            self.publish(cpu_affinity_set_topic, cpu_affinity_set_info, options=PublishOptions(exclude=details.caller))

            # .. and return info directly to caller
            #
            return new_affinity

    def get_pythonpath(self, details=None):
        """
        Returns the current Python module search paths.

        This procedure is registered under WAMP URI
        ``crossbar.worker.<worker_id>.get_pythonpath``.

        :returns: The current module search paths.
        :rtype: list of unicode
        """
        self.log.debug("{klass}.get_pythonpath", klass=self.__class__.__name__)
        return sys.path

    def add_pythonpath(self, paths, prepend=True, details=None):
        """
        Add paths to Python module search paths.

        This procedure is registered under WAMP URI
        ``crossbar.worker.<worker_id>.add_pythonpath``.

        :param paths: List of paths. Relative paths will be resolved relative
                      to the node directory.
        :type paths: list of unicode
        :param prepend: If `True`, prepend the given paths to the current paths.
                        Otherwise append.
        :type prepend: bool
        """
        self.log.debug("{klass}.add_pythonpath", klass=self.__class__.__name__)

        paths_added = []
        for p in paths:
            # transform all paths (relative to cbdir) into absolute paths
            #
            path_to_add = os.path.abspath(os.path.join(self.config.extra.cbdir, p))
            if os.path.isdir(path_to_add):
                paths_added.append({'requested': p, 'resolved': path_to_add})
            else:
                emsg = "Cannot add Python search path '{}': resolved path '{}' is not a directory".format(p, path_to_add)
                self.log.error(emsg)
                raise ApplicationError(u'crossbar.error.invalid_argument', emsg, requested=p, resolved=path_to_add)

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
        topic = u'{}.on_pythonpath_add'.format(self._uri_prefix)
        res = {
            u'paths': sys.path,
            u'paths_added': paths_added,
            u'prepend': prepend,
            u'who': details.caller
        }
        self.publish(topic, res, options=PublishOptions(exclude=details.caller))

        return res

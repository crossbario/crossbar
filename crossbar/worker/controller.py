#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import os
import sys
import pkg_resources
import signal
from typing import Optional, List

import jinja2
from jinja2.sandbox import SandboxedEnvironment
from jinja2 import Environment

from twisted.internet.error import ReactorNotRunning
from twisted.internet.defer import inlineCallbacks

from autobahn.util import utcnow, hltype
from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.types import PublishOptions, Challenge
from autobahn import wamp

from txaio import make_logger

from crossbar.common.reloader import TrackingModuleReloader
from crossbar.common.process import NativeProcess
from crossbar.common.profiler import PROFILERS
from crossbar.common.key import _read_release_key
from crossbar._util import term_print

__all__ = ('WorkerController', )


class WorkerController(NativeProcess):
    """
    A native Crossbar.io worker process. The worker will be connected
    to the node's management router running inside the node controller
    via WAMP-over-stdio.
    """

    WORKER_TYPE = 'native'

    log = make_logger()

    def __init__(self, config=None, reactor=None, personality=None):
        # base ctor
        NativeProcess.__init__(self, config=config, reactor=reactor, personality=personality)

        # Release (public) key
        self._release_pubkey = _read_release_key()

    def onConnect(self):
        """
        Called when the worker has connected to the node's management router.
        """
        NativeProcess.onConnect(self, False)

        self._module_tracker = TrackingModuleReloader(snapshot=False)

        self._profiles = {}

        # flag indicating when worker is shutting down
        self._is_shutting_down = False

        # Jinja2 templates for Web (like WS status page et al)
        #
        self._templates_dir = []
        for package, directory in self.personality.TEMPLATE_DIRS:
            dir_path = os.path.abspath(pkg_resources.resource_filename(package, directory))
            self._templates_dir.append(dir_path)
        self.log.debug("Using Web templates from {template_dirs}", template_dirs=self._templates_dir)

        # FIXME: make configurable, but default should remain SandboxedEnvironment for security
        if True:
            # The sandboxed environment. It works like the regular environment but tells the compiler to
            # generate sandboxed code.
            # https://jinja.palletsprojects.com/en/2.11.x/sandbox/#jinja2.sandbox.SandboxedEnvironment
            self._templates = SandboxedEnvironment(loader=jinja2.FileSystemLoader(self._templates_dir),
                                                   autoescape=True)
        else:
            self._templates = Environment(loader=jinja2.FileSystemLoader(self._templates_dir), autoescape=True)

        self.join(self.config.realm)

    @property
    def templates_dir(self) -> List[str]:
        """
        Template directories used in the Jinja2 rendering environment.

        :return:
        """
        return self._templates_dir

    def templates(self) -> Environment:
        """
        Jinja2 rendering environment.

        :return: jinja2.Environment for the built-in templates from personality.TEMPLATE_DIRS
        """
        return self._templates

    @inlineCallbacks
    def onJoin(self, details, publish_ready=True):
        """
        Called when worker process has joined the node management realm.
        """
        yield NativeProcess.onJoin(self, details)

        # above upcall registers all our "@wamp.register(None)" methods

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
        yield self.publish('{}.on_worker_ready'.format(self._uri_prefix), {
            'type': self.WORKER_TYPE,
            'id': self.config.extra.worker,
            'pid': os.getpid(),
        },
                           options=PublishOptions(acknowledge=True))

        self.log.debug("Worker '{worker}' running as PID {pid}", worker=self.config.extra.worker, pid=os.getpid())
        term_print('CROSSBAR[{}]:WORKER_STARTED'.format(self.config.extra.worker))

    @wamp.register(None)
    @inlineCallbacks
    def shutdown(self, details=None):
        """
        Registered under: ``crossbar.worker.<worker_id>.shutdown``
        Event published under: ``crossbar.worker.<worker_id>.on_shutdown_requested``
        """
        if self._is_shutting_down:
            # ignore: we are already shutting down ..
            return
            # raise ApplicationError('crossbar.error.operation_in_progress', 'cannot shutdown - the worker is already shutting down')
        else:
            self._is_shutting_down = True

        self.log.info("Shutdown of worker requested!")

        # publish management API event
        #
        yield self.publish('{}.on_shutdown_requested'.format(self._uri_prefix), {
            'who': details.caller if details else None,
            'when': utcnow()
        },
                           options=PublishOptions(exclude=details.caller if details else None, acknowledge=True))

        # we now call self.leave() to initiate the clean, orderly shutdown of the native worker.
        # the call is scheduled to run on the next reactor iteration only, because we want to first
        # return from the WAMP call when this procedure is called from the node controller
        #
        self._reactor.callLater(0, self.leave)

    @wamp.register(None)
    def set_node_id(self, node_id, details=None):
        self._node_id = node_id

    @wamp.register(None)
    def get_node_id(self, details=None):
        return self._node_id

    @wamp.register(None)
    def get_profilers(self, details=None):
        """
        Registered under: ``crossbar.worker.<worker_id>.get_profilers``

        Returns available profilers.

        :param details: WAMP call details (auto-filled by WAMP).
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :returns: A list of profilers.
        :rtype: list[str]
        """
        return [p.marshal() for p in PROFILERS.items()]

    @wamp.register(None)
    def start_profiler(self, profiler='vmprof', runtime=10, start_async=True, details=None):
        """
        Registered under: ``crossbar.worker.<worker_id>.start_profiler``

        Start a profiler producing a profile which is stored and can be
        queried later.

        :param profiler: The profiler to start, e.g. ``vmprof``.
        :type profiler: str

        :param runtime: Profiling duration in seconds.
        :type runtime: float

        :param start_async: Flag to turn on/off asynchronous mode.
        :type start_async: bool

        :param details: WAMP call details (auto-filled by WAMP).
        :type details: :class:`autobahn.wamp.types.CallDetails`

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

        on_profile_started = '{}.on_profile_started'.format(self._uri_prefix)
        on_profile_finished = '{}.on_profile_finished'.format(self._uri_prefix)

        if start_async:
            publish_options = None
        else:
            publish_options = PublishOptions(exclude=details.caller)

        profile_started = {
            'id': profile_id,
            'who': details.caller,
            'profiler': profiler,
            'runtime': runtime,
            'async': start_async,
        }

        self.publish(on_profile_started, profile_started, options=publish_options)

        def on_profile_success(profile_result):
            self._profiles[profile_id] = {
                'id': profile_id,
                'profiler': profiler,
                'runtime': runtime,
                'profile': profile_result
            }

            self.publish(on_profile_finished, {
                'id': profile_id,
                'error': None,
                'profile': profile_result
            },
                         options=publish_options)

            return profile_result

        def on_profile_failed(error):
            self.log.warn('profiling failed: {error}', error=error)

            self.publish(on_profile_finished, {
                'id': profile_id,
                'error': '{0}'.format(error),
                'profile': None
            },
                         options=publish_options)

            return error

        profile_finished.addCallbacks(on_profile_success, on_profile_failed)

        if start_async:
            # if running in async mode, immediately return the ID under
            # which the profile can be retrieved later (when it is finished)
            return profile_started
        else:
            # if running in sync mode, return only when the profiling was
            # actually finished - and return the complete profile
            return profile_finished

    @wamp.register(None)
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
            raise ApplicationError('crossbar.error.no_such_object', 'no profile with ID {} saved'.format(profile_id))

    @wamp.register(None)
    def get_pythonpath(self, details=None):
        """
        Returns the current Python module search paths.

        This procedure is registered under WAMP URI
        ``crossbar.worker.<worker_id>.get_pythonpath``.

        :returns: The current module search paths.
        :rtype: list[str]
        """
        self.log.debug("{klass}.get_pythonpath", klass=self.__class__.__name__)
        return sys.path

    @wamp.register(None)
    def add_pythonpath(self, paths, prepend=True, details=None):
        """
        Add paths to Python module search paths.

        This procedure is registered under WAMP URI
        ``crossbar.worker.<worker_id>.add_pythonpath``.

        :param paths: List of paths. Relative paths will be resolved relative
                      to the node directory.
        :type paths: list[str]
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
                emsg = "Cannot add Python search path '{}': resolved path '{}' is not a directory".format(
                    p, path_to_add)
                self.log.error(emsg)
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
        topic = '{}.on_pythonpath_add'.format(self._uri_prefix)
        res = {'paths': sys.path, 'paths_added': paths_added, 'prepend': prepend, 'who': details.caller}
        self.publish(topic, res, options=PublishOptions(exclude=details.caller))

        return res

    @inlineCallbacks
    def sign_challenge(self, challenge: Challenge, channel_id: Optional[bytes], channel_id_type=Optional[str]):
        """
        Call into node controller (over secure controller-worker pipe) to sign challenge with node key.

        :param challenge:
        :param channel_id:
        :param channel_id_type:
        :return:
        """
        self.log.info('{func}() ...', func=hltype(self.sign_challenge))
        result = yield self.call("crossbar.sign_challenge", challenge.method, challenge.extra, channel_id,
                                 channel_id_type)
        self.log.info('{func}(): {result}', func=hltype(self.sign_challenge), result=result)
        return result

    @inlineCallbacks
    def get_public_key(self):
        """
        Call into node controller (over secure controller-worker pipe) to get the node's public key.

        :return:
        """
        self.log.info('{func}() ...', func=hltype(self.get_public_key))
        result = yield self.call("crossbar.get_public_key")
        self.log.info('{func}(): {result}', func=hltype(self.get_public_key), result=result)
        return result

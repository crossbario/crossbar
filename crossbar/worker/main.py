#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import binascii
import argparse
import importlib

import cbor2

from twisted.internet.error import ReactorNotRunning

from crossbar._util import hl, hlid, hltype, _add_debug_options, term_print

try:
    import vmprof
    _HAS_VMPROF = True
except ImportError:
    _HAS_VMPROF = False

__all__ = ('_run_command_exec_worker', )


def get_argument_parser(parser=None):
    if not parser:
        parser = argparse.ArgumentParser()

    _add_debug_options(parser)

    parser.add_argument('--reactor',
                        default=None,
                        choices=['select', 'poll', 'epoll', 'kqueue', 'iocp'],
                        help='Explicit Twisted reactor selection (optional).')

    parser.add_argument('--loglevel',
                        default='info',
                        choices=['none', 'error', 'warn', 'info', 'debug', 'trace'],
                        help='Initial log level.')

    parser.add_argument('-c', '--cbdir', type=str, required=True, help="Crossbar.io node directory (required).")

    parser.add_argument('-r',
                        '--realm',
                        type=str,
                        required=True,
                        help='Crossbar.io node (management) realm (required).')

    parser.add_argument('-p',
                        '--personality',
                        required=True,
                        type=str,
                        help='Crossbar.io personality _class_ name, eg "crossbar.personality.Personality" (required).')

    parser.add_argument(
        '-k',
        '--klass',
        required=True,
        type=str,
        help='Crossbar.io worker class, eg "crossbar.worker.container.ContainerController" (required).')

    parser.add_argument('-n', '--node', required=True, type=str, help='Crossbar.io node ID (required).')

    parser.add_argument('-w', '--worker', type=str, required=True, help='Crossbar.io worker ID (required).')

    parser.add_argument('-e',
                        '--extra',
                        type=str,
                        required=False,
                        help='Crossbar.io worker extra configuration from worker.options.extra (optional).')

    parser.add_argument('--title', type=str, default=None, help='Worker process title to set (optional).')

    parser.add_argument('--expose_controller',
                        type=bool,
                        default=False,
                        help='Expose node controller session to all components (this feature requires crossbar).')

    parser.add_argument('--expose_shared',
                        type=bool,
                        default=False,
                        help='Expose a shared object to all components (this feature requires crossbar).')

    parser.add_argument('--shutdown', type=str, default=None, help='Shutdown method')

    parser.add_argument('--restart', type=str, default=None, help='Restart method')

    if _HAS_VMPROF:
        parser.add_argument('--vmprof',
                            action='store_true',
                            help='Profile node controller and native worker using vmprof.')

    return parser


def _run_command_exec_worker(options, reactor=None, personality=None):
    """
    Entry point into (native) worker processes. This wires up stuff such that
    a worker instance is talking WAMP-over-stdio to the node controller.
    """
    import os
    import sys
    import platform
    import signal

    # https://coverage.readthedocs.io/en/coverage-4.4.2/subprocess.html#measuring-sub-processes
    MEASURING_COVERAGE = False
    if 'COVERAGE_PROCESS_START' in os.environ:
        try:
            import coverage
        except ImportError:
            pass
        else:
            # The following will read the environment variable COVERAGE_PROCESS_START,
            # and that should be set to the .coveragerc file:
            #
            #   export COVERAGE_PROCESS_START=${PWD}/.coveragerc
            #
            coverage.process_startup()
            MEASURING_COVERAGE = True

    # we use an Autobahn utility to import the "best" available Twisted reactor
    from autobahn.twisted.choosereactor import install_reactor
    reactor = install_reactor(options.reactor)

    # make sure logging to something else than stdio is setup _first_
    from crossbar._logging import make_JSON_observer, cb_logging_aware
    from txaio import make_logger, start_logging
    from twisted.logger import globalLogPublisher
    from twisted.python.reflect import qual

    log = make_logger()

    # Print a magic phrase that tells the capturing logger that it supports
    # Crossbar's rich logging
    print(cb_logging_aware, file=sys.__stderr__)
    sys.__stderr__.flush()

    flo = make_JSON_observer(sys.__stderr__)
    globalLogPublisher.addObserver(flo)

    term_print('CROSSBAR[{}]:WORKER_STARTING'.format(options.worker))

    # Ignore SIGINT so we get consistent behavior on control-C versus
    # sending SIGINT to the controller process. When the controller is
    # shutting down, it sends TERM to all its children but ctrl-C
    # handling will send a SIGINT to all the processes in the group
    # (so then the controller sends a TERM but the child already or
    # will very shortly get a SIGINT as well). Twisted installs signal
    # handlers, but not for SIGINT if there's already a custom one
    # present.
    def ignore(sig, frame):
        log.debug("Ignoring SIGINT in worker.")

    signal.signal(signal.SIGINT, ignore)

    # actually begin logging
    start_logging(None, options.loglevel)

    # get personality klass, eg "crossbar.personality.Personality"
    l = options.personality.split('.')
    personality_module, personality_klass = '.'.join(l[:-1]), l[-1]

    # now load the personality module and class
    _mod = importlib.import_module(personality_module)
    Personality = getattr(_mod, personality_klass)

    # get worker klass, eg "crossbar.worker.container.ContainerController"
    l = options.klass.split('.')
    worker_module, worker_klass = '.'.join(l[:-1]), l[-1]

    # now load the worker module and class
    _mod = importlib.import_module(worker_module)
    klass = getattr(_mod, worker_klass)

    log.info(
        'Starting {worker_type}-worker "{worker_id}" on node "{node_id}" (personality "{personality}") and local node management realm "{realm}" .. {worker_class}',
        worker_type=hl(klass.WORKER_TYPE),
        worker_id=hlid(options.worker),
        node_id=hlid(options.node),
        realm=hlid(options.realm),
        personality=hl(Personality.NAME),
        worker_class=hltype(klass),
    )
    log.info(
        'Running as PID {pid} on {python}-{reactor}',
        pid=os.getpid(),
        python=platform.python_implementation(),
        reactor=qual(reactor.__class__).split('.')[-1],
    )
    if MEASURING_COVERAGE:
        log.info(hl('Code coverage measurements enabled (coverage={coverage_version}).', color='green', bold=True),
                 coverage_version=coverage.__version__)

    # set process title if requested to
    #
    try:
        import setproctitle
    except ImportError:
        log.debug("Could not set worker process title (setproctitle not installed)")
    else:
        if options.title:
            setproctitle.setproctitle(options.title)
        else:
            setproctitle.setproctitle('crossbar-worker [{}]'.format(options.klass))

    # node directory
    #
    options.cbdir = os.path.abspath(options.cbdir)
    os.chdir(options.cbdir)
    # log.msg("Starting from node directory {}".format(options.cbdir))

    # set process title if requested to
    #
    try:
        import setproctitle
    except ImportError:
        log.debug("Could not set worker process title (setproctitle not installed)")
    else:
        if options.title:
            setproctitle.setproctitle(options.title)
        else:
            setproctitle.setproctitle('crossbar-worker [{}]'.format(options.klass))

    from twisted.internet.error import ConnectionDone
    from autobahn.twisted.websocket import WampWebSocketServerProtocol

    class WorkerServerProtocol(WampWebSocketServerProtocol):
        def connectionLost(self, reason):
            # the behavior here differs slightly whether we're shutting down orderly
            # or shutting down because of "issues"
            if isinstance(reason.value, ConnectionDone):
                was_clean = True
            else:
                was_clean = False

            try:
                # this log message is unlikely to reach the controller (unless
                # only stdin/stdout pipes were lost, but not stderr)
                if was_clean:
                    log.info("Connection to node controller closed cleanly")
                else:
                    log.warn("Connection to node controller lost: {reason}", reason=reason)

                # give the WAMP transport a change to do it's thing
                WampWebSocketServerProtocol.connectionLost(self, reason)
            except:
                # we're in the process of shutting down .. so ignore ..
                pass
            finally:
                # after the connection to the node controller is gone,
                # the worker is "orphane", and should exit

                # determine process exit code
                if was_clean:
                    exit_code = 0
                else:
                    exit_code = 1

                # exit the whole worker process when the reactor has stopped
                reactor.addSystemEventTrigger('after', 'shutdown', os._exit, exit_code)

                # stop the reactor
                try:
                    reactor.stop()
                except ReactorNotRunning:
                    pass

    # if vmprof global profiling is enabled via command line option, this will carry
    # the file where vmprof writes its profile data
    if _HAS_VMPROF:
        _vm_prof = {
            # need to put this into a dict, since FDs are ints, and python closures can't
            # write to this otherwise
            'outfd': None
        }

    # https://twistedmatrix.com/documents/current/api/twisted.internet.interfaces.IReactorCore.html
    # Each "system event" in Twisted, such as 'startup', 'shutdown', and 'persist', has 3 phases:
    # 'before', 'during', and 'after' (in that order, of course). These events will be fired
    # internally by the Reactor.

    def before_reactor_started():
        term_print('CROSSBAR[{}]:REACTOR_STARTING'.format(options.worker))

    def after_reactor_started():
        term_print('CROSSBAR[{}]:REACTOR_STARTED'.format(options.worker))

        if _HAS_VMPROF and options.vmprof:
            outfn = os.path.join(options.cbdir, '.vmprof-worker-{}-{}.dat'.format(options.worker, os.getpid()))
            _vm_prof['outfd'] = os.open(outfn, os.O_RDWR | os.O_CREAT | os.O_TRUNC)
            vmprof.enable(_vm_prof['outfd'], period=0.01)
            term_print('CROSSBAR[{}]:VMPROF_ENABLED:{}'.format(options.worker, outfn))

    def before_reactor_stopped():
        term_print('CROSSBAR[{}]:REACTOR_STOPPING'.format(options.worker))

        if _HAS_VMPROF and options.vmprof and _vm_prof['outfd']:
            vmprof.disable()
            term_print('CROSSBAR[{}]:VMPROF_DISABLED'.format(options.worker))

    def after_reactor_stopped():
        # FIXME: we are indeed reaching this line, however,
        # the log output does not work (it also doesnt work using
        # plain old print). Dunno why.

        # my theory about this issue is: by the time this line
        # is reached, Twisted has already closed the stdout/stderr
        # pipes. hence we do an evil trick: we directly write to
        # the process' controlling terminal
        # https://unix.stackexchange.com/a/91716/52500
        term_print('CROSSBAR[{}]:REACTOR_STOPPED'.format(options.worker))

    reactor.addSystemEventTrigger('before', 'startup', before_reactor_started)
    reactor.addSystemEventTrigger('after', 'startup', after_reactor_started)
    reactor.addSystemEventTrigger('before', 'shutdown', before_reactor_stopped)
    reactor.addSystemEventTrigger('after', 'shutdown', after_reactor_stopped)

    try:
        # define a WAMP application session factory
        #
        from autobahn.wamp.types import ComponentConfig

        def make_session():
            session_config = ComponentConfig(realm=options.realm, extra=options)
            session = klass(config=session_config, reactor=reactor, personality=Personality)
            return session

        # create a WAMP-over-WebSocket transport server factory
        #
        from autobahn.twisted.websocket import WampWebSocketServerFactory
        transport_factory = WampWebSocketServerFactory(make_session, 'ws://localhost')
        transport_factory.protocol = WorkerServerProtocol
        transport_factory.setProtocolOptions(failByDrop=False)

        # create a protocol instance and wire up to stdio
        #
        from twisted.python.runtime import platform as _platform
        from twisted.internet import stdio
        proto = transport_factory.buildProtocol(None)
        if _platform.isWindows():
            stdio.StandardIO(proto)
        else:
            stdio.StandardIO(proto, stdout=3)

        # now start reactor loop
        #
        log.info(hl('Entering event reactor ...', color='green', bold=True))
        reactor.run()

    except Exception as e:
        log.info("Unhandled exception: {e}", e=e)
        if reactor.running:
            reactor.addSystemEventTrigger('after', 'shutdown', os._exit, 1)
            reactor.stop()
        else:
            sys.exit(1)


if __name__ == '__main__':
    import sys
    from crossbar import _util

    _args = sys.argv[1:]
    _util.set_flags_from_args(_args)

    parser = get_argument_parser()
    args = parser.parse_args(_args)

    if args.extra:
        args.extra = cbor2.loads(binascii.a2b_hex(args.extra))

    _run_command_exec_worker(args)

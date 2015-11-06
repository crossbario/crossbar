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

from __future__ import absolute_import, print_function

from twisted.internet.error import ReactorNotRunning

__all__ = ('run',)


def run():
    """
    Entry point into (native) worker processes. This wires up stuff such that
    a worker instance is talking WAMP-over-stdio to the node controller.
    """
    import os
    import sys
    import platform
    import signal

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

    # create the top-level parser
    #
    import argparse
    parser = argparse.ArgumentParser()

    parser.add_argument('--reactor',
                        default=None,
                        choices=['select', 'poll', 'epoll', 'kqueue', 'iocp'],
                        help='Explicit Twisted reactor selection (optional).')

    parser.add_argument('--loglevel',
                        default="info",
                        choices=['none', 'error', 'warn', 'info', 'debug', 'trace'],
                        help='Initial log level.')

    parser.add_argument('-c',
                        '--cbdir',
                        type=str,
                        help="Crossbar.io node directory (required).")

    parser.add_argument('-n',
                        '--node',
                        type=str,
                        help='Crossbar.io node ID (required).')

    parser.add_argument('-w',
                        '--worker',
                        type=str,
                        help='Crossbar.io worker ID (required).')

    parser.add_argument('-r',
                        '--realm',
                        type=str,
                        help='Crossbar.io node (management) realm (required).')

    parser.add_argument('-t',
                        '--type',
                        choices=['router', 'container', 'websocket-testee'],
                        help='Worker type (required).')

    parser.add_argument('--title',
                        type=str,
                        default=None,
                        help='Worker process title to set (optional).')

    options = parser.parse_args()

    # make sure logging to something else than stdio is setup _first_
    #
    from crossbar._logging import make_JSON_observer, cb_logging_aware, _stderr
    from crossbar._logging import make_logger, start_logging, set_global_log_level
    from twisted.logger import globalLogPublisher

    # Set the global log level
    set_global_log_level(options.loglevel)

    log = make_logger()

    # Print a magic phrase that tells the capturing logger that it supports
    # Crossbar's rich logging
    print(cb_logging_aware, file=_stderr)
    _stderr.flush()

    flo = make_JSON_observer(_stderr)
    globalLogPublisher.addObserver(flo)
    start_logging()

    try:
        import setproctitle
    except ImportError:
        log.debug("Could not set worker process title (setproctitle not installed)")
    else:
        # set process title if requested to
        #
        if options.title:
            setproctitle.setproctitle(options.title)
        else:
            WORKER_TYPE_TO_TITLE = {
                'router': 'crossbar-worker [router]',
                'container': 'crossbar-worker [container]',
                'websocket-testee': 'crossbar-worker [websocket-testee]'
            }
            setproctitle.setproctitle(WORKER_TYPE_TO_TITLE[options.type].strip())

    # we use an Autobahn utility to import the "best" available Twisted reactor
    #
    from autobahn.twisted.choosereactor import install_reactor
    reactor = install_reactor(options.reactor)

    from twisted.python.reflect import qual
    log.info("Worker running under {python}-{reactor}",
             python=platform.python_implementation(),
             reactor=qual(reactor.__class__).split('.')[-1])

    options.cbdir = os.path.abspath(options.cbdir)
    os.chdir(options.cbdir)
    # log.msg("Starting from node directory {}".format(options.cbdir))

    from crossbar.worker.router import RouterWorkerSession
    from crossbar.worker.container import ContainerWorkerSession
    from crossbar.worker.testee import WebSocketTesteeWorkerSession

    WORKER_TYPE_TO_CLASS = {
        'router': RouterWorkerSession,
        'container': ContainerWorkerSession,
        'websocket-testee': WebSocketTesteeWorkerSession
    }

    from autobahn.twisted.websocket import WampWebSocketServerProtocol

    class WorkerServerProtocol(WampWebSocketServerProtocol):

        def connectionLost(self, reason):
            try:
                # this log message is unlikely to reach the controller (unless
                # only stdin/stdout pipes were lost, but not stderr)
                log.warn("Connection to node controller lost.")
                WampWebSocketServerProtocol.connectionLost(self, reason)
            except:
                pass
            finally:
                # losing the connection to the node controller is fatal:
                # stop the reactor and exit with error
                log.info("No more controller connection; shutting down.")
                reactor.addSystemEventTrigger('after', 'shutdown', os._exit, 1)
                try:
                    reactor.stop()
                except ReactorNotRunning:
                    pass

    try:
        # create a WAMP application session factory
        #
        from autobahn.twisted.wamp import ApplicationSessionFactory
        from autobahn.wamp.types import ComponentConfig

        session_config = ComponentConfig(realm=options.realm, extra=options)
        session_factory = ApplicationSessionFactory(session_config)
        session_factory.session = WORKER_TYPE_TO_CLASS[options.type]

        # create a WAMP-over-WebSocket transport server factory
        #
        from autobahn.twisted.websocket import WampWebSocketServerFactory
        transport_factory = WampWebSocketServerFactory(session_factory, "ws://localhost", debug=False, debug_wamp=False)
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
        if False:
            log.info("vmprof enabled.")

            import os
            import vmprof

            PROFILE_FILE = 'vmprof_{}.dat'.format(os.getpid())

            outfd = os.open(PROFILE_FILE, os.O_RDWR | os.O_CREAT | os.O_TRUNC)
            vmprof.enable(outfd, period=0.01)

            log.info("Entering event loop...")
            reactor.run()

            vmprof.disable()
        else:
            log.debug("Entering event loop...")
            reactor.run()

    except Exception as e:
        log.info("Unhandled exception: {}".format(e))
        if reactor.running:
            reactor.addSystemEventTrigger('after', 'shutdown', os._exit, 1)
            reactor.stop()
        else:
            sys.exit(1)


if __name__ == '__main__':
    run()

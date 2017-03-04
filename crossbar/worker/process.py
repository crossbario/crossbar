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

from __future__ import absolute_import, print_function

import six

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
                        type=six.text_type,
                        help="Crossbar.io node directory (required).")

    parser.add_argument('-r',
                        '--realm',
                        type=six.text_type,
                        help='Crossbar.io node (management) realm (required).')

    parser.add_argument('-t',
                        '--type',
                        choices=['router', 'container', 'websocket-testee'],
                        help='Worker type (required).')

    parser.add_argument('-w',
                        '--worker',
                        type=six.text_type,
                        help='Crossbar.io worker ID (required).')

    parser.add_argument('--title',
                        type=six.text_type,
                        default=None,
                        help='Worker process title to set (optional).')

    parser.add_argument('--expose_controller',
                        type=bool,
                        default=False,
                        help='Expose node controller session to all components (this feature requires Crossbar.io Fabric extension).')

    parser.add_argument('--expose_shared',
                        type=bool,
                        default=False,
                        help='Expose a shared object to all components (this feature requires Crossbar.io Fabric extension).')

    options = parser.parse_args()

    # make sure logging to something else than stdio is setup _first_
    #
    from crossbar._logging import make_JSON_observer, cb_logging_aware
    from txaio import make_logger, start_logging
    from twisted.logger import globalLogPublisher

    log = make_logger()

    # Print a magic phrase that tells the capturing logger that it supports
    # Crossbar's rich logging
    print(cb_logging_aware, file=sys.__stderr__)
    sys.__stderr__.flush()

    flo = make_JSON_observer(sys.__stderr__)
    globalLogPublisher.addObserver(flo)
    start_logging(None, options.loglevel)

    # we use an Autobahn utility to import the "best" available Twisted reactor
    #
    from autobahn.twisted.choosereactor import install_reactor
    reactor = install_reactor(options.reactor)

    WORKER_TYPE_TO_TITLE = {
        'router': 'Router',
        'container': 'Container',
        'websocket-testee': 'WebSocket Testee'
    }

    from twisted.python.reflect import qual
    log.info('{worker_title} worker "{worker_id}" process {pid} starting on {python}-{reactor} ..',
             worker_title=WORKER_TYPE_TO_TITLE[options.type],
             worker_id=options.worker,
             pid=os.getpid(),
             python=platform.python_implementation(),
             reactor=qual(reactor.__class__).split('.')[-1])

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
            WORKER_TYPE_TO_PROCESS_TITLE = {
                'router': 'crossbar-worker [router]',
                'container': 'crossbar-worker [container]',
                'websocket-testee': 'crossbar-worker [websocket-testee]'
            }
            setproctitle.setproctitle(WORKER_TYPE_TO_PROCESS_TITLE[options.type].strip())

    # node directory
    #
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
        transport_factory = WampWebSocketServerFactory(session_factory, u'ws://localhost')
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
        log.info("Unhandled exception: {e}", e=e)
        if reactor.running:
            reactor.addSystemEventTrigger('after', 'shutdown', os._exit, 1)
            reactor.stop()
        else:
            sys.exit(1)


if __name__ == '__main__':
    run()

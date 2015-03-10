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

__all__ = ('run',)


def run():
    """
    Entry point into (native) worker processes. This wires up stuff such that
    a worker instance is talking WAMP-over-stdio to the node controller.
    """
    import os
    import sys
    import platform

    # create the top-level parser
    #
    import argparse
    parser = argparse.ArgumentParser()

    parser.add_argument('-d',
                        '--debug',
                        action='store_true',
                        help='Debug on (optional).')

    parser.add_argument('--reactor',
                        default=None,
                        choices=['select', 'poll', 'epoll', 'kqueue', 'iocp'],
                        help='Explicit Twisted reactor selection (optional).')

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
                        choices=['router', 'container'],
                        help='Worker type (required).')

    parser.add_argument('--title',
                        type=str,
                        default=None,
                        help='Worker process title to set (optional).')

    options = parser.parse_args()

    # make sure logging to something else than stdio is setup _first_
    #
    from twisted.python import log
    from crossbar.twisted.processutil import BareFormatFileLogObserver
    flo = BareFormatFileLogObserver(sys.stderr)
    log.startLoggingWithObserver(flo.emit)

    try:
        import setproctitle
    except ImportError:
        log.msg("Warning: could not set worker process title (setproctitle not installed)")
    else:
        # set process title if requested to
        #
        if options.title:
            setproctitle.setproctitle(options.title)
        else:
            WORKER_TYPE_TO_TITLE = {
                'router': 'crossbar-worker [router]',
                'container': 'crossbar-worker [container]'
            }
            setproctitle.setproctitle(WORKER_TYPE_TO_TITLE[options.type].strip())

    # we use an Autobahn utility to import the "best" available Twisted reactor
    #
    from autobahn.twisted.choosereactor import install_reactor
    reactor = install_reactor(options.reactor)

    from twisted.python.reflect import qual
    log.msg("Running under {} using {} reactor".format(platform.python_implementation(), qual(reactor.__class__).split('.')[-1]))

    options.cbdir = os.path.abspath(options.cbdir)
    os.chdir(options.cbdir)
    # log.msg("Starting from node directory {}".format(options.cbdir))

    from crossbar.worker.router import RouterWorkerSession
    from crossbar.worker.container import ContainerWorkerSession

    WORKER_TYPE_TO_CLASS = {
        'router': RouterWorkerSession,
        'container': ContainerWorkerSession
    }

    from autobahn.twisted.websocket import WampWebSocketServerProtocol

    class WorkerServerProtocol(WampWebSocketServerProtocol):

        def connectionLost(self, reason):
            try:
                # this log message is unlikely to reach the controller (unless
                # only stdin/stdout pipes were lost, but not stderr)
                log.msg("Connection to node controller lost.")
                WampWebSocketServerProtocol.connectionLost(self, reason)
            except:
                pass
            finally:
                # loosing the connection to the node controller is fatal:
                # stop the reactor and exit with error
                if reactor.running:
                    reactor.addSystemEventTrigger('after', 'shutdown', os._exit, 1)
                    reactor.stop()
                else:
                    sys.exit(1)

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
        from twisted.internet import stdio
        proto = transport_factory.buildProtocol(None)
        stdio.StandardIO(proto)

        # now start reactor loop
        #
        log.msg("Entering event loop ..")
        reactor.run()

    except Exception as e:
        log.msg("Unhandled exception: {}".format(e))
        if reactor.running:
            reactor.addSystemEventTrigger('after', 'shutdown', os._exit, 1)
            reactor.stop()
        else:
            sys.exit(1)


if __name__ == '__main__':
    run()

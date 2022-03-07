##############################################################################
#
#                        Crossbar.io
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

import json
import time
import os
from datetime import datetime
from selectors import DefaultSelector, EVENT_READ
from typing import List

import txaio

from twisted.internet.defer import inlineCallbacks
from twisted.internet import threads
from twisted.python.threadpool import ThreadPool

try:
    import docker
    HAS_DOCKER = True
except:
    HAS_DOCKER = False

if HAS_DOCKER:

    class Channel:
        log = txaio.make_logger()

        def __init__(self, selector, socket, id, tty_id, shell):
            self._selector = selector
            self._socket = socket
            self._id = id
            self._tty_id = tty_id
            self._shell = shell
            self.register()
            self.log.debug('Channel create, id={id}, tty_id={tty_id}', id=id, tty_id=tty_id)

        def set_tty(self, tty_id):
            self._tty_id = tty_id

        def register(self):
            self._key = self._selector.register(self._socket, events=EVENT_READ, data={'id': self._id})
            self.keepalive()

        def unregister(self):
            if self._key:
                self._selector.unregister(self._key.fileobj)
                self._key.fileobj.close()
                self._key = None

        def write(self, data):
            try:
                os.write(self._socket.fileno(), data.encode('utf-8'))
                self.keepalive()
                return
            except BrokenPipeError:
                self.log.debug('Someone stopped or reset the container [PIPE]!')
            except ValueError:
                self.log.debug('Someone stopped or reset the container [VALUE]!')
            self._shell = None

        def keepalive(self):
            self._lastseen = datetime.now()

        def expired(self, when):
            return (when - self._lastseen).seconds > 20

        def close(self):
            if self._shell:
                #
                #   Ok, hack alert !! Currently Docker exec doesn't support ANY
                #   mechanism for killing off exec'd commands .. so we're going to
                #   send a Control+C -> exit and hope for the best. If the user gets
                #   into trouble, they just have to restart the container.
                #
                self.write('\x03\n')
                self.write('exit\n')

            self.unregister()
            return self._key

    class Channels:
        log = txaio.make_logger()

        def __init__(self):
            self._channels = {}
            self._used_tty_ids = {}
            self._selector = DefaultSelector()
            self._last_channels = 0
            self._last_expired = 0
            self._next_tty_id = 0

        def get_next_id(self, id):
            if id and id in self._channels:
                return self.get_tty(id)
            tty_id = self._next_tty_id
            self._next_tty_id += 1
            return tty_id

        def get_tty(self, id):
            return self._channels[id]._tty_id if id in self._channels else -1

        def create(self, id, socket, tty_id, shell=False):
            self._used_tty_ids[tty_id] = True
            self._channels[id] = Channel(self._selector, socket, id, tty_id, shell)

        def exists(self, id):
            return id in self._channels

        def tty_exists(self, id):
            return id in self._used_tty_ids

        def set_tty(self, id, tty_id):
            self._channels[id].set_tty(tty_id)

        def silence(self, id):
            if id in self._channels:
                self._channels[id].unregister()

        def close(self, id):

            if id in self._channels:
                channel = self._channels[id]
                channel.close()
                if channel._tty_id in self._used_tty_ids:
                    del self._used_tty_ids[channel._tty_id]
                if id in self._channels:
                    del self._channels[id]
            else:
                self.log.error('attempt to close phantom channel')

        def write(self, id, data):
            self._channels[id].write(data)

        def select(self, timeout):
            return self._selector.select(timeout=timeout)

        def keepalive(self, id):
            self._channels[id].keepalive()

        def expire(self):
            channels = len(self._channels)
            expired = 0
            now = datetime.now()
            for id in dict(self._channels):
                if self._channels[id].expired(now):
                    expired += 1
                    self.close(id)
            if (channels != self._last_channels) or (expired != self._last_expired):
                self.log.info('Docker console expire - updated :: channels={}, expired={}'.format(channels, expired))
                self._last_channels = channels
                self._last_expired = expired

    class DockerClient:
        """
        Asynchronous Docker client (living on a background thread pool).
        """
        _docker = docker
        log = txaio.make_logger()

        CONSOLE_HISTORY = 60
        WAIT_TIMEOUT = 1
        EXCLUDE_DIRS_ANY = ['.cache']  # type: List[str]

        def __init__(self, reactor, controller):
            """
            Set up our async Docker interface.
            """
            self._reactor = reactor
            self._controller = controller
            self._finished = True
            self._channels = None
            self._threadpool = None
            self._events = None

        def console(self, section, status):
            self.log.info(f'docker - {section} - {status}')

        def startup(self):
            """
            Startup Docker client.
            """
            if not self._finished:
                self.log.warn('Docker client already running!')
                return

            self.console('module', 'starting')

            self._finished = False
            self._channels = Channels()

            # dedicated threadpool for docker work
            self._threadpool = ThreadPool(minthreads=4, maxthreads=100, name='docker')
            self._threadpool.start()

            # our 'events' pub/sub docker events emulator
            threads.deferToThreadPool(self._reactor, self._threadpool, self.events)

            # our 'logs' pub/sub docker console output
            threads.deferToThreadPool(self._reactor, self._threadpool, self.logs)

            # our 'keepalive' monitor
            threads.deferToThreadPool(self._reactor, self._threadpool, self.keepalive)

            self.console('module', 'started')

        def shutdown(self):
            """
            Shutdown Docker client.
            """
            if self._finished:
                self.console('module', 'already stopped')
                return

            self.console('module', 'stopping')
            self._finished = True
            self.console('keepalive', 'stopping')

            if self._events:
                self.console('events', 'stopping')
                self._events.close()

            if self._threadpool:
                self.console('threads', 'stopping')
                self._threadpool.stop()

            self.console('module', 'stopped')

        def keepalive(self):
            """
            Monitor all our active channels and expire any once keepalive's stop
            """
            self.console('keepalive', 'started')
            while not self._finished:
                self._channels.expire()
                for x in range(10):
                    if self._finished:
                        break
                    time.sleep(self.WAIT_TIMEOUT)
            self.console('keepalive', 'stopped')

        def logs(self):
            """
            Forward console logs from containers back into Crossbar
            """
            self.console('logs', 'started')
            while not self._finished:
                worklist = self._channels.select(self.WAIT_TIMEOUT)
                for (key, events) in worklist:
                    id = key.data['id']
                    line = os.read(key.fd, 8192)
                    if not line:
                        self._channels.silence(id)
                        continue
                    tty_id = self._channels.get_tty(id)
                    if tty_id >= 0:
                        self._reactor.callFromThread(
                            self._controller.publish,
                            f'crossbar.worker.{self._controller._uri_prefix}.docker.tty_{tty_id}',
                            {'line': line.decode('utf-8')})
                        time.sleep(0.1)
            self.console('logs', 'stopped')

        def events(self):
            """
            Called from node controller in a background thread to watch (blocking!)
            for Docker events and publish those as WAMP events on the main thread.
            """
            self.console('events', 'started')

            # DOCKER records logs with 1 second granularity, so it will potentiall have MANY lines with
            # the same timestamp. Asking for timestamp + delta is unsafe as it can only ask for the
            # next second, which will potentially lose all records logged which were effectively logged
            # against the previous second, but happened "after" that last call to "events". Docker "should"
            # log with time.time() or similar, but sadly ...

            # IF there is a problem with "events" in docker, it needs to be identified and fixed.
            # - this routine has been live on "demo1" for 9 months with no problems reported.

            while not self._finished:
                #
                #   "events" will close if docker is restarted, we aim to survive that event ...
                #
                try:
                    self._events = self._docker.from_env().events()
                    for event in self._events:
                        if self._finished:
                            break
                        event = json.loads(event, encoding='utf8')
                        ident = event.get('id')
                        if not ident:
                            continue
                        etype = event.get('Type')
                        eactn = event.get('Action')
                        topic = u'crossbar.worker.{}.docker.on_{}_{}'.format(self._controller._uri_prefix, etype,
                                                                             eactn)
                        if etype == 'container' and eactn == 'restart':
                            self.watch(ident, self._channels.get_tty(ident))
                        try:
                            payload = {'id': ident}
                            self.log.debug('publish : {topic} => {packet}', topic=topic, packet=payload)
                            if self._controller:
                                self._reactor.callFromThread(self._controller.publish, topic, payload)

                        except Exception as e:
                            self.log.error('Error: not able to handle event type :: {}'.format(topic))
                            print(e)

                except Exception as e:
                    self.log.error(f'error in "events" - {str(e)}')

            self.console('events', 'stopped')

        @inlineCallbacks
        def create(self, image, kwargs):
            """
            Create a new container and get it ready to run
            """
            def shim(image, **kwargs):
                client = self._docker.from_env()
                try:
                    container = client.containers.create(image, **kwargs)
                    return {'id': container.id}
                except docker.errors.ImageNotFound:
                    self.log.info('No Image ({image}) attempting to pull', image=image)
                    try:
                        client.images.pull(image)
                        container = client.containers.create(image, **kwargs)
                        return {'id': container.id}
                    except docker.errors.APIError:
                        raise Exception('Docker failed to pull ({image})', image=image)

            self.log.debug('docker create :: {image} -> {kw}', image=image, kw=kwargs)
            kwargs['detach'] = True
            kwargs['tty'] = True
            kwargs['stdin_open'] = True
            return (yield threads.deferToThreadPool(self._reactor, self._threadpool, shim, image, **kwargs))

        @inlineCallbacks
        def get_info(self):
            """
            Recover information about our docker installation.

            Shell command: ``crossbar shell --realm mrealm1 show docker node1``
            """
            def shim():
                return self._docker.from_env().info()

            self.log.debug('docker get_info')
            return (yield threads.deferToThreadPool(self._reactor, self._threadpool, shim))

        @inlineCallbacks
        def get_containers(self):
            """
            Recover a list of container ID's
            """
            def shim():
                return [c.id for c in self._docker.from_env().containers.list(all=True)]

            self.log.debug('docker get_containers')
            return (yield threads.deferToThreadPool(self._reactor, self._threadpool, shim))

        @inlineCallbacks
        def get_container(self, id):
            """
            Recover information about one specific container (by id)
            """
            def shim(id):
                try:
                    return self._docker.from_env().containers.get(id).attrs
                except Exception as e:
                    return {'error': 'unable to get container details', 'traceback': str(e)}

            self.log.debug('docker get_container -> {id}', id=id)
            return (yield threads.deferToThreadPool(self._reactor, self._threadpool, shim, id))

        @inlineCallbacks
        def get_images(self):
            """
            Recover a list of image ID's

            Shell command: ``crossbar shell --realm mrealm1 list docker-images node1``
            """
            def shim():
                return [c.id for c in self._docker.from_env().images.list()]

            self.log.debug('docker get_images')
            return (yield threads.deferToThreadPool(self._reactor, self._threadpool, shim))

        @inlineCallbacks
        def delete_image(self, id):
            """
            Purge old images
            """
            def shim():
                try:
                    return self._docker.from_env().images.remove(id)
                except Exception as e:
                    print(e)
                    print(dir(e))
                    return {'error': 'unable to remove image', 'traceback': str(e)}

            self.log.debug('docker delete_image')
            return (yield threads.deferToThreadPool(self._reactor, self._threadpool, shim))

        @inlineCallbacks
        def get_image(self, id):
            """
            Recover information about one specific image (by id)

            Shell command: ``crossbar shell --realm mrealm1 show docker-image node1 4bbb66``
            """
            def shim(id):
                try:
                    return self._docker.from_env().images.get(id).attrs
                except Exception as e:
                    return {'error': 'unable to get image', 'traceback': str(e)}

            self.log.debug('docker get_image -> {id}', id=id)
            return (yield threads.deferToThreadPool(self._reactor, self._threadpool, shim, id))

        @inlineCallbacks
        def df(self):
            """
            Get information relating to docker's usage of available storage
            """
            def shim():
                return self._docker.from_env().df()

            self.log.debug('docker df')
            return (yield threads.deferToThreadPool(self._reactor, self._threadpool, shim))

        @inlineCallbacks
        def ping(self):
            """
            Bounce a message off docket to see if it's running
            """
            def shim():
                try:
                    return self._docker.from_env().ping()
                except Exception:
                    return False

            self.log.debug('docker ping')
            return (yield threads.deferToThreadPool(self._reactor, self._threadpool, shim))

        @inlineCallbacks
        def version(self):
            """
            Get the version information of our docker instance
            """
            def shim():
                return self._docker.from_env().version()

            self.log.debug('docker version')
            return (yield threads.deferToThreadPool(self._reactor, self._threadpool, shim))

        @inlineCallbacks
        def container(self, id, cmd):
            """
            Operate on a specific container (by id)
            """
            def shim(id, cmd):
                container = self._docker.from_env().containers.get(id)
                if hasattr(container, cmd):
                    return getattr(container, cmd)()
                raise Exception('no such command :: {}'.format(cmd))

            self.log.debug('docker container -> {id} + {cmd}', id=id, cmd=cmd)
            return (yield threads.deferToThreadPool(self._reactor, self._threadpool, shim, id, cmd))

        @inlineCallbacks
        def start(self, id):
            """
            Specific container routine that needs a non-default timeout
            """
            def shim(id):
                container = self._docker.from_env().containers.get(id)
                status = container.start()
                tty_id = self._channels.get_tty(id)
                if tty_id >= 0:
                    client = docker.APIClient()
                    params = {'stdin': 1, 'stdout': 1, 'stderr': 1, 'stream': 1, 'timestamps': 0, 'logs': 0}
                    socket = client.attach_socket(id, params)
                    self._channels.close(id)
                    self._channels.create(id, socket, tty_id)
                    status = {'status': 'OK', 'id': id, 'tty_id': tty_id}
                return status

            self.log.debug('docker container start -> {id}', id=id)
            return (yield threads.deferToThreadPool(self._reactor, self._threadpool, shim, id))

        @inlineCallbacks
        def restart(self, id):
            """
            Specific container routine that needs a non-default timeout
            """
            def shim(id):
                container = self._docker.from_env().containers.get(id)
                try:
                    container.restart(timeout=1)
                except Exception as e:
                    self.log.error('Exception while trying to restart container')
                    self.log.error(str(e))
                tty_id = self._channels.get_tty(id)
                client = self._docker.APIClient()
                params = {'stdin': 1, 'stdout': 1, 'stderr': 1, 'stream': 1, 'timestamps': 0, 'logs': 0}
                socket = client.attach_socket(id, params)
                self._channels.close(id)
                self._channels.create(id, socket, tty_id)
                return {'status': 'OK', 'id': id, 'tty_id': tty_id}

            self.log.info('docker container restart -> {id}', id=id)
            return (yield threads.deferToThreadPool(self._reactor, self._threadpool, shim, id))

        @inlineCallbacks
        def image(self, id, cmd):
            """
            Operate on a specific image (by id)
            """
            def shim(id, cmd):
                image = self._docker.from_env().images.get(id)
                if hasattr(image, cmd):
                    return getattr(image, cmd)()
                raise Exception('no such command :: {}'.format(cmd))

            self.log.debug('docker image -> {id} + {cmd}', id=id, cmd=cmd)
            return (yield threads.deferToThreadPool(self._reactor, self._threadpool, shim, id, cmd))

        @inlineCallbacks
        def prune(self, filter):
            """
            Prune docker images
            """
            def shim(filter):
                return self._docker.from_env().images.prune(filter)

            self.log.debug('docker prune -> {filter}', filter=filter)
            return (yield threads.deferToThreadPool(self._reactor, self._threadpool, shim, filter))

        @inlineCallbacks
        def backlog(self, id):
            """
            Request historical console logs / buffer
            """
            def shim(id):
                if not self._channels.exists(id):
                    return {'status': 'NOTFOUND'}

                client = self._docker.from_env()
                try:
                    container = client.containers.get(id)
                # FIXME: NotFound
                except:
                    return {'status': 'OK', 'packet': ''}

                lines = container.logs(stdout=1, stderr=1, stream=0, timestamps=1, tail=60)
                return {'status': 'OK', 'packet': lines[-16384:].decode('utf-8')}

            self.log.debug('docker backlog -> {id}', id=id)
            return (yield threads.deferToThreadPool(self._reactor, self._threadpool, shim, id))

        def request_tty(self, id):
            return {'status': 'OK', 'tty_id': self._channels.get_next_id(id)}

        @inlineCallbacks
        def watch(self, id, tty_id):
            """
            Watch the console of the specified container
            """
            def shim(id):
                try:
                    client = self._docker.from_env()
                    container = client.containers.get(id)
                except docker.errors.NotFound:
                    return {'status': 'NOTFOUND', 'packet': ''}

                if self._channels.exists(id) or self._channels.tty_exists(tty_id):
                    self._channels.set_tty(id, tty_id)
                    buffer = container.logs(stdout=1, stderr=1, stream=0, timestamps=0, tail=self.CONSOLE_HISTORY)
                else:
                    client = self._docker.APIClient()
                    params = {'stdin': 1, 'stdout': 1, 'stderr': 1, 'stream': 1, 'timestamps': 0, 'logs': 0}
                    socket = client.attach_socket(id, params)
                    buffer = container.logs(stdout=1, stderr=1, stream=0, timestamps=0, tail=self.CONSOLE_HISTORY)
                    self._channels.create(id, socket, tty_id)

                buffer = buffer.decode('utf-8')
                # attempt to clean broken ESC sequence
                if len(buffer) > 16384:
                    buffer = buffer[-16384:]
                    for i in range(12):
                        if ord(buffer[i]) == 27:
                            buffer = buffer[i:]
                            break
                return {'status': 'OK', 'id': id, 'tty_id': tty_id, 'buffer': buffer}

            self.log.debug('docker watch -> {id}', id=id)
            return (yield threads.deferToThreadPool(self._reactor, self._threadpool, shim, id))

        def keystroke(self, id, data):
            """
            Enter a new keystroke into a container console
            """
            if not self._channels.exists(id):
                return {'status': 'NOTFOUND'}

            if isinstance(data, list):
                for item in data:
                    if item['action'] == 'keepalive':
                        self._channels.keepalive(id)
                    elif item['action'] == 'size_console':
                        client = self._docker.from_env()
                        container = client.containers.get(id)
                        container.resize(item['rows'], item['cols'])
                    elif item['action'] == 'size_shell':
                        client = self._docker.APIClient()
                        client.exec_resize(id, item['rows'], item['cols'])
                    elif item['action'] == 'close':
                        self._channels.close(id)
                    else:
                        self.log.error('unknown keystroke command: {cmd}', cmd=item)
                return

            self._channels.write(id, data)
            return {'status': 'OK'}

        @inlineCallbacks
        def shell(self, container, tty_id, kwargs={}):
            """
            Execute a shell in a running container
            """
            client = self._docker.APIClient()

            def shim(image, **kwargs):
                kwargs['tty'] = True
                kwargs['stdin'] = True
                cmd = '/bin/bash'
                return client.exec_create(container, cmd, **kwargs)

            self.log.debug('docker shell :: {container} -> {kw}', container=container, kw=kwargs)
            execId = (yield threads.deferToThreadPool(self._reactor, self._threadpool, shim, container, **kwargs))
            id = execId.get('Id')

            def shim2():
                socket = client.exec_start(id, detach=False, tty=True, socket=True)
                self._channels.create(id, socket, tty_id, True)
                return {'status': 'OK', 'id': id}

            return (yield threads.deferToThreadPool(self._reactor, self._threadpool, shim2))

        def fs_root(self, id, path):
            while path and path[0] == '/':
                path = path[1:]
            container = self._docker.from_env().containers.get(id)
            for point in container.attrs.get('Mounts', []):
                dst = point.get('Destination', '')
                src = point.get('Source', '')
                if f'/{path}'.startswith(f'{dst}/'):
                    path = "/".join(path.split('/')[1:])
                    return os.path.join(src, path)
            raise Exception(f'invalid path "{path}"')

        def fs_open(self, id, path):
            """
            Read the filesystem structure for the given container
            """
            while path and path[0] == '/':
                path = path[1:]
            files = []
            dirs = []
            container = self._docker.from_env().containers.get(id)
            if not path:
                for point in container.attrs.get('Mounts', []):
                    dirs.append(point.get('Destination'))
            else:
                if path[:-1] != '/':
                    path += '/'
                for point in container.attrs.get('Mounts', []):
                    dst = point.get('Destination', '')
                    src = point.get('Source', '')
                    print(f'path={path} dst={dst}')
                    if not f'/{path}'.startswith(f'{dst}/'):
                        continue
                    path = "/".join(path.split('/')[1:])
                    root = os.path.join(src, path)
                    print(f'Root={root}')
                    with os.scandir(root) as iterator:
                        for entry in iterator:
                            if entry.is_file():
                                files.append(entry.name)
                            elif entry.is_dir():
                                if entry.name not in self.EXCLUDE_DIRS_ANY:
                                    dirs.append(entry.name)
            dirs.sort()
            files.sort()
            return {'dirs': dirs, 'files': files}

        def fs_get(self, id, path):
            """
            Recover a file from a container filesystem
            """
            with open(self.fs_root(id, path)) as io:
                return {'data': io.read()}

        def fs_put(self, id, path, data):
            """
            Store a file into a Docker container
            """
            with open(self.fs_root(id, path), 'w') as io:
                io.write(data)

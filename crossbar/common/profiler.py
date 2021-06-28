#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import os
import tempfile

from twisted.internet.defer import Deferred
from twisted.internet.threads import deferToThread

from autobahn.util import utcnow, newid

from txaio import make_logger

try:
    import vmprof
    _HAS_VMPROF = True
except ImportError:
    _HAS_VMPROF = False

PROFILERS = {}

__all__ = ('PROFILERS')


class Profiler(object):

    log = make_logger()

    STATE_RUNNING = 1
    STATE_STOPPED = 2

    def __init__(self, id, config=None):
        """

        :param id: The ID under which this profiler will be identified.
        :type id: unicode

        """
        self._id = id
        self._state = Profiler.STATE_STOPPED
        self._config = config or {}

        # None or UTC timestamp when profile was started
        self._started = None

        # None or a Deferred that fires when the profile has finished
        self._finished = None

        # None or the ID of the profile being currently created
        self._profile_id = None

        # None or absolute path to profile file being created
        self._profile_filename = None

        # the directory under which (temporary) profile file generated
        # by VMprof will be stored
        self._profile_dir = tempfile.gettempdir()

    def marshal(self):
        return {
            'id': self._id,
            'config': self._config,
            'state': 'running' if self._state == Profiler.STATE_RUNNING else 'stopped',
            'started': self._started,
        }


if _HAS_VMPROF:

    class VMprof(Profiler):
        def __init__(self, id, config=None):
            Profiler.__init__(self, id, config)

        def _walk_tree(self, parent, node, level, callback):
            callback(parent, node, level)
            level += 1
            for c in node.children.values():
                self._walk_tree(node, c, level, callback)

        def start(self, runtime=10):
            """
            Start profiling with VMprof for the given duration.
            """
            if self._state != Profiler.STATE_STOPPED:
                raise Exception("profile currently not stopped - cannot start")

            self._profile_filename = os.path.join(self._profile_dir,
                                                  "cb_vmprof_{}_{}.dat".format(os.getpid(), utcnow()))
            profile_fd = os.open(self._profile_filename, os.O_RDWR | os.O_CREAT | os.O_TRUNC)

            vmprof.enable(profile_fd, period=0.01)

            self._state = Profiler.STATE_RUNNING
            self._finished = Deferred()
            self._profile_id = newid()

            # this will run on a background thread
            def convert_profile(profile_filename):
                self.log.info("Converting profile file {fname}", fname=profile_filename)

                try:
                    stats = vmprof.read_profile(profile_filename, virtual_only=True, include_extra_info=True)
                except Exception:
                    self.log.error(
                        "Fatal: could not read vmprof profile file '{fname}': {log_failure.value}",
                        fname=profile_filename,
                    )
                    raise

                tree = stats.get_tree()
                total = float(tree.count)

                res = []

                def process_node(parent, node, level):
                    parent_name = parent.name if parent else None

                    perc = round(100. * float(node.count) / total, 1)
                    if parent and parent.count:
                        perc_of_parent = round(100. * float(node.count) / float(parent.count), 1)
                    else:
                        perc_of_parent = 100.

                    parts = node.name.count(':')

                    if parts == 3:
                        block_type, funname, funline, filename = node.name.split(':')
                        res.append({
                            'type': 'py',
                            'level': level,
                            'parent': parent_name,
                            'fun': funname,
                            'filename': filename,
                            'dirname': os.path.dirname(filename),
                            'basename': os.path.basename(filename),
                            'line': funline,
                            'perc': perc,
                            'perc_of_parent': perc_of_parent,
                            'count': node.count,
                            'parent_count': parent.count if parent else None,
                        })
                    elif parts == 1:
                        block_type, funname = node.name.split(':')
                        res.append({
                            'type': 'jit',
                            'level': level,
                            'parent': parent_name,
                            'fun': funname,
                            'perc': perc,
                            'perc_of_parent': perc_of_parent,
                            'count': node.count,
                            'parent_count': parent.count if parent else None,
                        })
                    else:
                        raise Exception("fail!")

                self._walk_tree(None, tree, 0, process_node)

                return res

            def finish_profile():
                vmprof.disable()
                self.log.info("Profile created under {filename}", filename=self._profile_filename)

                # now defer to thread conversion
                d = deferToThread(convert_profile, self._profile_filename)

                def on_profile_converted(res):
                    self.log.info("Profile data with {count} log entries generated", count=len(res))
                    self._finished.callback(res)

                def on_profile_conversaion_failed(err):
                    self.log.failure("profile conversion failed", failure=err)
                    self._finished.errback(err)

                d.addCallbacks(on_profile_converted, on_profile_conversaion_failed)

                def cleanup(res):
                    # reset state
                    self._state = Profiler.STATE_STOPPED
                    self._profile_filename = None
                    self._started = None
                    self._finished = None
                    self._profile_id = None

                d.addBoth(cleanup)

            self.log.info("Starting profiling using {profiler} for {runtime} seconds.",
                          profiler=self._id,
                          runtime=runtime)

            from twisted.internet import reactor
            reactor.callLater(runtime, finish_profile)

            return self._profile_id, self._finished

    PROFILERS['vmprof'] = VMprof('vmprof', config={'period': 0.01})

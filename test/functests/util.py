###############################################################################
#
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

# utility classes and methods, used by launcher.py and probe.py among
# others.

import sys
from six import StringIO
from twisted.internet.protocol import ProcessProtocol
from twisted.internet.error import ProcessTerminated, ProcessExitedAlready, ProcessDone
from twisted.internet.defer import Deferred

# @implementer(IProcessProtocol)
class CtsSubprocessProtocol(ProcessProtocol):
    """
    A helper to talk to a subprocess we've launched. Used for
    launching the probes, as well as crossbar instances (see
    spawn_testee and spawn_probe).

    XXX FIXME should unify with functests.helpers.CrossbarProcessProtocol if possible and delete one.
    """

    def __init__(self, all_done, launched, stdout=None, stderr=None):
        # XXX why save these? ...or add API to get them post-hoc
        self._stderr = stderr if stderr else StringIO()
        self._stdout = stdout if stdout else StringIO()

        self._all_done = all_done
        self._launched = launched

    def connectionMade(self):
        """ProcessProtocol override"""
        self._launched.callback(self)

    def outReceived(self, data):
        """ProcessProtocol override"""
        self._stdout.write(data)

    def errReceived(self, data):
        """ProcessProtocol override"""
        self._stderr.write(data)

    def processExited(self, reason):
        """IProcessProtocol API"""
        pass

    def processEnded(self, reason):
        """IProcessProtocol API"""
        # reason.value should always be a ProcessTerminated instance
        fail = reason.value
        # print('end', fail, self._all_done.called, self._launched.called)

        # figure out if we have any callbacks left to resolve
        to_call = []
        if not self._launched.called:
            to_call.append(self._launched)
        if not self._all_done.called:
            to_call.append(self._all_done)

        # ...if we do, figure out errback/callback
        # XXX if arg to callback is a Failure, it errback()s I believe
        # -- or else it might make sense to .callback() with the `reason`
        if to_call:
            if isinstance(fail, (ProcessDone, ProcessTerminated)):
                if fail.exitCode != 0:
                    for cb in to_call:
                        cb.errback(fail)
                else:
                    for cb in to_call:
                        cb.callback(self)
            else:
                for cb in to_call:
                    cb.errback(fail)


class SingleObserver(object):
    """
    A helper for ".when_*()" sort of functions.
    """
    _NotFired = object()

    def __init__(self):
        self._observers = []
        self._fired = self._NotFired

    def when_fired(self):
        d = Deferred()
        if self._fired is not self._NotFired:
            d.callback(self._fired)
        else:
            self._observers.append(d)
        return d

    def fire(self, value):
        if self._observers is None:
            return  # raise RuntimeError("already fired") ?
        self._fired = value
        for d in self._observers:
            d.callback(self._fired)
        self._observers = None
        return value  # so we're transparent if used as a callback

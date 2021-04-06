"""
Helpers for test_cb_shutdown.py
"""

from twisted.internet import reactor, task


def good_join(session, details):
    print("good join: {}".format(details))

    def foo():
        return "foo"

    session.register(foo, u"foo")
    return task.deferLater(reactor, 5, lambda: None)


def failed_join(session, details):
    print("failed join: {}".format(details))

    # we wait more than 2 seconds here to avoid the "component exited
    # really quickly, shut down the node" code in
    # crossbar/node/node.py

    def fail():
        raise RuntimeError("the bad stuff")

    return task.deferLater(reactor, 5, fail)


def join_then_close(session, details):
    print("join then fail: {}".format(details))

    def fail():
        session.disconnect()

    return task.deferLater(reactor, 5, fail)

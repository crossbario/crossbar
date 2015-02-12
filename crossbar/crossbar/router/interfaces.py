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

import abc
import six


@six.add_metaclass(abc.ABCMeta)
class IRouterBase(object):

    @abc.abstractproperty
    def factory(self):
        """
        The router factory this router was created from.
        """

    @abc.abstractproperty
    def realm(self):
        """
        The WAMP realm this router handles.
        """

    @abc.abstractmethod
    def attach(self, session):
        """
        Attach a WAMP application session to this router.

        :param session: Application session to add.
        :type session: An instance that implements :class:`autobahn.wamp.interfaces.ISession`
        """

    @abc.abstractmethod
    def detach(self, session):
        """
        Detach a WAMP application session from this router.

        :param session: Application session to remove.
        :type session: An instance that implements :class:`autobahn.wamp.interfaces.ISession`
        """


class IRouter(IRouterBase):

    """
    WAMP router interface. Routers are responsible for event and call routing.
    """
    ACTION_CALL = 1
    ACTION_REGISTER = 2
    ACTION_PUBLISH = 3
    ACTION_SUBSCRIBE = 4

    ACTION_TO_STRING = {
        ACTION_CALL: 'call',
        ACTION_REGISTER: 'register',
        ACTION_PUBLISH: 'publish',
        ACTION_SUBSCRIBE: 'subscribe'
    }

    @abc.abstractmethod
    def process(self, session, message):
        """
        Process a WAMP message received on the given session.

        :param session: Application session on which the message was received.
        :type session: A provider of :class:`autobahn.wamp.interfaces.ISession`.
        :param message: The WAMP message to be processed.
        :type message: A provider of :class:`autobahn.wamp.interfaces.IMessage`.
        """

    @abc.abstractmethod
    def authorize(self, session, uri, action):
        """
        Authorization hook: check if the given ``session`` is authorized to perform
        the given ``action`` on the given ``uri``.

        :param session: Application session on which the action is to be authorized.
        :type session: A provider of :class:`autobahn.wamp.interfaces.ISession`.
        :param uri: The URI on which the session wants to perform the action.
        :type uri: str
        :param action: The action the session wants to perform. One of
           ``IRouter.ACTION_CALL``, ``IRouter.ACTION_REGISTER``,
           ``IRouter.ACTION_PUBLISH`` or ``IRouter.ACTION_SUBSCRIBE``.
        :type action: int
        """

    @abc.abstractmethod
    def validate(self, payload_type, uri, args, kwargs):
        """
        Validation hook: check if the given payload (``args`` and ``kwargs``) is
        valid for the given URI and payload type.

        :param uri: The URI on which the session wants to perform the action.
        :type uri: str
        :param payload_type: The payload type to be validated. One of ``["event", "call", "call_result", "call_error"]``
        :type payload_type: str
        :param args: The positional payload to be validated.
        :type args: list
        :param kwargs: The keyword payload to be validated.
        :type kwargs: dict
        """


class IBroker(IRouterBase):

    """
    WAMP broker interface. Brokers are responsible for event routing
    """

    @abc.abstractmethod
    def processPublish(self, session, publish):
        """
        Process a WAMP ``PUBLISH`` message received from a WAMP client.

        :param session: Application session on which the message was received.
        :type session: A provider of :class:`autobahn.wamp.interfaces.ISession`.
        :param publish: The WAMP ``PUBLISH`` message to be processed.
        :type publish: Instance of :class:`autobahn.wamp.message.Publish`.
        """

    @abc.abstractmethod
    def processSubscribe(self, session, subscribe):
        """
        Process a WAMP ``SUBSCRIBE`` message received from a WAMP client.

        :param session: Application session on which the message was received.
        :type session: A provider of :class:`autobahn.wamp.interfaces.ISession`.
        :param publish: The WAMP ``SUBSCRIBE`` message to be processed.
        :type publish: Instance of :class:`autobahn.wamp.message.Subscribe`.
        """

    @abc.abstractmethod
    def processUnsubscribe(self, session, unsubscribe):
        """
        Process a WAMP ``UNSUBSCRIBE`` message received from a WAMP client.

        :param session: Application session on which the message was received.
        :type session: A provider of :class:`autobahn.wamp.interfaces.ISession`.
        :param publish: The WAMP ``UNSUBSCRIBE`` message to be processed.
        :type publish: Instance of :class:`autobahn.wamp.message.Unsubscribe`.
        """


class IDealer(IRouterBase):

    """
    WAMP dealer interface. Dealers are responsible for call routing.
    """

    @abc.abstractmethod
    def processRegister(self, session, register):
        """
        Process a WAMP ``REGISTER`` message received from a WAMP client.

        :param session: Application session on which the message was received.
        :type session: A provider of :class:`autobahn.wamp.interfaces.ISession`.
        :param publish: The WAMP ``REGISTER`` message to be processed.
        :type publish: Instance of :class:`autobahn.wamp.message.Register`.
        """

    @abc.abstractmethod
    def processUnregister(self, session, unregister):
        """
        Process a WAMP ``UNREGISTER`` message received from a WAMP client.

        :param session: Application session on which the message was received.
        :type session: A provider of :class:`autobahn.wamp.interfaces.ISession`.
        :param publish: The WAMP ``UNREGISTER`` message to be processed.
        :type publish: Instance of :class:`autobahn.wamp.message.Unregister`.
        """

    @abc.abstractmethod
    def processCall(self, session, call):
        """
        Process a WAMP ``CALL`` message received from a WAMP client.

        :param session: Application session on which the message was received.
        :type session: A provider of :class:`autobahn.wamp.interfaces.ISession`.
        :param publish: The WAMP ``CALL`` message to be processed.
        :type publish: Instance of :class:`autobahn.wamp.message.Call`.
        """

    @abc.abstractmethod
    def processCancel(self, session, cancel):
        """
        Process a WAMP ``CANCEL`` message received from a WAMP client.

        :param session: Application session on which the message was received.
        :type session: A provider of :class:`autobahn.wamp.interfaces.ISession`.
        :param publish: The WAMP ``CANCEL`` message to be processed.
        :type publish: Instance of :class:`autobahn.wamp.message.Cancel`.
        """

    @abc.abstractmethod
    def processYield(self, session, yield_):
        """
        Process a WAMP ``YIELD`` message received from a WAMP client.

        :param session: Application session on which the message was received.
        :type session: A provider of :class:`autobahn.wamp.interfaces.ISession`.
        :param publish: The WAMP ``YIELD`` message to be processed.
        :type publish: Instance of :class:`autobahn.wamp.message.Yield`.
        """

    @abc.abstractmethod
    def processInvocationError(self, session, error):
        """
        Process a WAMP ``ERROR`` message received from a WAMP client.

        :param session: Application session on which the message was received.
        :type session: A provider of :class:`autobahn.wamp.interfaces.ISession`.
        :param publish: The WAMP ``ERROR`` message to be processed.
        :type publish: Instance of :class:`autobahn.wamp.message.Error`.
        """


@six.add_metaclass(abc.ABCMeta)
class IRouterFactory(object):

    @abc.abstractmethod
    def get(self, realm):
        """
        Get router for responsible for given realm.
        """

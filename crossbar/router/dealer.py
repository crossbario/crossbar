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

import random

from autobahn import util
from autobahn.wamp import role
from autobahn.wamp import message
from autobahn.wamp.exception import ProtocolError, ApplicationError

from autobahn.wamp.message import _URI_PAT_STRICT_NON_EMPTY, \
    _URI_PAT_LOOSE_NON_EMPTY, _URI_PAT_STRICT_EMPTY, _URI_PAT_LOOSE_EMPTY

from crossbar.router.observation import UriObservationMap
from crossbar.router import RouterOptions, RouterAction
from crossbar._logging import make_logger

import txaio

__all__ = ('Dealer',)


class InvocationRequest(object):

    def __init__(self, id, caller, call):
        self.id = id
        self.caller = caller
        self.call = call


class RegistrationExtra(object):

    def __init__(self, invoke=message.Register.INVOKE_SINGLE):
        self.invoke = invoke
        self.roundrobin_current = 0


class Dealer(object):
    """
    Basic WAMP dealer.
    """

    log = make_logger()

    def __init__(self, router, options=None):
        """

        :param router: The router this dealer is part of.
        :type router: Object that implements :class:`crossbar.router.interfaces.IRouter`.
        :param options: Router options.
        :type options: Instance of :class:`crossbar.router.types.RouterOptions`.
        """
        self._router = router
        self._options = options or RouterOptions()

        # generator for WAMP request IDs
        self._request_id_gen = util.IdGenerator()

        # registration map managed by this dealer
        self._registration_map = UriObservationMap(ordered=True)

        # map: session -> set of registrations (needed for detach)
        self._session_to_registrations = {}

        # pending callee invocation requests
        self._invocations = {}

        # check all procedure URIs with strict rules
        self._option_uri_strict = self._options.uri_check == RouterOptions.URI_CHECK_STRICT

        # supported features from "WAMP Advanced Profile"
        self._role_features = role.RoleDealerFeatures(caller_identification=True,
                                                      pattern_based_registration=True,
                                                      session_meta_api=True,
                                                      registration_meta_api=True,
                                                      shared_registration=True,
                                                      progressive_call_results=True,
                                                      registration_revocation=True)

    def attach(self, session):
        """
        Implements :func:`crossbar.router.interfaces.IDealer.attach`
        """
        if session not in self._session_to_registrations:
            self._session_to_registrations[session] = set()
        else:
            raise Exception("session with ID {} already attached".format(session._session_id))

    def detach(self, session):
        """
        Implements :func:`crossbar.router.interfaces.IDealer.detach`
        """
        if session in self._session_to_registrations:

            for registration in self._session_to_registrations[session]:

                was_registered, was_last_callee = self._registration_map.drop_observer(session, registration)

                # publish WAMP meta events
                #
                if self._router._realm:
                    service_session = self._router._realm.session
                    if service_session and not registration.uri.startswith(u'wamp.'):
                        if was_registered:
                            service_session.publish(u'wamp.registration.on_unregister', session._session_id, registration.id)
                        if was_last_callee:
                            service_session.publish(u'wamp.registration.on_delete', session._session_id, registration.id)

            del self._session_to_registrations[session]

        else:
            raise Exception(u"session with ID {} not attached".format(session._session_id))

    def processRegister(self, session, register):
        """
        Implements :func:`crossbar.router.interfaces.IDealer.processRegister`
        """
        # check topic URI: for SUBSCRIBE, must be valid URI (either strict or loose), and all
        # URI components must be non-empty other than for wildcard subscriptions
        #
        if self._option_uri_strict:
            if register.match == u"wildcard":
                uri_is_valid = _URI_PAT_STRICT_EMPTY.match(register.procedure)
            else:
                uri_is_valid = _URI_PAT_STRICT_NON_EMPTY.match(register.procedure)
        else:
            if register.match == u"wildcard":
                uri_is_valid = _URI_PAT_LOOSE_EMPTY.match(register.procedure)
            else:
                uri_is_valid = _URI_PAT_LOOSE_NON_EMPTY.match(register.procedure)

        if not uri_is_valid:
            reply = message.Error(message.Register.MESSAGE_TYPE, register.request, ApplicationError.INVALID_URI, [u"register for invalid procedure URI '{0}' (URI strict checking {1})".format(register.procedure, self._option_uri_strict)])
            session._transport.send(reply)
            return

        # disallow registration of procedures starting with "wamp." and  "crossbar." other than for
        # trusted sessions (that are sessions built into Crossbar.io)
        #
        if session._authrole is not None and session._authrole != u"trusted":
            is_restricted = register.procedure.startswith(u"wamp.") or register.procedure.startswith(u"crossbar.")
            if is_restricted:
                reply = message.Error(message.Register.MESSAGE_TYPE, register.request, ApplicationError.INVALID_URI, [u"register for restricted procedure URI '{0}')".format(register.procedure)])
                session._transport.send(reply)
                return

        # get existing registration for procedure / matching strategy - if any
        #
        registration = self._registration_map.get_observation(register.procedure, register.match)
        if registration:

            # there is an existing registration, and that has an invocation strategy that only allows a single callee
            # on a the given registration
            #
            if registration.extra.invoke == message.Register.INVOKE_SINGLE:
                reply = message.Error(message.Register.MESSAGE_TYPE, register.request, ApplicationError.PROCEDURE_ALREADY_EXISTS, [u"register for already registered procedure '{0}'".format(register.procedure)])
                session._transport.send(reply)
                return

            # there is an existing registration, and that has an invokation strategy different from the one
            # requested by the new callee
            #
            if registration.extra.invoke != register.invoke:
                reply = message.Error(message.Register.MESSAGE_TYPE, register.request, ApplicationError.PROCEDURE_EXISTS_INVOCATION_POLICY_CONFLICT, [u"register for already registered procedure '{0}' with conflicting invocation policy (has {1} and {2} was requested)".format(register.procedure, registration.extra.invoke, register.invoke)])
                session._transport.send(reply)
                return

        # authorize action
        #
        d = txaio.as_future(self._router.authorize, session, register.procedure, RouterAction.ACTION_REGISTER)

        def on_authorize_success(authorized):
            if not authorized:
                # error reply since session is not authorized to register
                #
                reply = message.Error(message.Register.MESSAGE_TYPE, register.request, ApplicationError.NOT_AUTHORIZED, [u"session is not authorized to register procedure '{0}'".format(register.procedure)])

            else:
                # ok, session authorized to register. now get the registration
                #
                registration_extra = RegistrationExtra(register.invoke)
                registration, was_already_registered, is_first_callee = self._registration_map.add_observer(session, register.procedure, register.match, registration_extra)

                if not was_already_registered:
                    self._session_to_registrations[session].add(registration)

                # publish WAMP meta events
                #
                if self._router._realm:
                    service_session = self._router._realm.session
                    if service_session and not registration.uri.startswith(u'wamp.'):
                        if is_first_callee:
                            registration_details = {
                                'id': registration.id,
                                'created': registration.created,
                                'uri': registration.uri,
                                'match': registration.match,
                                'invoke': registration.extra.invoke,
                            }
                            service_session.publish(u'wamp.registration.on_create', session._session_id, registration_details)
                        if not was_already_registered:
                            service_session.publish(u'wamp.registration.on_register', session._session_id, registration.id)

                # acknowledge register with registration ID
                #
                reply = message.Registered(register.request, registration.id)

            # send out reply to register requestor
            #
            session._transport.send(reply)

        def on_authorize_error(err):
            """
            the call to authorize the action _itself_ failed (note this is
            different from the call to authorize succeed, but the
            authorization being denied)
            """
            self.log.failure(err)
            reply = message.Error(
                message.Register.MESSAGE_TYPE,
                register.request,
                ApplicationError.AUTHORIZATION_FAILED,
                [u"failed to authorize session for registering procedure '{0}': {1}".format(register.procedure, err.value)]
            )
            session._transport.send(reply)

        txaio.add_callbacks(d, on_authorize_success, on_authorize_error)

    def processUnregister(self, session, unregister):
        """
        Implements :func:`crossbar.router.interfaces.IDealer.processUnregister`
        """
        # get registration by registration ID or None (if it doesn't exist on this broker)
        #
        registration = self._registration_map.get_observation_by_id(unregister.registration)

        if registration:

            if session in registration.observers:

                was_registered, was_last_callee = self._unregister(registration, session)

                reply = message.Unregistered(unregister.request)
            else:
                # registration exists on this dealer, but the session that wanted to unregister wasn't registered
                #
                reply = message.Error(message.Unregister.MESSAGE_TYPE, unregister.request, ApplicationError.NO_SUCH_REGISTRATION)

        else:
            # registration doesn't even exist on this broker
            #
            reply = message.Error(message.Unregister.MESSAGE_TYPE, unregister.request, ApplicationError.NO_SUCH_REGISTRATION)

        session._transport.send(reply)

    def _unregister(self, registration, session):

        # drop session from registration observers
        #
        was_registered, was_last_callee = self._registration_map.drop_observer(session, registration)

        # remove registration from session->registrations map
        #
        if was_registered:
            self._session_to_registrations[session].discard(registration)

        # publish WAMP meta events
        #
        if self._router._realm:
            service_session = self._router._realm.session
            if service_session and not registration.uri.startswith(u'wamp.'):
                if was_registered:
                    service_session.publish(u'wamp.registration.on_unregister', session._session_id, registration.id)
                if was_last_callee:
                    service_session.publish(u'wamp.registration.on_delete', session._session_id, registration.id)

        return was_registered, was_last_callee

    def removeCallee(self, registration, session, reason=None):
        """
        Actively unregister a callee session from a registration.
        """
        was_registered, was_last_callee = self._unregister(registration, session)

        # actively inform the callee that it has been unregistered
        #
        if 'callee' in session._session_roles and session._session_roles['callee'] and session._session_roles['callee'].registration_revocation:
            reply = message.Unregistered(0, registration=registration.id, reason=reason)
            session._transport.send(reply)

        return was_registered, was_last_callee

    def processCall(self, session, call):
        """
        Implements :func:`crossbar.router.interfaces.IDealer.processCall`
        """
        # check procedure URI: for CALL, must be valid URI (either strict or loose), and
        # all URI components must be non-empty
        if self._option_uri_strict:
            uri_is_valid = _URI_PAT_STRICT_NON_EMPTY.match(call.procedure)
        else:
            uri_is_valid = _URI_PAT_LOOSE_NON_EMPTY.match(call.procedure)

        if not uri_is_valid:
            reply = message.Error(message.Call.MESSAGE_TYPE, call.request, ApplicationError.INVALID_URI, [u"call with invalid procedure URI '{0}' (URI strict checking {1})".format(call.procedure, self._option_uri_strict)])
            session._transport.send(reply)
            return

        # get registrations active on the procedure called
        #
        registration = self._registration_map.best_matching_observation(call.procedure)

        if registration:

            # validate payload
            #
            try:
                self._router.validate('call', call.procedure, call.args, call.kwargs)
            except Exception as e:
                reply = message.Error(message.Call.MESSAGE_TYPE, call.request, ApplicationError.INVALID_ARGUMENT, [u"call of procedure '{0}' with invalid application payload: {1}".format(call.procedure, e)])
                session._transport.send(reply)
                return

            # authorize CALL action
            #
            d = txaio.as_future(self._router.authorize, session, call.procedure, RouterAction.ACTION_CALL)

            def on_authorize_success(authorized):

                # the call to authorize the action _itself_ succeeded. now go on depending on whether
                # the action was actually authorized or not ..
                #
                if not authorized:
                    reply = message.Error(message.Call.MESSAGE_TYPE, call.request, ApplicationError.NOT_AUTHORIZED, [u"session is not authorized to call procedure '{0}'".format(call.procedure)])
                    session._transport.send(reply)

                else:

                    # determine callee according to invocation policy
                    #
                    if registration.extra.invoke == message.Register.INVOKE_SINGLE:
                        callee = registration.observers[0]

                    elif registration.extra.invoke == message.Register.INVOKE_FIRST:
                        callee = registration.observers[0]

                    elif registration.extra.invoke == message.Register.INVOKE_LAST:
                        callee = registration.observers[len(registration.observers) - 1]

                    elif registration.extra.invoke == message.Register.INVOKE_ROUNDROBIN:
                        callee = registration.observers[registration.extra.roundrobin_current % len(registration.observers)]
                        registration.extra.roundrobin_current += 1

                    elif registration.extra.invoke == message.Register.INVOKE_RANDOM:
                        callee = registration.observers[random.randint(0, len(registration.observers) - 1)]

                    else:
                        # should not arrive here
                        raise Exception(u"logic error")

                    # new ID for the invocation
                    #
                    invocation_request_id = self._request_id_gen.next()

                    # caller disclosure
                    #
                    if call.disclose_me:
                        caller = session._session_id
                    else:
                        caller = None

                    # for pattern-based registrations, the INVOCATION must contain
                    # the actual procedure being called
                    #
                    if registration.match != message.Register.MATCH_EXACT:
                        procedure = call.procedure
                    else:
                        procedure = None

                    invocation = message.Invocation(invocation_request_id,
                                                    registration.id,
                                                    args=call.args,
                                                    kwargs=call.kwargs,
                                                    timeout=call.timeout,
                                                    receive_progress=call.receive_progress,
                                                    caller=caller,
                                                    procedure=procedure)

                    self._invocations[invocation_request_id] = InvocationRequest(invocation_request_id, session, call)
                    callee._transport.send(invocation)

            def on_authorize_error(err):
                """
                the call to authorize the action _itself_ failed (note this is
                different from the call to authorize succeed, but the
                authorization being denied)
                """
                self.log.failure(err)
                reply = message.Error(
                    message.Call.MESSAGE_TYPE,
                    call.request,
                    ApplicationError.AUTHORIZATION_FAILED,
                    [u"failed to authorize session for calling procedure '{0}': {1}".format(call.procedure, err.value)]
                )
                session._transport.send(reply)

            txaio.add_callbacks(d, on_authorize_success, on_authorize_error)

        else:
            reply = message.Error(message.Call.MESSAGE_TYPE, call.request, ApplicationError.NO_SUCH_PROCEDURE, [u"no callee registered for procedure '{0}'".format(call.procedure)])
            session._transport.send(reply)

    # noinspection PyUnusedLocal
    def processCancel(self, session, cancel):
        """
        Implements :func:`crossbar.router.interfaces.IDealer.processCancel`
        """
        assert(session in self._session_to_registrations)

        raise Exception("not implemented")

    def processYield(self, session, yield_):
        """
        Implements :func:`crossbar.router.interfaces.IDealer.processYield`
        """
        # assert(session in self._session_to_registrations)

        if yield_.request in self._invocations:

            # get the invocation request tracked for the caller
            #
            invocation_request = self._invocations[yield_.request]

            # validate payload
            #
            is_valid = True
            try:
                self._router.validate('call_result', invocation_request.call.procedure, yield_.args, yield_.kwargs)
            except Exception as e:
                is_valid = False
                reply = message.Error(message.Call.MESSAGE_TYPE, invocation_request.call.request, ApplicationError.INVALID_ARGUMENT, [u"call result from procedure '{0}' with invalid application payload: {1}".format(invocation_request.call.procedure, e)])
            else:
                reply = message.Result(invocation_request.call.request, args=yield_.args, kwargs=yield_.kwargs, progress=yield_.progress)

            # the calling session might have been lost in the meantime ..
            #
            if invocation_request.caller._transport:
                invocation_request.caller._transport.send(reply)

            # the call is done if it's a regular call (non-progressive) or if the payload was invalid
            #
            if not yield_.progress or not is_valid:
                del self._invocations[yield_.request]

        else:
            raise ProtocolError(u"Dealer.onYield(): YIELD received for non-pending request ID {0}".format(yield_.request))

    def processInvocationError(self, session, error):
        """
        Implements :func:`crossbar.router.interfaces.IDealer.processInvocationError`
        """
        # assert(session in self._session_to_registrations)

        if error.request in self._invocations:

            # get the invocation request tracked for the caller
            #
            invocation_request = self._invocations[error.request]

            # validate payload
            #
            try:
                self._router.validate('call_error', invocation_request.call.procedure, error.args, error.kwargs)
            except Exception as e:
                reply = message.Error(message.Call.MESSAGE_TYPE, invocation_request.call.request, ApplicationError.INVALID_ARGUMENT, [u"call error from procedure '{0}' with invalid application payload: {1}".format(invocation_request.call.procedure, e)])
            else:
                reply = message.Error(message.Call.MESSAGE_TYPE, invocation_request.call.request, error.error, args=error.args, kwargs=error.kwargs)

            # the calling session might have been lost in the meantime ..
            #
            if invocation_request.caller._transport:
                invocation_request.caller._transport.send(reply)

            # the call is done
            #
            del self._invocations[error.request]

        else:
            raise ProtocolError(u"Dealer.onInvocationError(): ERROR received for non-pending request_type {0} and request ID {1}".format(error.request_type, error.request))

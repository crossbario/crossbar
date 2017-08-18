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

from __future__ import absolute_import

import random
import txaio

from autobahn import util
from autobahn.wamp import role, message, types
from autobahn.wamp.exception import ProtocolError, ApplicationError

from autobahn.wamp.message import \
    _URI_PAT_STRICT_LAST_EMPTY, \
    _URI_PAT_LOOSE_LAST_EMPTY, \
    _URI_PAT_STRICT_NON_EMPTY, \
    _URI_PAT_LOOSE_NON_EMPTY, \
    _URI_PAT_STRICT_EMPTY, \
    _URI_PAT_LOOSE_EMPTY

from crossbar.router.observation import UriObservationMap
from crossbar.router import RouterOptions

from txaio import make_logger

__all__ = ('Dealer',)


class InvocationRequest(object):
    """
    Holding information for an individual invocation.
    """

    __slots__ = ('id', 'registration', 'caller', 'call', 'callee', 'canceled')

    def __init__(self, id, registration, caller, call, callee):
        self.id = id
        self.registration = registration
        self.caller = caller
        self.call = call
        self.callee = callee
        self.canceled = False


class RegistrationExtra(object):
    """
    Registration-level extra information held in UriObservationMap.
    """

    __slots__ = ('invoke', 'roundrobin_current')

    def __init__(self, invoke=message.Register.INVOKE_SINGLE):
        self.invoke = invoke
        self.roundrobin_current = 0


class RegistrationCalleeExtra(object):
    """
    Callee-level extra information held in UriObservationMap.
    """

    __slots__ = ('concurrency', 'concurrency_current')

    def __init__(self, concurrency=None):
        self.concurrency = concurrency
        self.concurrency_current = 0

    def __repr__(self):
        return '{}(concurrency={}, concurrency_current={})'.format(self.__class__.__name__, self.concurrency, self.concurrency_current)


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

        # map: session -> in-flight invocations
        self._callee_to_invocations = {}
        # BEWARE: this map must be kept up-to-date along with the
        # _invocations map below! Use the helper methods
        # _add_invoke_request and _remove_invoke_request

        # map: session -> in-flight invocations
        self._caller_to_invocations = {}

        # careful here: the 'request' IDs are unique per-session
        # (only) so we map from (session_id, call) tuples to in-flight invocations
        # map: (session_id, call) -> in-flight invocations
        self._invocations_by_call = {}

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
                                                      registration_revocation=True,
                                                      payload_transparency=True,
                                                      testament_meta_api=True,
                                                      payload_encryption_cryptobox=True,
                                                      call_canceling=True)

        # store for call queues
        if self._router._store:
            self._call_store = self._router._store.call_store
        else:
            self._call_store = None

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
        # if the caller on an in-flight invocation goes away
        # INTERRUPT the callee if supported
        if session in self._caller_to_invocations:
            outstanding = self._caller_to_invocations.get(session, [])
            for invoke in outstanding:  # type: InvocationRequest
                if invoke.callee is invoke.caller:  # if the calling itself - no need to notify
                    continue
                callee = invoke.callee
                if 'callee' not in callee._session_roles \
                        or not callee._session_roles['callee'] \
                        or not callee._session_roles['callee'].call_canceling:
                    self.log.debug(
                        "INTERRUPT not supported on in-flight INVOKE with id={request} on"
                        " session {session} (caller went away)",
                        request=invoke.id,
                        session=session._session_id,
                    )
                    continue
                self.log.debug(
                    "INTERRUPTing in-flight INVOKE with id={request} on"
                    " session {session} (caller went away)",
                    request=invoke.id,
                    session=session._session_id,
                )
                self._router.send(invoke.callee, message.Interrupt(invoke.id))

        if session in self._session_to_registrations:
            # send out Errors for any in-flight calls we have
            outstanding = self._callee_to_invocations.get(session, [])
            for invoke in outstanding:
                self.log.debug(
                    "Cancelling in-flight INVOKE with id={request} on"
                    " session {session}",
                    request=invoke.call.request,
                    session=session._session_id,
                )
                reply = message.Error(
                    message.Call.MESSAGE_TYPE,
                    invoke.call.request,
                    ApplicationError.CANCELED,
                    [u"callee disconnected from in-flight request"],
                )
                # send this directly to the caller's session
                # (it is possible the caller was disconnected and thus
                # _transport is None before we get here though)
                if invoke.caller._transport:
                    invoke.caller._transport.send(reply)

            for registration in self._session_to_registrations[session]:
                was_registered, was_last_callee = self._registration_map.drop_observer(session, registration)

                if was_registered and was_last_callee:
                    self._registration_map.delete_observation(registration)

                # publish WAMP meta events
                #
                if self._router._realm:
                    service_session = self._router._realm.session
                    if service_session and not registration.uri.startswith(u'wamp.'):
                        options = types.PublishOptions(
                            correlation=None
                        )
                        if was_registered:
                            service_session.publish(u'wamp.registration.on_unregister', session._session_id, registration.id, options=options)
                        if was_last_callee:
                            service_session.publish(u'wamp.registration.on_delete', session._session_id, registration.id, options=options)

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
            elif register.match == u"prefix":
                uri_is_valid = _URI_PAT_STRICT_LAST_EMPTY.match(register.procedure)
            elif register.match == u"exact":
                uri_is_valid = _URI_PAT_STRICT_NON_EMPTY.match(register.procedure)
            else:
                # should not arrive here
                raise Exception("logic error")
        else:
            if register.match == u"wildcard":
                uri_is_valid = _URI_PAT_LOOSE_EMPTY.match(register.procedure)
            elif register.match == u"prefix":
                uri_is_valid = _URI_PAT_LOOSE_LAST_EMPTY.match(register.procedure)
            elif register.match == u"exact":
                uri_is_valid = _URI_PAT_LOOSE_NON_EMPTY.match(register.procedure)
            else:
                # should not arrive here
                raise Exception("logic error")

        if not uri_is_valid:
            reply = message.Error(message.Register.MESSAGE_TYPE, register.request, ApplicationError.INVALID_URI, [u"register for invalid procedure URI '{0}' (URI strict checking {1})".format(register.procedure, self._option_uri_strict)])
            reply.correlation = register.correlation
            self._router.send(session, reply)
            return

        # disallow registration of procedures starting with "wamp." other than for
        # trusted sessions (that are sessions built into Crossbar.io routing core)
        #
        if session._authrole is not None and session._authrole != u"trusted":
            is_restricted = register.procedure.startswith(u"wamp.")
            if is_restricted:
                reply = message.Error(message.Register.MESSAGE_TYPE, register.request, ApplicationError.INVALID_URI, [u"register for restricted procedure URI '{0}')".format(register.procedure)])
                reply.correlation = register.correlation
                self._router.send(session, reply)
                return

        # get existing registration for procedure / matching strategy - if any
        #
        registration = self._registration_map.get_observation(register.procedure, register.match)

        # XXX actually, shouldn't we do *all* processing only after
        # authorization? otherwise we're leaking the fact that a
        # procedure exists here at all...

        # if force_reregister was enabled, we only do any actual
        # kicking of existing registrations *after* authorization
        if registration and not register.force_reregister:
            # there is an existing registration, and that has an
            # invocation strategy that only allows a single callee
            # on a the given registration
            #
            if registration.extra.invoke == message.Register.INVOKE_SINGLE:
                reply = message.Error(
                    message.Register.MESSAGE_TYPE,
                    register.request,
                    ApplicationError.PROCEDURE_ALREADY_EXISTS,
                    [u"register for already registered procedure '{0}'".format(register.procedure)]
                )
                reply.correlation = register.correlation
                self._router.send(session, reply)
                return

            # there is an existing registration, and that has an
            # invokation strategy different from the one requested
            # by the new callee
            #
            if registration.extra.invoke != register.invoke:
                reply = message.Error(
                    message.Register.MESSAGE_TYPE,
                    register.request,
                    ApplicationError.PROCEDURE_EXISTS_INVOCATION_POLICY_CONFLICT,
                    [
                        u"register for already registered procedure '{0}' "
                        u"with conflicting invocation policy (has {1} and "
                        u"{2} was requested)".format(
                            register.procedure,
                            registration.extra.invoke,
                            register.invoke
                        )
                    ]
                )
                reply.correlation = register.correlation
                self._router.send(session, reply)
                return

        # authorize REGISTER action
        #
        d = self._router.authorize(session, register.procedure, u'register', options=register.marshal_options())

        def on_authorize_success(authorization):
            if not authorization[u'allow']:
                # error reply since session is not authorized to register
                #
                reply = message.Error(message.Register.MESSAGE_TYPE, register.request, ApplicationError.NOT_AUTHORIZED, [u"session is not authorized to register procedure '{0}'".format(register.procedure)])

            else:
                registration = self._registration_map.get_observation(register.procedure, register.match)
                if register.force_reregister and registration:
                    for obs in registration.observers:
                        self._registration_map.drop_observer(obs, registration)
                        kicked = message.Unregistered(
                            0,
                            registration=registration.id,
                            reason=u"wamp.error.unregistered",
                        )
                        kicked.correlation = register.correlation
                        self._router.send(obs, kicked)
                    self._registration_map.delete_observation(registration)

                # ok, session authorized to register. now get the registration
                #
                registration_extra = RegistrationExtra(register.invoke)
                registration_callee_extra = RegistrationCalleeExtra(register.concurrency)
                registration, was_already_registered, is_first_callee = self._registration_map.add_observer(session, register.procedure, register.match, registration_extra, registration_callee_extra)

                if not was_already_registered:
                    self._session_to_registrations[session].add(registration)

                # publish WAMP meta events
                #
                if self._router._realm:
                    service_session = self._router._realm.session
                    if service_session and not registration.uri.startswith(u'wamp.'):
                        options = types.PublishOptions(
                            correlation=register.correlation
                        )
                        if is_first_callee:
                            registration_details = {
                                u'id': registration.id,
                                u'created': registration.created,
                                u'uri': registration.uri,
                                u'match': registration.match,
                                u'invoke': registration.extra.invoke,
                            }
                            service_session.publish(u'wamp.registration.on_create', session._session_id, registration_details, options=options)
                        if not was_already_registered:
                            service_session.publish(u'wamp.registration.on_register', session._session_id, registration.id, options=options)

                # acknowledge register with registration ID
                #
                reply = message.Registered(register.request, registration.id)

            # send out reply to register requestor
            #
            reply.correlation = register.correlation
            self._router.send(session, reply)

        def on_authorize_error(err):
            """
            the call to authorize the action _itself_ failed (note this is
            different from the call to authorize succeed, but the
            authorization being denied)
            """
            self.log.failure("Authorization of 'register' for '{uri}' failed", uri=register.procedure, failure=err)
            reply = message.Error(
                message.Register.MESSAGE_TYPE,
                register.request,
                ApplicationError.AUTHORIZATION_FAILED,
                [u"failed to authorize session for registering procedure '{0}': {1}".format(register.procedure, err.value)]
            )
            reply.correlation = register.correlation
            self._router.send(session, reply)

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

        reply.correlation = unregister.correlation
        self._router.send(session, reply)

    def _unregister(self, registration, session):

        # drop session from registration observers
        #
        was_registered, was_last_callee = self._registration_map.drop_observer(session, registration)

        if was_registered and was_last_callee:
            self._registration_map.delete_observation(registration)

        # remove registration from session->registrations map
        #
        if was_registered:
            self._session_to_registrations[session].discard(registration)

        # publish WAMP meta events
        #
        if self._router._realm:
            service_session = self._router._realm.session
            if service_session and not registration.uri.startswith(u'wamp.'):
                options = types.PublishOptions(
                    correlation=None
                )
                if was_registered:
                    service_session.publish(u'wamp.registration.on_unregister', session._session_id, registration.id, options=options)
                if was_last_callee:
                    service_session.publish(u'wamp.registration.on_delete', session._session_id, registration.id, options=options)

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
            self._router.send(session, reply)

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
            reply.correlation = call.correlation
            self._router.send(session, reply)
            return

        # get registrations active on the procedure called
        #
        registration = self._registration_map.best_matching_observation(call.procedure)

        if registration:

            # validate payload (skip in "payload_transparency" mode)
            #
            if call.payload is None:
                try:
                    self._router.validate(u'call', call.procedure, call.args, call.kwargs)
                except Exception as e:
                    reply = message.Error(message.Call.MESSAGE_TYPE, call.request, ApplicationError.INVALID_ARGUMENT, [u"call of procedure '{0}' with invalid application payload: {1}".format(call.procedure, e)])
                    reply.correlation = call.correlation
                    self._router.send(session, reply)
                    return

            # authorize CALL action
            #
            d = self._router.authorize(session, call.procedure, u'call', options=call.marshal_options())

            def on_authorize_success(authorization):
                # the call to authorize the action _itself_ succeeded. now go on depending on whether
                # the action was actually authorized or not ..
                #
                if not authorization[u'allow']:
                    reply = message.Error(message.Call.MESSAGE_TYPE, call.request, ApplicationError.NOT_AUTHORIZED, [u"session is not authorized to call procedure '{0}'".format(call.procedure)])
                    reply.correlation = call.correlation
                    self._router.send(session, reply)

                else:
                    self._call(session, call, registration, authorization)

            def on_authorize_error(err):
                """
                the call to authorize the action _itself_ failed (note this is
                different from the call to authorize succeed, but the
                authorization being denied)
                """
                self.log.failure("Authorization of 'call' for '{uri}' failed", uri=call.procedure, failure=err)
                reply = message.Error(
                    message.Call.MESSAGE_TYPE,
                    call.request,
                    ApplicationError.AUTHORIZATION_FAILED,
                    [u"failed to authorize session for calling procedure '{0}': {1}".format(call.procedure, err.value)]
                )
                reply.correlation = call.correlation
                self._router.send(session, reply)

            txaio.add_callbacks(d, on_authorize_success, on_authorize_error)

        else:
            reply = message.Error(message.Call.MESSAGE_TYPE, call.request, ApplicationError.NO_SUCH_PROCEDURE, [u"no callee registered for procedure <{0}>".format(call.procedure)])
            reply.correlation = call.correlation
            self._router.send(session, reply)

    def _call(self, session, call, registration, authorization, is_queued_call=False):
        # will hold the callee (the concrete endpoint) that we will forward the call to ..
        #
        callee = None
        callee_extra = None

        # determine callee according to invocation policy
        #
        if registration.extra.invoke in [message.Register.INVOKE_SINGLE, message.Register.INVOKE_FIRST, message.Register.INVOKE_LAST]:

            # a single endpoint is considered for forwarding the call ..

            if registration.extra.invoke == message.Register.INVOKE_SINGLE:
                callee = registration.observers[0]

            elif registration.extra.invoke == message.Register.INVOKE_FIRST:
                callee = registration.observers[0]

            elif registration.extra.invoke == message.Register.INVOKE_LAST:
                callee = registration.observers[len(registration.observers) - 1]

            else:
                # should not arrive here
                raise Exception(u"logic error")

            # check maximum concurrency of the (single) endpoint
            callee_extra = registration.observers_extra.get(callee, None)
            if callee_extra:
                if callee_extra.concurrency and callee_extra.concurrency_current >= callee_extra.concurrency:
                    if is_queued_call or (self._call_store and self._call_store.maybe_queue_call(session, call, registration, authorization)):
                        return False
                    else:
                        reply = message.Error(
                            message.Call.MESSAGE_TYPE,
                            call.request,
                            u'crossbar.error.max_concurrency_reached',
                            [u'maximum concurrency {} of callee/endpoint reached (on non-shared/single registration)'.format(callee_extra.concurrency)]
                        )
                        reply.correlation = call.correlation
                        self._router.send(session, reply)
                        return False
                else:
                    callee_extra.concurrency_current += 1

        elif registration.extra.invoke == message.Register.INVOKE_ROUNDROBIN:

            # remember where we started to search for a suitable callee/endpoint in the round-robin list of callee endpoints
            roundrobin_start_index = registration.extra.roundrobin_current % len(registration.observers)

            # now search fo a suitable callee/endpoint
            while True:
                callee = registration.observers[registration.extra.roundrobin_current % len(registration.observers)]
                callee_extra = registration.observers_extra.get(callee, None)

                registration.extra.roundrobin_current += 1

                if callee_extra and callee_extra.concurrency:

                    if callee_extra.concurrency_current >= callee_extra.concurrency:

                        # this callee has set a maximum concurrency that has already been reached.
                        # we need to search further .. but only if we haven't reached the beginning
                        # of our round-robin list
                        if registration.extra.roundrobin_current % len(registration.observers) == roundrobin_start_index:
                            # we've looked through the whole round-robin list, and didn't find a suitable
                            # callee (one that hasn't it's maximum concurrency already reached).
                            if is_queued_call or (self._call_store and self._call_store.maybe_queue_call(session, call, registration, authorization)):
                                return False
                            else:
                                reply = message.Error(
                                    message.Call.MESSAGE_TYPE,
                                    call.request,
                                    u'crossbar.error.max_concurrency_reached',
                                    [u'maximum concurrency of all callee/endpoints reached (on round-robin registration)'.format(callee_extra.concurrency)]
                                )
                                reply.correlation = call.correlation
                                self._router.send(session, reply)
                                return False
                        else:
                            # .. search on ..
                            pass
                    else:
                        # ok, we've found a callee that has set a maximum concurrency, but where the
                        # maximum has not yet been reached
                        break
                else:
                    # ok, we've found a callee which hasn't set a maximum concurrency, and hence is always
                    # eligible for having a call forwarded to
                    break

            if callee_extra:
                callee_extra.concurrency_current += 1

        elif registration.extra.invoke == message.Register.INVOKE_RANDOM:

            # FIXME: implement max. concurrency and call queueing
            callee = registration.observers[random.randint(0, len(registration.observers) - 1)]

        else:
            # should not arrive here
            raise Exception(u"logic error")

        # new ID for the invocation
        #
        invocation_request_id = self._request_id_gen.next()

        # caller disclosure
        #
        if authorization[u'disclose']:
            disclose = True
        elif (call.procedure.startswith(u"wamp.") or
              call.procedure.startswith(u"crossbar.")):
            disclose = True
        else:
            disclose = False

        if disclose:
            caller = session._session_id
            caller_authid = session._authid
            caller_authrole = session._authrole
        else:
            caller = None
            caller_authid = None
            caller_authrole = None

        # for pattern-based registrations, the INVOCATION must contain
        # the actual procedure being called
        #
        if registration.match != message.Register.MATCH_EXACT:
            procedure = call.procedure
        else:
            procedure = None

        if call.payload:
            invocation = message.Invocation(invocation_request_id,
                                            registration.id,
                                            payload=call.payload,
                                            timeout=call.timeout,
                                            receive_progress=call.receive_progress,
                                            caller=caller,
                                            caller_authid=caller_authid,
                                            caller_authrole=caller_authrole,
                                            procedure=procedure,
                                            enc_algo=call.enc_algo,
                                            enc_key=call.enc_key,
                                            enc_serializer=call.enc_serializer)
        else:
            invocation = message.Invocation(invocation_request_id,
                                            registration.id,
                                            args=call.args,
                                            kwargs=call.kwargs,
                                            timeout=call.timeout,
                                            receive_progress=call.receive_progress,
                                            caller=caller,
                                            caller_authid=caller_authid,
                                            caller_authrole=caller_authrole,
                                            procedure=procedure)

        invocation.correlation = call.correlation

        self._add_invoke_request(invocation_request_id, registration, session, call, callee)
        self._router.send(callee, invocation)
        return True

    def _add_invoke_request(self, invocation_request_id, registration, session, call, callee):
        """
        Internal helper.  Adds an InvocationRequest to both the
        _callee_to_invocations and _invocations maps.
        """
        invoke_request = InvocationRequest(invocation_request_id, registration, session, call, callee)
        self._invocations[invocation_request_id] = invoke_request
        self._invocations_by_call[session._session_id, call.request] = invoke_request
        invokes = self._callee_to_invocations.get(callee, [])
        invokes.append(invoke_request)
        self._callee_to_invocations[callee] = invokes

        # map to keep track of the invocations by each caller
        invokes = self._caller_to_invocations.get(session, [])
        invokes.append(invoke_request)
        self._caller_to_invocations[session] = invokes

        return invoke_request

    def _remove_invoke_request(self, invocation_request):
        """
        Internal helper. Removes an InvocationRequest from both the
        _callee_to_invocations and _invocations maps.
        """
        invokes = self._callee_to_invocations[invocation_request.callee]
        invokes.remove(invocation_request)
        if not invokes:
            del self._callee_to_invocations[invocation_request.callee]

        invokes = self._caller_to_invocations[invocation_request.caller]
        invokes.remove(invocation_request)
        if not invokes:
            del self._caller_to_invocations[invocation_request.caller]

        del self._invocations[invocation_request.id]

        # the session_id will be None if the caller session has
        # already vanished
        caller_id = invocation_request.caller._session_id
        if caller_id is not None:
            del self._invocations_by_call[caller_id, invocation_request.call.request]

    # noinspection PyUnusedLocal
    def processCancel(self, session, cancel):
        # type: (session.RouterSession, message.Cancel) -> None
        """
        Implements :func:`crossbar.router.interfaces.IDealer.processCancel`
        """
        if (session._session_id, cancel.request) in self._invocations_by_call:
            invocation_request = self._invocations_by_call[session._session_id, cancel.request]

            # correlate the cancel request to the original call
            cancel.correlation = invocation_request.call.correlation

            # for those that repeatedly push elevator buttons
            if invocation_request.canceled:
                return

            invocation_request.canceled = True

            if 'callee' in session._session_roles and session._session_roles['callee'] and session._session_roles['callee'].call_canceling:
                interrupt = message.Interrupt(invocation_request.id, cancel.mode)
                interrupt.correlation = invocation_request.call.correlation
                self._router.send(invocation_request.callee, interrupt)

            return

    def processYield(self, session, yield_):
        """
        Implements :func:`crossbar.router.interfaces.IDealer.processYield`
        """
        # assert(session in self._session_to_registrations)

        if yield_.request in self._invocations:

            # get the invocation request tracked for the caller
            #
            invocation_request = self._invocations[yield_.request]

            # correlate the received yield return to the original call
            yield_.correlation = invocation_request.call.correlation

            # check to make sure this session is the one that is supposed to be yielding
            if invocation_request.callee is not session:
                raise ProtocolError(
                    u"Dealer.onYield(): YIELD received for non-owned request ID {0}".format(yield_.request))

            is_valid = True
            if yield_.payload is None:
                # validate normal args/kwargs payload
                try:
                    self._router.validate('call_result', invocation_request.call.procedure, yield_.args, yield_.kwargs)
                except Exception as e:
                    is_valid = False
                    reply = message.Error(message.Call.MESSAGE_TYPE, invocation_request.call.request, ApplicationError.INVALID_ARGUMENT, [u"call result from procedure '{0}' with invalid application payload: {1}".format(invocation_request.call.procedure, e)])
                else:
                    reply = message.Result(invocation_request.call.request, args=yield_.args, kwargs=yield_.kwargs, progress=yield_.progress)
            else:
                reply = message.Result(invocation_request.call.request, payload=yield_.payload, progress=yield_.progress,
                                       enc_algo=yield_.enc_algo, enc_key=yield_.enc_key, enc_serializer=yield_.enc_serializer)

            # the calling session might have been lost in the meantime ..
            #
            if invocation_request.caller._transport:
                reply.correlation = invocation_request.call.correlation
                self._router.send(invocation_request.caller, reply)

            # the call is done if it's a regular call (non-progressive) or if the payload was invalid
            #
            if not yield_.progress or not is_valid:
                callee_extra = invocation_request.registration.observers_extra.get(session, None)
                if callee_extra:
                    callee_extra.concurrency_current -= 1

                self._remove_invoke_request(invocation_request)

                # check for any calls queued on the registration for which an
                # invocation just returned, and hence there is likely concurrency
                # free again to actually forward calls previously queued calls
                # that were queued because no callee endpoint concurrency was free
                if self._call_store:
                    queued_call = self._call_store.get_queued_call(invocation_request.registration)
                    if queued_call:
                        invocation_sent = self._call(queued_call.session,
                                                     queued_call.call,
                                                     queued_call.registration,
                                                     queued_call.authorization,
                                                     True)
                        # only actually pop the queued call when we really were
                        # able to forward the call now
                        if invocation_sent:
                            self._call_store.pop_queued_call(invocation_request.registration)

        else:
            raise ProtocolError(u"Dealer.onYield(): YIELD received for non-pending request ID {0}".format(yield_.request))

    def processInvocationError(self, session, error):
        """
        Implements :func:`crossbar.router.interfaces.IDealer.processInvocationError`
        """
        # assert(session in self._session_to_registrations)

        if error.request in self._invocations:

            # get the invocation request tracked for the caller
            invocation_request = self._invocations[error.request]

            # correlate the received invocation error to the original call
            error.correlation = invocation_request.call.correlation

            # if concurrency is enabled on this, an error counts as
            # "an answer" so we decrement.
            callee_extra = invocation_request.registration.observers_extra.get(session, None)
            if callee_extra:
                callee_extra.concurrency_current -= 1

            if error.payload is None:
                # validate normal args/kwargs payload
                try:
                    self._router.validate('call_error', invocation_request.call.procedure, error.args, error.kwargs)
                except Exception as e:
                    reply = message.Error(message.Call.MESSAGE_TYPE,
                                          invocation_request.call.request,
                                          ApplicationError.INVALID_ARGUMENT,
                                          [u"call error from procedure '{0}' with invalid application payload: {1}".format(invocation_request.call.procedure, e)])
                else:
                    reply = message.Error(message.Call.MESSAGE_TYPE,
                                          invocation_request.call.request,
                                          error.error,
                                          args=error.args,
                                          kwargs=error.kwargs)
            else:
                reply = message.Error(message.Call.MESSAGE_TYPE,
                                      invocation_request.call.request,
                                      error.error,
                                      payload=error.payload,
                                      enc_algo=error.enc_algo,
                                      enc_key=error.enc_key,
                                      enc_serializer=error.enc_serializer)

            # the calling session might have been lost in the meantime ..
            #
            if invocation_request.caller._transport:
                reply.correlation = invocation_request.call.correlation
                self._router.send(invocation_request.caller, reply)

            # the call is done
            #
            invoke = self._invocations[error.request]
            self._remove_invoke_request(invoke)

        else:
            raise ProtocolError(u"Dealer.onInvocationError(): ERROR received for non-pending request_type {0} and request ID {1}".format(error.request_type, error.request))

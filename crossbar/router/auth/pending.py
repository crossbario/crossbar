#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import importlib
from typing import Union, Dict, Any, Optional

from txaio import make_logger
from twisted.internet.defer import Deferred

from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.types import Accept, Deny, HelloDetails, Challenge, TransportDetails
from autobahn.wamp.interfaces import ISession

from crossbar._util import hlid, hltype
from crossbar.interfaces import IRealmContainer

import txaio

__all__ = ('PendingAuth', )

_authenticators: Dict[str, object] = dict()


class PendingAuth:
    """
    Base class for pending WAMP authentications.

    After creating a pending authentication first call ``open()`` and
    then ``verify()`` (each should be called exactly once, and in this order).
    """
    log = make_logger()

    AUTHMETHOD = 'abstract'

    def __init__(self, pending_session_id: int, transport_details: TransportDetails, realm_container: IRealmContainer,
                 config: Dict[str, Any]):
        """

        :param pending_session_id: The WAMP session ID if this authentication succeeds.
        :param transport_details: Transport details of the authenticating session.
        :param realm_container: Realm container (router or proxy) for access to configured realms and roles.
        :param config: Authentication configuration to apply for the pending auth.
        """
        # Details about the authenticating session
        self._session_details = {
            'transport': transport_details.marshal(),
            'session': pending_session_id,
            'authmethod': None,
            'authextra': None
        }

        # The router factory we are working for
        self._realm_container: IRealmContainer = realm_container

        # WAMP-Ticket configuration to apply for the pending auth
        self._config: Dict[str, Any] = config

        # The realm of the authenticating principal.
        self._realm: Optional[str] = None

        # The authentication ID of the authenticating principal.
        self._authid: Optional[str] = None

        # The role under which the principal will be authenticated when
        # the authentication succeeds.
        self._authrole: Optional[str] = None

        # Optional authentication provider (URI of procedure to call).
        self._authprovider: Optional[str] = None

        # The authentication method
        self._authmethod: str = self.AUTHMETHOD

        # Application-specific extra data forwarded to the authenticating client in WELCOME
        self._authextra: Optional[Dict[str, Any]] = None

        # The URI of the authenticator procedure to call (filled only in dynamic mode).
        self._authenticator: Optional[str] = None

        # The realm the (dynamic) authenticator itself is joined to
        self._authenticator_realm: Optional[str] = None

        # The session over which to issue the call to the authenticator (filled only in dynamic mode).
        self._authenticator_session: Optional[ISession] = None

    def _assign_principal(self, principal):
        if isinstance(principal, str):
            # FIXME: more strict authrole checking
            pass
        elif isinstance(principal, dict):
            # FIXME: check principal
            pass
        else:
            error = ApplicationError.AUTHENTICATION_FAILED
            message = 'got invalid return type "{}" from dynamic authenticator'.format(type(principal))
            return Deny(error, message)

        # backwards compatibility: dynamic authenticator
        # was expected to return a role directly
        if isinstance(principal, str):
            principal = {'role': principal}

        # allow to override realm request, redirect realm or set default realm
        if 'realm' in principal:
            self._realm = principal['realm']

        # allow overriding effectively assigned authid
        if 'authid' in principal:
            self._authid = principal['authid']

        # determine effectively assigned authrole
        if 'role' in principal:
            self._authrole = principal['role']
        elif 'default-role' in self._config:
            self._authrole = self._config['default-role']

        # allow forwarding of application-specific "welcome data"
        if 'extra' in principal:
            self._authextra = principal['extra']

        # a realm must have been assigned by now, otherwise bail out!
        if not self._realm:
            return Deny(ApplicationError.NO_SUCH_REALM, message='no realm assigned')

        # an authid MUST be set at least by here - otherwise bail out now!
        if not self._authid:
            return Deny(ApplicationError.NO_SUCH_PRINCIPAL, message='no authid assigned')

        # an authrole MUST be set at least by here - otherwise bail out now!
        if not self._authrole:
            return Deny(ApplicationError.NO_SUCH_ROLE, message='no authrole assigned')

        # if realm is not started on router, bail out now!
        if not self._realm_container.has_realm(self._realm):
            return Deny(ApplicationError.NO_SUCH_REALM,
                        message='no realm "{}" exists on this router'.format(self._realm))

        # if role is not running on realm, bail out now!
        if self._authrole not in ['trusted', 'anonymous'
                                  ] and not self._realm_container.has_role(self._realm, self._authrole):
            return Deny(ApplicationError.NO_SUCH_ROLE,
                        message='realm "{}" has no role "{}"'.format(self._realm, self._authrole))

    def _init_dynamic_authenticator(self):
        # procedure URI to call
        self._authenticator = self._config['authenticator']

        # authenticator realm
        if 'authenticator-realm' in self._config:
            self._authenticator_realm = self._config['authenticator-realm']
            self.log.debug('{func} authenticator realm "{realm}" set from authenticator configuration',
                           func=hltype(self._init_function_authenticator),
                           realm=hlid(self._authenticator_realm))
        else:
            self._authenticator_realm = self._realm
            self.log.debug('{func} authenticator realm "{realm}" set from session',
                           func=hltype(self._init_function_authenticator),
                           realm=hlid(self._authenticator_realm))

        if not self._realm_container.has_realm(self._authenticator_realm):
            return Deny(ApplicationError.NO_SUCH_REALM,
                        message=("explicit realm <{}> configured for dynamic "
                                 "authenticator does not exist".format(self._authenticator_realm)))

        # authenticator role
        if 'authenticator-role' in self._config:
            self._authenticator_role = self._config['authenticator-role']
            self.log.debug('{func} authenticator role "{authrole}" set from authenticator configuration',
                           func=hltype(self._init_function_authenticator),
                           authrole=hlid(self._authenticator_role))
        else:
            self._authenticator_role = self._authrole
            self.log.debug('{func} authenticator role "{authrole}" set from session',
                           func=hltype(self._init_function_authenticator),
                           authrole=hlid(self._authenticator_role))

        if self._authenticator_realm is None:
            return Deny(
                ApplicationError.NO_SUCH_ROLE,
                message="role <{}> configured, but no realm".format(self._authenticator_role),
            )
        if not self._realm_container.has_role(self._authenticator_realm, self._authenticator_role):
            return Deny(
                ApplicationError.NO_SUCH_ROLE,
                message="explicit role <{}> on realm <{}> configured for dynamic authenticator does not exist".format(
                    self._authenticator_role, self._authenticator_realm))

        self.log.info(
            'initializing authenticator service session for realm "{realm}" with authrole "{authrole}" .. {func}',
            realm=hlid(self._authenticator_realm),
            authrole=hlid(self._authenticator_role),
            func=hltype(self._init_dynamic_authenticator))

        # get a dynamic authenticator session (where the dynamic authenticator procedure is registered and called):
        #
        #   * lives on a realm/role explicitly given
        #   * authenticates implicitly (the implementation in the router or proxy container is responsible
        #      for setting up authentication of the dynamic authenticator session client transport)
        #
        d_connected = self._realm_container.get_service_session(self._authenticator_realm, self._authenticator_role)
        d_ready = Deferred()

        def connect_success(session):
            self.log.info(
                'authenticator service session {session_id} attached to realm "{realm}" with authrole "{authrole}" {func}',
                func=hltype(self._init_dynamic_authenticator),
                session_id=hlid(session._session_id),
                authrole=hlid(session._authrole),
                realm=hlid(session._realm))
            self._authenticator_session = session
            d_ready.callback(None)

        def connect_error(err):
            self.log.failure()
            d_ready.callback(err)

        d_connected.addCallbacks(connect_success, connect_error)
        return d_ready

    def _marshal_dynamic_authenticator_error(self, err):
        if isinstance(err.value, ApplicationError):
            # forward the inner error URI and message (or coerce the first args item to str)
            msg = None
            if err.value.args:
                msg = '{}'.format(err.value.args[0])
            return Deny(err.value.error, msg)
        else:
            # wrap the error
            error = ApplicationError.AUTHENTICATION_FAILED
            message = 'dynamic authenticator failed: {}'.format(err.value)
            return Deny(error, message)

    def _accept(self):
        return Accept(realm=self._realm,
                      authid=self._authid,
                      authrole=self._authrole,
                      authmethod=self._authmethod,
                      authprovider=self._authprovider,
                      authextra=self._authextra)

    def _init_function_authenticator(self):
        self.log.debug('{klass}._init_function_authenticator', klass=self.__class__.__name__)

        # import the module for the function
        create_fqn = self._config['create']
        if '.' not in create_fqn:
            return Deny(ApplicationError.NO_SUCH_PROCEDURE,
                        "'function' authenticator has no module: '{}'".format(create_fqn))

        if self._config.get('expose_controller', None):
            from crossbar.worker.controller import WorkerController
            if not isinstance(self._realm_container, WorkerController):
                excp = Exception("Internal Error: Our container '{}' is not a WorkerController".format(
                    self._realm_container, ))
                self.log.failure('{klass} could not expose controller', klass=self.__class__.__name__, failure=excp)
                raise excp
            controller = self._realm_container
        else:
            controller = None

        create_d = txaio.as_future(_authenticator_for_name, self._config, controller=controller)

        def got_authenticator(authenticator):
            self._authenticator = authenticator

        create_d.addCallback(got_authenticator)
        return create_d

    def hello(self, realm: str, details: HelloDetails) -> Union[Accept, Deny, Challenge]:
        """
        When a HELLO message is received, this gets called to open the pending authentication.

        :param realm: The realm to client wishes to join (if the client did announce a realm).
        :param details: The details of the client provided for HELLO.
        :returns: Either return a challenge, or immediately accept or deny session.
        """
        raise NotImplementedError('{}(realm="{}", details={})'.format(hltype(self.hello), realm, details))

    def authenticate(self, signature: str) -> Union[Accept, Deny]:
        """
        The client has answered with a WAMP AUTHENTICATE message. Verify the message and accept or deny.

        :param signature: Signature over the challenge as received from the authenticating session.
        :returns: Either accept or deny the session.
        """
        raise NotImplementedError('{}(signature="{}")'.format(hltype(self.hello), signature))


def _authenticator_for_name(config, controller=None):
    """
    :returns: a future which fires with an authenticator function
        (possibly freshly created)
    """

    create_fqn = config['create']
    create_function = _authenticators.get(create_fqn, None)

    if create_function is None:
        create_module, create_name = create_fqn.rsplit('.', 1)
        _mod = importlib.import_module(create_module)
        try:
            create_authenticator = getattr(_mod, create_name)
        except AttributeError:
            raise RuntimeError("No function '{}' in module '{}'".format(create_name, create_module))
        create_d = txaio.as_future(create_authenticator, config.get('config', dict()), controller)

        def got_authenticator(authenticator):
            _authenticators[create_fqn] = authenticator
            return authenticator

        create_d.addCallback(got_authenticator)

    else:
        create_d = Deferred()
        create_d.callback(create_function)
    return create_d

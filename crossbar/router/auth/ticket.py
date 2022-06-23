#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from typing import Union, Dict, Any

from txaio import make_logger, as_future

from autobahn.wamp.types import Accept, Deny, HelloDetails, Challenge, TransportDetails

from crossbar.router.auth.pending import PendingAuth
from crossbar.interfaces import IRealmContainer, IPendingAuth

__all__ = ('PendingAuthTicket', )


class PendingAuthTicket(PendingAuth):
    """
    Pending authentication information for WAMP-Ticket authentication.
    """

    log = make_logger()

    AUTHMETHOD = 'ticket'

    def __init__(self, pending_session_id: int, transport_details: TransportDetails, realm_container: IRealmContainer,
                 config: Dict[str, Any]):
        super(PendingAuthTicket, self).__init__(
            pending_session_id,
            transport_details,
            realm_container,
            config,
        )

        # The secret/ticket the authenticating principal will need to provide (filled only in static mode).
        self._signature = None

    def hello(self, realm: str, details: HelloDetails) -> Union[Accept, Deny, Challenge]:

        # remember the realm the client requested to join (if any)
        self._realm = realm

        # remember the authid the client wants to identify as (if any)
        self._authid = details.authid

        # use static principal database from configuration
        if self._config['type'] == 'static':

            self._authprovider = 'static'

            if self._authid in self._config.get('principals', {}):

                principal = self._config['principals'][self._authid]
                principal['extra'] = details.authextra

                error = self._assign_principal(principal)
                if error:
                    return error

                # now set signature as expected for WAMP-Ticket
                self._signature = principal['ticket']

                return Challenge(self._authmethod)
            else:
                return Deny(message='no principal with authid "{}" exists'.format(self._authid))

        # use configured procedure to dynamically get a ticket for the principal
        elif self._config['type'] == 'dynamic':

            self._authprovider = 'dynamic'

            init_d = as_future(self._init_dynamic_authenticator)

            def init(_error):
                if _error:
                    return _error
                self._session_details['authmethod'] = self._authmethod  # from AUTHMETHOD, via base
                self._session_details['authextra'] = details.authextra
                return Challenge(self._authmethod)

            init_d.addBoth(init)
            return init_d

        elif self._config['type'] == 'function':

            self._authprovider = 'function'

            init_d = as_future(self._init_function_authenticator)

            def init(_error):
                if _error:
                    return _error
                self._session_details['authmethod'] = self._authmethod  # from AUTHMETHOD, via base
                self._session_details['authextra'] = details.authextra
                return Challenge(self._authmethod)

            init_d.addBoth(init)
            return init_d

        else:
            # should not arrive here, as config errors should be caught earlier
            return Deny(message='invalid authentication configuration (authentication type "{}" is unknown)'.format(
                self._config['type']))

    def authenticate(self, signature: str) -> Union[Accept, Deny]:
        def on_authenticate_ok(principal):
            # backwards compatibility: dynamic ticket authenticator
            # was expected to return a role directly
            if isinstance(principal, str):
                principal = {'role': principal}

            error = self._assign_principal(principal)
            if error:
                return error

            return self._accept()

        def on_authenticate_error(err):
            return self._marshal_dynamic_authenticator_error(err)

        # WAMP-Ticket "static"
        if self._authprovider == 'static':

            # when doing WAMP-Ticket from static configuration, the ticket we
            # expect was previously stored in self._signature
            if signature == self._signature:
                # ticket was valid: accept the client
                self.log.debug("WAMP-Ticket: ticket was valid!")
                return self._accept()
            else:
                # ticket was invalid: deny client
                self.log.debug(
                    'WAMP-Ticket (static): expected ticket "{expected}"" ({expected_type}), but got "{sig}" ({sig_type})',
                    expected=self._signature,
                    expected_type=type(self._signature),
                    sig=signature,
                    sig_type=type(signature),
                )
                return Deny(message="ticket in static WAMP-Ticket authentication is invalid")

        # WAMP-Ticket "dynamic"
        elif self._authprovider == 'dynamic':

            self._session_details['ticket'] = signature

            assert self._authenticator_session
            d = self._authenticator_session.call(self._authenticator, self._realm, self._authid, self._session_details)

            d.addCallbacks(on_authenticate_ok, on_authenticate_error)

            return d

        # WAMP-Ticket "function"
        elif self._authprovider == 'function':

            self._session_details['ticket'] = signature

            auth_d = as_future(self._authenticator, self._realm, self._authid, self._session_details)

            auth_d.addCallbacks(on_authenticate_ok, on_authenticate_error)
            return auth_d

        else:
            # should not arrive here, as config errors should be caught earlier
            return Deny(message='invalid authentication configuration (authentication type "{}" is unknown)'.format(
                self._config['type']))


IPendingAuth.register(PendingAuthTicket)

#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from typing import Dict, Any

import txaio
from txaio import make_logger

from autobahn.wamp.types import Deny, TransportDetails

from crossbar.router.auth.pending import PendingAuth
from crossbar.interfaces import IRealmContainer, IPendingAuth

__all__ = ('PendingAuthTLS', )


class PendingAuthTLS(PendingAuth):
    """
    Pending WAMP-TLS authentication.
    """

    AUTHMETHOD = 'tls'

    log = make_logger()

    def __init__(self, pending_session_id: int, transport_details: TransportDetails, realm_container: IRealmContainer,
                 config: Dict[str, Any]):
        super(PendingAuthTLS, self).__init__(
            pending_session_id,
            transport_details,
            realm_container,
            config,
        )

        # https://tools.ietf.org/html/rfc5056
        # https://tools.ietf.org/html/rfc5929
        # https://www.ietf.org/proceedings/90/slides/slides-90-uta-0.pdf
        self._channel_id = transport_details.channel_id.get('tls-unique',
                                                            None) if transport_details.channel_id else None
        self._peer_cert = transport_details.peer_cert

        # for static-mode, the config has principals as a dict indexed
        # by authid, but we need the reverse map: cert-sha1 -> principal
        self._cert_sha1_to_principal = None
        if self._config['type'] == 'static':
            self._cert_sha1_to_principal = {}
            if 'principals' in self._config:
                for authid, principal in self._config['principals'].items():
                    self._cert_sha1_to_principal[principal['certificate-sha1']] = {
                        'authid': authid,
                        'role': principal['role']
                    }

    def hello(self, realm, details):

        # we must have a client TLS certificate to continue
        if not self._peer_cert:
            return Deny(message='client did not send a TLS client certificate')

        # remember the realm the client requested to join (if any)
        self._realm = realm

        # remember the authid the client wants to identify as (if any)
        self._authid = details.authid

        # use static principal database from configuration
        if self._config['type'] == 'static':

            self._authprovider = 'static'

            client_cert_sha1 = self._peer_cert['sha1']
            if client_cert_sha1 in self._cert_sha1_to_principal:
                principal = self._cert_sha1_to_principal[client_cert_sha1]
                error = self._assign_principal(principal)
                if error:
                    return error
                return self._accept()
            else:
                return Deny(message='no principal with authid "{}" exists'.format(client_cert_sha1))

        # use configured procedure to dynamically get a ticket for the principal
        elif self._config['type'] == 'dynamic':

            self._authprovider = 'dynamic'

            init_d = txaio.as_future(self._init_dynamic_authenticator)

            def init(result):
                if result:
                    return result

                self._session_details['authmethod'] = self._authmethod  # from AUTHMETHOD, via base
                self._session_details['authextra'] = details.authextra

                d = self._authenticator_session.call(self._authenticator, realm, details.authid, self._session_details)

                def on_authenticate_ok(_principal):
                    _error = self._assign_principal(_principal)
                    if _error:
                        return _error

                    # FIXME: not sure about this .. TLS is a transport-level auth mechanism .. so forward
                    # self._transport._authid = self._authid
                    # self._transport._authrole = self._authrole
                    # self._transport._authmethod = self._authmethod
                    # self._transport._authprovider = self._authprovider
                    # self._transport._authextra = self._authextra

                    return self._accept()

                def on_authenticate_error(err):
                    return self._marshal_dynamic_authenticator_error(err)

                d.addCallbacks(on_authenticate_ok, on_authenticate_error)
                return d

            init_d.addBoth(init)
            return init_d

        else:
            # should not arrive here, as config errors should be caught earlier
            return Deny(message='invalid authentication configuration (authentication type "{}" is unknown)'.format(
                self._config['type']))

    def authenticate(self, signature):
        # should not arrive here!
        raise Exception("internal error (WAMP-TLS does not implement AUTHENTICATE)")


IPendingAuth.register(PendingAuthTLS)

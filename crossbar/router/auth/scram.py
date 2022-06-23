#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import os
import hmac
import hashlib
import base64
import binascii
from typing import Union, Dict, Any

from passlib.utils import saslprep

from txaio import make_logger, as_future

from autobahn import util
from autobahn.wamp.types import Accept, Deny, HelloDetails, Challenge, TransportDetails

from crossbar.router.auth.pending import PendingAuth
from crossbar.interfaces import IRealmContainer, IPendingAuth

__all__ = ('PendingAuthScram', )


class PendingAuthScram(PendingAuth):
    """
    Pending SCRAM authentication.
    """

    log = make_logger()

    AUTHMETHOD = 'scram'

    def __init__(self, pending_session_id: int, transport_details: TransportDetails, realm_container: IRealmContainer,
                 config: Dict[str, Any]):
        super(PendingAuthScram, self).__init__(
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

    def hello(self, realm: str, details: HelloDetails) -> Union[Accept, Deny, Challenge]:
        # the channel binding requested by the client authenticating
        # client must send "nonce" in details, and MAY send "gs2_cbind_flag"
        self._client_nonce = details.authextra.get("nonce", None)
        if self._client_nonce is None:
            return Deny(message='client must send a nonce')
        try:
            self._client_nonce = base64.b64decode(self._client_nonce)
        except Exception:
            return Deny(message='client nonce must be base64')

        # FIXME TODO: channel-binding (currently "gs2_cbind_flag" in
        # the draft spec)

        # remember the realm the client requested to join (if any)
        self._realm = realm

        # remember the authid the client wants to identify as (if any)
        # XXX should we just "saslprep()" it here?
        self._authid = details.authid

        if self._authid is None:
            return Deny(message='cannot identify client: no authid requested')
        self._session_details['authmethod'] = self._authmethod  # from AUTHMETHOD, via base
        self._session_details['authextra'] = details.authextra

        def on_authenticate_ok(principal):
            self._salt = binascii.a2b_hex(principal['salt'])  # error if no salt per-user
            self._iterations = principal['iterations']
            self._memory = principal['memory']
            self._kdf = principal['kdf']
            self._stored_key = binascii.a2b_hex(principal['stored-key'])
            # do we actually need the server-key? can we compute it ourselves?
            self._server_key = binascii.a2b_hex(principal['server-key'])
            error = self._assign_principal(principal)
            if error:
                return error

            # XXX TODO this needs to include (optional) channel-binding
            extra = self._compute_challenge()
            return Challenge(self._authmethod, extra)

        def on_authenticate_error(err):
            return self._marshal_dynamic_authenticator_error(err)

        # use static principal database from configuration
        if self._config['type'] == 'static':
            self._authprovider = 'static'

            if self._authid in self._config.get('principals', {}):
                # we've already validated the configuration
                return on_authenticate_ok(self._config['principals'][self._authid])
            else:
                self.log.debug("No pricipal found for {authid}", authid=details.authid)
                return Deny(message='no principal with authid "{}" exists'.format(details.authid))

        elif self._config['type'] == 'dynamic':
            self._authprovider = 'dynamic'

            init_d = as_future(self._init_dynamic_authenticator)

            def init(error):
                if error:
                    return error

                # now call (via WAMP) the user provided authenticator (WAMP RPC endpoint)
                d = self._authenticator_session.call(self._authenticator, realm, details.authid, self._session_details)
                d.addCallbacks(on_authenticate_ok, on_authenticate_error)
                return d

            init_d.addBoth(init)
            return init_d

        elif self._config['type'] == 'function':
            self._authprovider = 'function'

            init_d = as_future(self._init_function_authenticator)

            def init(error):
                if error:
                    return error

                # now call (via direct Python function call) the user provided authenticator (Python function)
                auth_d = as_future(self._authenticator, realm, details.authid, self._session_details)
                auth_d.addCallbacks(on_authenticate_ok, on_authenticate_error)
                return auth_d

            init_d.addBoth(init)
            return init_d

        else:
            # should not arrive here, as config errors should be caught earlier
            return Deny(message='invalid authentication configuration (authentication type "{}" is unknown)'.format(
                self._config['type']))

    # XXX TODO this needs to include (optional) channel-binding
    def _compute_challenge(self):
        self._server_nonce = self._client_nonce + os.urandom(16)

        challenge = {
            "nonce": base64.b64encode(self._server_nonce).decode('ascii'),
            "kdf": self._kdf,
            "salt": base64.b64encode(self._salt).decode('ascii'),
            "iterations": self._iterations,
            "memory": self._memory,
        }
        return challenge

    def authenticate(self, signature: str) -> Union[Accept, Deny]:
        """
        Verify the signed message sent by the client.

        :param signature: the base64-encoded result "ClientProof"
            from the SCRAM protocol
        """

        channel_binding = ""
        client_nonce = base64.b64encode(self._client_nonce).decode('ascii')
        server_nonce = base64.b64encode(self._server_nonce).decode('ascii')
        salt = base64.b64encode(self._salt).decode('ascii')
        auth_message = ("{client_first_bare},{server_first},{client_final_no_proof}".format(
            client_first_bare="n={},r={}".format(saslprep(self._authid), client_nonce),
            server_first="r={},s={},i={}".format(server_nonce, salt, self._iterations),
            client_final_no_proof="c={},r={}".format(channel_binding, server_nonce),
        ))

        received_client_proof = base64.b64decode(signature)

        client_signature = hmac.new(self._stored_key, auth_message.encode('ascii'), hashlib.sha256).digest()
        recovered_client_key = util.xor(client_signature, received_client_proof)
        recovered_stored_key = hashlib.new('sha256', recovered_client_key).digest()

        # if we adjust self._authextra before _accept() it gets sent
        # back to the client
        server_signature = hmac.new(self._server_key, auth_message.encode('ascii'), hashlib.sha256).digest()
        if self._authextra is None:
            self._authextra = {}
        self._authextra['scram_server_signature'] = base64.b64encode(server_signature).decode('ascii')

        if hmac.compare_digest(recovered_stored_key, self._stored_key):
            return self._accept()

        self.log.error("SCRAM authentication failed for '{authid}'", authid=self._authid)
        return Deny(message='SCRAM authentication failed')


IPendingAuth.register(PendingAuthScram)

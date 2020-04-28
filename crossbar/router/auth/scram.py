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

import os
import hmac
import hashlib
import base64
import binascii

from autobahn import util
from autobahn.wamp import types

from passlib.utils import saslprep

from txaio import make_logger, as_future

from crossbar.router.auth.pending import PendingAuth

__all__ = ('PendingAuthScram',)


class PendingAuthScram(PendingAuth):
    """
    Pending SCRAM authentication.
    """

    log = make_logger()

    AUTHMETHOD = 'scram'

    def __init__(self, pending_session_id, transport_info, realm_container, config):
        super(PendingAuthScram, self).__init__(
            pending_session_id, transport_info, realm_container, config,
        )

        # https://tools.ietf.org/html/rfc5056
        # https://tools.ietf.org/html/rfc5929
        # https://www.ietf.org/proceedings/90/slides/slides-90-uta-0.pdf
        channel_id_hex = transport_info.get('channel_id', None)
        if channel_id_hex:
            self._channel_id = binascii.a2b_hex(channel_id_hex)
        else:
            self._channel_id = None

    def hello(self, realm, details):
        # the channel binding requested by the client authenticating
        # client must send "nonce" in details, and MAY send "gs2_cbind_flag"
        self._client_nonce = details.authextra.get("nonce", None)
        if self._client_nonce is None:
            return types.Deny(
                message='client must send a nonce'
            )
        try:
            self._client_nonce = base64.b64decode(self._client_nonce)
        except Exception:
            return types.Deny(
                message='client nonce must be base64'
            )

        # FIXME TODO: channel-binding (currently "gs2_cbind_flag" in
        # the draft spec)

        # remember the realm the client requested to join (if any)
        self._realm = realm

        # remember the authid the client wants to identify as (if any)
        # XXX should we just "saslprep()" it here?
        self._authid = details.authid

        if self._authid is None:
            return types.Deny(message='cannot identify client: no authid requested')
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
            return types.Challenge(self._authmethod, extra)

        # use static principal database from configuration
        if self._config['type'] == 'static':

            self._authprovider = 'static'

            if self._authid in self._config.get('principals', {}):
                # we've already validated the configuration
                return on_authenticate_ok(self._config['principals'][self._authid])
            else:
                self.log.debug("No pricipal found for {authid}", authid=details.authid)
                return types.Deny(
                    message='no principal with authid "{}" exists'.format(details.authid)
                )

        elif self._config['type'] == 'dynamic':

            init_d = as_future(self._init_dynamic_authenticator)

            def init(error):
                if error:
                    return error

                d = self._authenticator_session.call(self._authenticator, realm, details.authid, self._session_details)

                def on_authenticate_error(err):
                    return self._marshal_dynamic_authenticator_error(err)

                d.addCallbacks(on_authenticate_ok, on_authenticate_error)

                return d
            init_d.addBoth(init)
            return init_d

        else:
            # should not arrive here, as config errors should be caught earlier
            return types.Deny(message='invalid authentication configuration (authentication type "{}" is unknown)'.format(self._config['type']))

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

    def authenticate(self, signed_message):
        """
        Verify the signed message sent by the client.

        :param signed_message: the base64-encoded result "ClientProof"
            from the SCRAM protocol
        """

        channel_binding = ""
        client_nonce = base64.b64encode(self._client_nonce).decode('ascii')
        server_nonce = base64.b64encode(self._server_nonce).decode('ascii')
        salt = base64.b64encode(self._salt).decode('ascii')
        auth_message = (
            "{client_first_bare},{server_first},{client_final_no_proof}".format(
                client_first_bare="n={},r={}".format(saslprep(self._authid), client_nonce),
                server_first="r={},s={},i={}".format(server_nonce, salt, self._iterations),
                client_final_no_proof="c={},r={}".format(channel_binding, server_nonce),
            )
        )

        received_client_proof = base64.b64decode(signed_message)

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
        return types.Deny(message='SCRAM authentication failed')

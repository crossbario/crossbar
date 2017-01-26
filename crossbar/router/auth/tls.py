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

from autobahn.wamp import types

from crossbar.router.auth.pending import PendingAuth

__all__ = ('PendingAuthTLS',)


class PendingAuthTLS(PendingAuth):
    """
    Pending WAMP-TLS authentication.
    """

    AUTHMETHOD = u'tls'

    def __init__(self, session, config):
        PendingAuth.__init__(self, session, config)

        self._transport = session._transport

        # for static-mode, the config has principals as a dict indexed
        # by authid, but we need the reverse map: cert-sha1 -> principal
        self._cert_sha1_to_principal = None
        if self._config[u'type'] == u'static':
            self._cert_sha1_to_principal = {}
            if u'principals' in self._config:
                for authid, principal in self._config[u'principals'].items():
                    self._cert_sha1_to_principal[principal[u'certificate-sha1']] = {
                        u'authid': authid,
                        u'role': principal[u'role']
                    }

    def hello(self, realm, details):

        # remember the realm the client requested to join (if any)
        self._realm = realm

        # remember the authid the client wants to identify as (if any)
        self._authid = details.authid

        # use static principal database from configuration
        if self._config[u'type'] == u'static':

            self._authprovider = u'static'

            client_cert = self._session_details[u'transport'].get(u'client_cert', None)
            if not client_cert:
                return types.Deny(message=u'client did not send a TLS client certificate')
            client_cert_sha1 = client_cert[u'sha1']

            if client_cert_sha1 in self._cert_sha1_to_principal:

                principal = self._cert_sha1_to_principal[client_cert_sha1]

                error = self._assign_principal(principal)
                if error:
                    return error

                return self._accept()
            else:
                return types.Deny(message=u'no principal with authid "{}" exists'.format(client_cert_sha1))

            raise Exception("not implemented")

        # use configured procedure to dynamically get a ticket for the principal
        elif self._config[u'type'] == u'dynamic':

            self._authprovider = u'dynamic'

            error = self._init_dynamic_authenticator()
            if error:
                return error

            self._session_details[u'authmethod'] = self._authmethod  # from AUTHMETHOD, via base
            self._session_details[u'authextra'] = details.authextra

            d = self._authenticator_session.call(self._authenticator, realm, details.authid, self._session_details)

            def on_authenticate_ok(principal):
                error = self._assign_principal(principal)
                if error:
                    return error

                # FIXME: not sure about this .. TLS is a transport-level auth mechanism .. so forward
                self._transport._authid = self._authid
                self._transport._authrole = self._authrole
                self._transport._authmethod = self._authmethod
                self._transport._authprovider = self._authprovider
                self._transport._authextra = self._authextra

                return self._accept()

            def on_authenticate_error(err):
                return self._marshal_dynamic_authenticator_error(err)

            d.addCallbacks(on_authenticate_ok, on_authenticate_error)
            return d

        else:
            # should not arrive here, as config errors should be caught earlier
            return types.Deny(message=u'invalid authentication configuration (authentication type "{}" is unknown)'.format(self._config['type']))

    def authenticate(self, signature):
        # should not arrive here!
        raise Exception("internal error (WAMP-TLS does not implement AUTHENTICATE)")

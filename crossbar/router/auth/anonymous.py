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

from autobahn import util
from autobahn.wamp import types

from txaio import make_logger, as_future

from crossbar.router.auth.pending import PendingAuth
from crossbar._util import hlid, hltype

__all__ = ('PendingAuthAnonymous',)


class PendingAuthAnonymous(PendingAuth):

    """
    Pending authentication information for WAMP-Anonymous authentication.
    """

    log = make_logger()

    AUTHMETHOD = 'anonymous'

    def hello(self, realm: str, details: types.SessionDetails):
        self.log.info('{func}(realm={realm}, details.realm={authrealm}, details.authid={authid}, details.authrole={authrole}) [config={config}]',
                      func=hltype(self.hello), realm=hlid(realm), authrealm=hlid(details.realm),
                      authid=hlid(details.authid), authrole=hlid(details.authrole), config=self._config)

        # remember the realm the client requested to join (if any)
        self._realm = realm

        self._authid = self._config.get('authid', util.generate_serial_number())

        self._session_details['authmethod'] = 'anonymous'
        self._session_details['authextra'] = details.authextra

        # WAMP-anonymous "static"
        if self._config['type'] == 'static':

            self._authprovider = 'static'

            # FIXME: if cookie tracking is enabled, set authid to cookie value
            # self._authid = self._transport._cbtid

            principal = {
                'realm': realm,
                'authid': self._authid,
                'role': self._config.get('role', 'anonymous'),
                'extra': details.authextra
            }

            error = self._assign_principal(principal)
            if error:
                return error

            return self._accept()

        # WAMP-Ticket "dynamic"
        elif self._config['type'] == 'dynamic':

            self._authprovider = 'dynamic'

            init_d = as_future(self._init_dynamic_authenticator)

            def init(result):
                if result:
                    return result

                d = self._authenticator_session.call(self._authenticator, self._realm, self._authid, self._session_details)

                def on_authenticate_ok(principal):
                    error = self._assign_principal(principal)
                    if error:
                        return error

                    return self._accept()

                def on_authenticate_error(err):
                    return self._marshal_dynamic_authenticator_error(err)

                d.addCallbacks(on_authenticate_ok, on_authenticate_error)

                return d
            init_d.addBoth(init)
            return init_d

        else:
            # should not arrive here, as config errors should be caught earlier
            return types.Deny(message='invalid authentication configuration (authentication type "{}" is unknown)'.format(self._config['type']))


class PendingAuthAnonymousProxy(PendingAuthAnonymous):
    """
    Pending Anonymous authentication with additions for proxy
    """

    log = make_logger()
    AUTHMETHOD = 'anonymous-proxy'

    def hello(self, realm, details):
        self.log.info('{klass}.hello(realm={realm}, details={details}) ...',
                      klass=self.__class__.__name__, realm=realm, details=details)
        extra = details.authextra or {}

        for attr in ['proxy_authid', 'proxy_authrole', 'proxy_realm']:
            if attr not in extra:
                return types.Deny(message='missing required attribute {}'.format(attr))

        realm = extra['proxy_realm']
        details.authid = extra['proxy_authid']
        details.authrole = extra['proxy_authrole']
        details.authextra = extra.get('proxy_authextra', None)

        self.log.info('{klass}.hello(realm={realm}, details={details}) -> realm={realm}, authid={authid}, authrole={authrole}, authextra={authextra}',
                      klass=self.__class__.__name__, realm=realm, details=details, authid=details.authid,
                      authrole=details.authrole, authextra=details.authextra)

        # remember the realm the client requested to join (if any)
        self._realm = realm
        self._authid = details.authid
        self._session_details['authmethod'] = 'anonymous'
        self._session_details['authextra'] = details.authextra
        self._authprovider = 'static'

        # FIXME: if cookie tracking is enabled, set authid to cookie value
        # self._authid = self._transport._cbtid

        principal = {
            'realm': realm,
            'authid': details.authid,
            'role': details.authrole,
            'extra': details.authextra
        }

        error = self._assign_principal(principal)
        if error:
            return error

        return self._accept()

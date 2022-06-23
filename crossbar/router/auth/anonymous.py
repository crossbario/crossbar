#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from typing import Union
from txaio import make_logger, as_future

from autobahn import util
from autobahn.wamp.types import Accept, Deny, HelloDetails, Challenge

from crossbar.router.auth.pending import PendingAuth
from crossbar._util import hlid, hltype, hlval

__all__ = (
    'PendingAuthAnonymous',
    'PendingAuthAnonymousProxy',
)


class PendingAuthAnonymous(PendingAuth):
    """
    Pending authentication information for WAMP-Anonymous authentication.
    """

    log = make_logger()

    AUTHMETHOD = 'anonymous'

    def hello(self, realm: str, details: HelloDetails) -> Union[Accept, Deny, Challenge]:
        self.log.info(
            '{func}(realm={realm}, details.realm={authrealm}, details.authid={authid}, details.authrole={authrole}) [config={config}]',
            func=hltype(self.hello),
            realm=hlid(realm),
            authrealm=hlid(details.realm),
            authid=hlid(details.authid),
            authrole=hlid(details.authrole),
            config=self._config)

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

                d = self._authenticator_session.call(self._authenticator, self._realm, self._authid,
                                                     self._session_details)

                def on_authenticate_ok(_principal):
                    _error = self._assign_principal(_principal)
                    if _error:
                        return _error

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


class PendingAuthAnonymousProxy(PendingAuthAnonymous):
    """
    Pending Anonymous authentication with additions for proxy
    """

    log = make_logger()
    AUTHMETHOD = 'anonymous-proxy'

    def hello(self, realm, details):
        self.log.debug('{func}(realm="{realm}", details={details})',
                       func=hltype(self.hello),
                       realm=hlval(realm),
                       details=details)
        extra = details.authextra or {}

        for attr in ['proxy_authid', 'proxy_authrole', 'proxy_realm']:
            if attr not in extra:
                return Deny(message='missing required attribute {}'.format(attr))

        realm = extra['proxy_realm']
        details.authid = extra['proxy_authid']
        details.authrole = extra['proxy_authrole']
        details.authextra = extra.get('proxy_authextra', None)

        # remember the realm the client requested to join (if any)
        self._realm = realm
        self._authid = details.authid
        self._authrole = details.authrole
        self._session_details['authmethod'] = self.AUTHMETHOD
        self._session_details['authextra'] = details.authextra
        self._authprovider = 'static'

        # FIXME: if cookie tracking is enabled, set authid to cookie value
        # self._authid = self._transport._cbtid

        principal = {'realm': realm, 'authid': details.authid, 'role': details.authrole, 'extra': details.authextra}

        error = self._assign_principal(principal)
        if error:
            return error

        return self._accept()

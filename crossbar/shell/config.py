###############################################################################
#
# Crossbar.io Shell
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

import os
from six.moves import configparser

# pair a node from a node public key from a local file:
#
# cbf pair node --realm "myrealm" --node "mynode" /var/local/crossbar/.crossbar/key.pub

# pair a node from a node public key served from a HTTP URL:
#
# cbf pair node --realm "myrealm" --node "mynode" http://localhost:9140/key.pub

from txaio import make_logger


class Profile(object):

    log = make_logger()

    def __init__(self,
                 name=None,
                 url=None,
                 reconnect=None,
                 debug=None,
                 realm=None,
                 role=None,
                 pubkey=None,
                 privkey=None,
                 tls_hostname=None,
                 tls_certificates=None):
        self.name = name
        self.url = url
        self.reconnect = reconnect
        self.debug = debug
        self.realm = realm
        self.role = role
        self.pubkey = pubkey
        self.privkey = privkey
        self.tls_hostname = tls_hostname
        self.tls_certificates = tls_certificates

    def __str__(self):
        return u'Profile(name={}, url={}, reconnect={}, debug={}, realm={}, role={}, pubkey={}, privkey={}, tls_hostname={}, tls_certificates={})'.format(
            self.name, self.url, self.reconnect, self.debug, self.realm, self.role, self.pubkey, self.privkey,
            self.tls_hostname, self.tls_certificates)

    @staticmethod
    def parse(name, items):
        url = None
        reconnect = None
        debug = None
        realm = None
        role = None
        pubkey = None
        privkey = None
        tls_hostname = None
        tls_certificates = None
        for k, v in items:
            if k == 'url':
                url = str(v)
            elif k == 'reconnect':
                reconnect = int(v)
            elif k == 'debug':
                debug = bool(v)
            elif k == 'realm':
                realm = str(v)
            elif k == 'role':
                role = str(v)
            elif k == 'pubkey':
                pubkey = str(v)
            elif k == 'privkey':
                privkey = str(v)
            elif k == 'tls_hostname':
                tls_hostname = str(v)
            elif k == 'tls_certificates':
                tls_certificates = [x.strip() for x in str(v).split(',')]
            else:
                # skip unknown attribute
                Profile.log.warn('unprocessed config attribute "{}"'.format(k))

        return Profile(name, url, reconnect, debug, realm, role, pubkey, privkey, tls_hostname, tls_certificates)


class UserConfig(object):

    log = make_logger()

    def __init__(self, config_path):
        self._config_path = os.path.abspath(config_path)

        config = configparser.ConfigParser()
        config.read(config_path)

        self.config = config

        profiles = {}
        for profile_name in config.sections():
            profile = Profile.parse(profile_name, config.items(profile_name))
            profiles[profile_name] = profile
            self.log.info('Profile "{profile_name}" parsed: {profile}', profile_name=profile_name, profile=profile)

        self.profiles = profiles

        self.log.info('Profiles loaded for: {profiles}', profiles=sorted(self.profiles.keys()))

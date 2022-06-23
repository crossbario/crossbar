# coding=utf8

##############################################################################
#
#                        Crossbar.io
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.uri import error


@error('xbr.network.error.username_already_exists')
class UsernameAlreadyExists(ApplicationError):
    """
    An action could not be performed because the chosen username already exists.
    """
    def __init__(self, username, alt_username=None):
        if alt_username:
            msg = 'username "{}" already exists. alternative available username "{}"'.format(username, alt_username)
        else:
            msg = 'username "{}" already exists'.format(username)
        super().__init__('xbr.network.error.username_already_exists', msg, alt_username=alt_username)

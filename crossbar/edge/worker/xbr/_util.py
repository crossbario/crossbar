##############################################################################
#
#                        Crossbar.io
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################
import six

from crossbar._util import hl


def hlval(val):
    return hl('{}'.format(val), color='white', bold=True)


def hlcontract(oid):
    if not isinstance(oid, six.text_type):
        oid = '{}'.format(oid)
    return hl('<{}>'.format(oid), color='magenta', bold=True)

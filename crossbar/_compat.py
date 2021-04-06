#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################


def native_string(string):
    """
    Make C{string} be the type of C{str}, decoding with ASCII if required.
    """
    if isinstance(string, bytes):
        return string.decode('ascii')
    else:
        raise ValueError("This is already a native string.")

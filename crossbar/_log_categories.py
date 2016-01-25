#####################################################################################
#
#  Copyright (C) Tavendo GmbH
#
#  Unless a separate license agreement exists between you and Tavendo GmbH (e.g. you
#  have purchased a commercial license), the license terms below apply.
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

from __future__ import absolute_import, division, print_function

# The log categories
log_categories = {

    # CBXXX - Generic Crossbar logs
    "CB500": "Unhandled exception in Crossbar.",

    # ARXXX - Adapter, REST Bridge
    "AR100": "REST bridge request recieved.",
    "AR200": "REST bridge publish succeeded.",
    "AR201": "REST bridge webhook event succeeded.",
    "AR202": "REST bridge call succeeded.",
    "AR203": "REST bridge signature valid.",
    "AR400": "Malformed request to the REST bridge.",
    "AR405": "Method not accepted by the REST bridge.",
    "AR413": "Request too long.",
    "AR450": "Non-accepted request encoding.",
    "AR451": "Non-decodable request body.",
    "AR452": "Non-accepted content type.",
    "AR453": "Request body was invalid JSON.",
    "AR454": "Request body was valid JSON, but not well formed (incorrect type).",
    "AR455": "Request body was valid JSON, but not well formed (missing key).",
    "AR456": "REST bridge publish failed.",
    "AR457": "REST bridge webhook request failed.",
    "AR458": "REST bridge call failed.",
    "AR459": "REST bridge signature secret not valid.",
    "AR460": "REST bridge signature key not valid.",
    "AR461": "REST bridge signature was invalid (missing mandatory fields).",
    "AR462": "REST bridge signature was invalid (invalid field content).",
    "AR463": "Multiple headers not allowed.",
}


log_keys = log_categories.keys()

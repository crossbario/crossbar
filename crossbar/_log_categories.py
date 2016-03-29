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

    "DBG100": "DEBUG {x} {y} {z}",

    # CBXXX - Generic Crossbar logs
    "CB500": "Unhandled exception in Crossbar.",
    "CB501": "Unhandled exception in Crossbar: {exc}",

    # ARXXX - Adapter, REST Bridge
    "AR100": "REST bridge request recieved. (path='{path}', method={method})",
    "AR200": "REST bridge publish succeeded. ({code}, {reason})",
    "AR201": "REST bridge webhook event succeeded.",
    "AR202": "REST bridge call succeeded.",
    "AR203": "REST bridge signature valid.",
    "AR400": "Malformed request to the REST bridge.",
    "AR405": "Method not accepted by the REST bridge. ({method} not allowed, only {allowed})",
    "AR413": "Request too long. ({length} is longer than accepted {accepted})",
    "AR450": "Non-accepted request encoding, must be UTF-8.",
    "AR451": "Non-decodable request body, was not UTF-8.",
    "AR452": "Non-accepted content type. (must be one of '{accepted}', not '{given}')",
    "AR453": "Request body was invalid JSON.",
    "AR454": "Request body was valid JSON, but not well formed (must be a dict).",
    "AR455": "Request body was valid JSON, but not well formed (missing key -- '{key}).",
    "AR456": "REST bridge publish failed.",
    "AR457": "REST bridge webhook request failed.",
    "AR458": "REST bridge call failed: {exc}",
    "AR459": "REST bridge signature secret not valid.",
    "AR460": "REST bridge signature key not valid.",
    "AR461": "REST bridge signature was invalid (missing mandatory field - {reason}).",
    "AR462": "REST bridge signature was invalid ({reason}).",
    "AR463": "Multiple versions of the same header is not allowed.",
    "AR464": "Request expired, too old timestamp.",
    "AR465": "Body length ({bodylen}) is different to Content-Length header ({conlen}).",
    "AR466": "Request denied based on IP address.",
}


log_keys = log_categories.keys()

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

from __future__ import absolute_import, division

import inspect
import json


def class_name(obj):
    """
    This returns a name like "module.Class" given either an instance, or a class.
    """

    if inspect.isclass(obj):
        cls = obj
    else:
        cls = obj.__class__
    return '{}.{}'.format(cls.__module__, cls.__name__)


def dump_json(obj, minified=True):
    """
    Dump JSON to a string, either pretty printed or not. Returns a Unicode
    string.
    """
    if minified:
        return json.dumps(obj, separators=(',', ':'), ensure_ascii=False)

    else:
        return json.dumps(obj, indent=4, separators=(',', ': '),
                          sort_keys=True, ensure_ascii=False)

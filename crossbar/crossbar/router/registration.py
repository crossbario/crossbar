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

from __future__ import absolute_import

__all__ = ('RegistrationMap',)


class RegistrationMap(object):
    """
    A registration map is mapping procedure URIs to registrations.
    A registrations holds callee sessions that implement procedures.

    With PubSub, all subscribers on a subscription are notified (modulo
        subscriber black-/whitelisting).

    With RPC, normally the only is a single callee on a registration.
    However, there might be more complex policies:

     - default
     - first
     - round-robin
     - random

     - all-gather
     - all-progressive
     - shard

     Q: Implement sharded-calls via normal registrations, where the
     inviduals endpoints that process a certain shard use URIs like

     com.myapp.customer.s1.place_order
     com.myapp.customer.s2.place_order
     com.myapp.customer.s3.place_order
     com.myapp.customer.s4.place_order

     But: we want the caller be able to simply call

     com.myapp.product.order

     and not be exposed to the current number of shards.

     What about:

     com.myapp.customer.7632432.place_order

     Would require range-based subscriptions, like

     Callee 1: com.myapp.customer.[0   -1000].place_order
     Callee 2: com.myapp.customer.[1001-2000].place_order
     ...

     - under the "default" policy, there can be only one callee registered anyway

     - under a "first callee" policy, multiple callees may registere
       for the same procedure / bet attached to the same registration:
        a primary callee that handles all invocations, unless it dies,
       and a fallback callee takes over invocations.
       this essentially is a "first callee" policy, where first is
       defined by order of registration

     - a "random callee" policy, where a single, randomly chosen callee
       gets forwarded the invocation

     - a "round-robin" policy, where one after another callee gets forwarded
       invocations (in a strict ordering)

    With all of above, a given single call is will still result
    in a single invocation and a single result. It is just the selection
    of a specific callee that is under a dynamic policy.


     - a "all" policy, where all callees get forwarded invocations
       for a single call (with exactly the same arguments) and results
       are processed according

    """

    def __init__(self):
        pass

    def match_registrations(self, procedure):
        return []

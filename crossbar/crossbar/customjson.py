###############################################################################
##
##  Copyright (C) 2011-2013 Tavendo GmbH
##
##  This program is free software: you can redistribute it and/or modify
##  it under the terms of the GNU Affero General Public License, version 3,
##  as published by the Free Software Foundation.
##
##  This program is distributed in the hope that it will be useful,
##  but WITHOUT ANY WARRANTY; without even the implied warranty of
##  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
##  GNU Affero General Public License for more details.
##
##  You should have received a copy of the GNU Affero General Public License
##  along with this program. If not, see <http://www.gnu.org/licenses/>.
##
###############################################################################


import datetime, isodate
from json import JSONEncoder


class CustomJsonEncoder(JSONEncoder):
   """
   JSON encoder able to serialize Python datetime.datetime/date/time/timedelta objects.

   To use this class, do

      json.dumps(obj, cls = CustomJsonEncoder)

   See: http://docs.python.org/library/json.html#json.JSONEncoder
   """

   def default(self, obj):

      if isinstance(obj, datetime.date) or \
         isinstance(obj, datetime.datetime) or \
         isinstance(obj, datetime.time):
         ## Note this issue with isodate module: "time formating does not allow
         ## to create fractional representations".
         ## Hence we use standard Python isoformat()
         ##
         s = obj.isoformat()
         if hasattr(obj, 'tzinfo') and obj.tzinfo is None and s[-1] != 'Z':
            ## assume UTC and append 'Z' for ISO format compliance!
            return s + 'Z'
         else:
            return s

      elif isinstance(obj, datetime.timedelta):
         #return (datetime.datetime.min + obj).time().isoformat()
         return isodate.duration_isoformat(obj)

      else:
         return super(CustomJsonEncoder, self).default(obj)

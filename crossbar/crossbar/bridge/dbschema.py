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


from autobahn.wamp import json_loads


def getSchemaVersion(conn, latestVersions):

      info = {'schema-category': None,
              'schema-version': None,
              'schema-created': None,
              'schema-latest-version': None}

      cur = conn.cursor()
      try:
         cur.execute("SELECT key, value FROM config WHERE key IN ('schema-category', 'schema-version', 'schema-created')")
         for row in cur.fetchall():
            info[row[0]] = json_loads(row[1]) if row[1] is not None else None
      except:
         pass

      if info.has_key('schema-category'):
         if latestVersions.has_key(info['schema-category']):
            info['schema-latest-version'] = latestVersions[info['schema-category']]

      if info['schema-version'] is not None:
         info['schema-needs-upgrade'] = info['schema-version'] < info['schema-latest-version']
      else:
         info['schema-needs-upgrade'] = False

      return info

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


URI_BASE = "http://crossbar.io/"

URI_ERROR = URI_BASE + "error#"
URI_API = URI_BASE + "api#"
URI_EVENT = URI_BASE + "event#"
URI_WIRETAP_EVENT = URI_BASE + "event/wiretap#"

## remoting technical error
URI_ERROR_REMOTING = URI_BASE + "error#remoting"

## SQL error
URI_ERROR_SQL = URI_BASE + "error#sql"

URI_APPCRED = URI_BASE + "object/appcred/"

URI_HANACONNECT = URI_BASE + "object/hanaconnect/"
URI_HANAPUSHRULE = URI_BASE + "object/hanapushrule/"
URI_HANAREMOTE = URI_BASE + "object/hanaremote/"

URI_PGCONNECT = URI_BASE + "object/pgconnect/"
URI_PGPUSHRULE = URI_BASE + "object/pgpushrule/"
URI_PGREMOTE = URI_BASE + "object/pgremote/"

URI_ORACONNECT = URI_BASE + "object/oraconnect/"
URI_ORAPUSHRULE = URI_BASE + "object/orapushrule/"
URI_ORAREMOTE = URI_BASE + "object/oraremote/"

URI_POSTRULE = URI_BASE + "object/postrule/"
URI_SERVICEKEY = URI_BASE + "object/servicekey/"
URI_CLIENTPERM = URI_BASE + "object/clientperm/"
URI_EXTDIRECTREMOTE = URI_BASE + "object/extdirectremote/"
URI_RESTREMOTE = URI_BASE + "object/restremote/"
URI_FTPUSER = URI_BASE + "object/ftpuser/"

URI_MAXLEN = 2000

URI_WAMP_BASE = "http://api.wamp.ws/"
URI_WAMP_ERROR = URI_WAMP_BASE + "error#"
URI_WAMP_RPC = URI_WAMP_BASE + "procedure#"
URI_WAMP_EVENT = URI_WAMP_BASE + "event#"

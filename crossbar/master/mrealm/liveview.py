###############################################################################
#
# Crossbar.io Master
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from txaio import make_logger
from autobahn.wamp.types import PublishOptions


class LiveView(object):
    """
    Live representation of full system state, that is the state of all nodes
    and resources on those nodes associated with this domain (instance of CFC).
    """
    log = make_logger()

    _PUBOPTS = PublishOptions(acknowledge=True)

    def __init__(self, session, db, schema):
        """

        :param session: Management realm controller session.
        :type session: :class:`crossbar.master.controller.MrealmController`

        :param db: Management realm database.
        :type db: :class:`zlmdb.Database`

        :param schema: Management realms database schema.
        :type schema: :class:`cfxdb.mrealmschema.MrealmSchema`
        """
        self._session = session
        self._prefix = None
        self.db = db
        self.schema = schema

    def register(self, session, prefix, options):
        """

        :param session:
        :param prefix:
        :param options:
        :return:
        """
        self._prefix = prefix
        return session.register(self, prefix=prefix, options=options)

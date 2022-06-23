###############################################################################
#
# Crossbar.io Master
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

import uuid
from pprint import pformat

import txaio

txaio.use_twisted()
from txaio import sleep, time_ns
from twisted.internet.defer import inlineCallbacks

from autobahn import wamp
from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.types import RegisterOptions

from crossbar._util import hl, hlid, hltype

# FIXME:
META_DOC_OTYPE_TO_SLOT = None

# from cfxdb._mrealm import META_DOC_OTYPE_TO_SLOT


class ObjectModified(Exception):
    """
    Thrown when an object is to be updated, but was modified in the meantime.

    This is detected by matching the "modified" attribute, which is a timestamp
    of type integer with ns since Posix epoch (1970/1/1 UTC)
    """


class Documentation(object):
    """
    FIXME.
    """
    def __init__(self):
        pass

    def marshal(self):
        return None


class MetadataManager(object):
    """
    The Metadata Manager manages metadata on arbitrary other objects in
    the management realm database.

    For example, it allows to attach Tags to Node, WebCluster or WebService
    objects.

    The metadata services exposed include:

        - Tags
        - Documentation
        - Comments
    """
    log = None

    otype_to_slot = {
        'docs': META_DOC_OTYPE_TO_SLOT,
    }

    def __init__(self, session, db, schema):
        """

        :param session: Backend of user created management realms.
        :type session: :class:`crossbar.master.mrealm.controller.MrealmController`

        :param globaldb: Global database handle.
        :type globaldb: :class:`zlmdb.Database`

        :param globalschema: Global database schema.
        :type globalschema: :class:`cfxdb.globalschema.GlobalSchema`

        :param db: Management realm database handle.
        :type db: :class:`zlmdb.Database`

        :param schema: Management realm database schema.
        :type schema: :class:`cfxdb.mrealmschema.MrealmSchema`
        """
        self._session = session
        self.log = session.log

        # will be set in session.register
        self._prefix = None

        # the management realm OID this metadata manager operates for
        self._mrealm_oid = session._mrealm_oid

        # database handles/schemata
        self.db = db
        self.schema = schema

        self._started = None

    @inlineCallbacks
    def start(self, prefix):
        """
        Start the Metadata manager.

        :return:
        """
        assert self._started is None, 'cannot start Metadata manager - already running!'

        regs = yield self._session.register(self, prefix=prefix, options=RegisterOptions(details_arg='details'))
        self._prefix = prefix
        procs = [reg.procedure for reg in regs]
        self.log.debug('Mrealm controller {api} registered management procedures [{func}]:\n\n{procs}\n',
                       api=hl('Metadata manager API', color='green', bold=True),
                       func=hltype(self.start),
                       procs=hl(pformat(procs), color='white', bold=True))

        self._started = time_ns()
        self.log.info('Metadata manager ready for management realm {mrealm_oid}! [{func}]',
                      mrealm_oid=hlid(self._mrealm_oid),
                      func=hltype(self.start))

    @inlineCallbacks
    def stop(self):
        """
        Stop the (currently running) Web-cluster manager.

        :return:
        """
        assert self._started > 0, 'cannot stop Metadata manager - currently not running!'
        yield sleep(0)
        self._started = None

    @wamp.register(None)
    def get_docs(self, otype, oid, details=None):
        """

        :param otype: Type of object to return documentation for.
        :type otype: str

        :param oid: OID of the object to return documentation for.

        :param details:

        :return: Documentation object,
        """
        assert type(otype) == str
        assert otype in MetadataManager.otype_to_slot
        assert type(oid) == str

        slot = MetadataManager.otype_to_slot[otype]  # noqa
        try:
            oid = uuid.UUID(oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid object_id: {}'.format(str(e)))

        with self.db.begin() as txn:
            documentation = self.schema.documentation[txn, oid]
            if documentation:
                return documentation.marshal()
            else:
                return None

    @wamp.register(None)
    def add_docs(self, otype, oid, docs, details=None):
        """

        :param oid:
        :param docs:
        :param details:
        :return:
        """
        assert type(otype) == str
        assert otype in MetadataManager.otype_to_slot
        assert type(oid) == str

        slot = MetadataManager.otype_to_slot[otype]
        try:
            oid = uuid.UUID(oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid object_id: {}'.format(str(e)))

        docs = Documentation.parse(docs)

        result = {'object': oid}

        with self.db.begin(write=True) as txn:
            # get current docs attached to OID
            current_docs = self.schema.obj2docs[txn, (slot, oid)]

            # reuse doc OID or generate new one
            if current_docs:
                if docs.modified != current_docs.modified:
                    raise Exception
                docs.oid = current_docs.oid
                result['new'] = False
            else:
                docs.oid = uuid.uuid4()
                result['new'] = True

            # the OID of the doc (vs the OID of the object the doc is for!)
            result['docs'] = str(docs.oid)

            # save the doc object itself
            self.schema.docs[txn, docs.oid] = docs

            # save the mapping from object to doc object
            self.schema.obj2docs[txn, oid] = docs.oid

        self._session.publish(result, u'{}.on_docs_added'.format(self.prefix))

        return result

    @wamp.register(None)
    def delete_docs(self, oid, details=None):
        """

        :param oid:
        :param details:
        :return:
        """
        assert type(oid) == str

        result = []

        with self.db.begin(write=True) as txn:
            docs = self.schema.obj2docs[txn, oid]
            if docs:
                docs_oid = docs.oid
                del self.schema.obj2docs[txn, oid]
                del self.schema.docs[oid]
                result.append(docs_oid)

        return result

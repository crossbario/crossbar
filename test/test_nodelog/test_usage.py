DBFILE = '../cfc/.crossbar/.db-mrealm-ceabc374-99b1-4623-95ba-36b5f1f85e5c'
GDBFILE = '../cfc/.crossbar/.db-controller'

from pprint import pprint
import zlmdb
from crossbar.master.database.mrealmschema import MrealmSchema
from crossbar.master.database.globalschema import GlobalSchema

db = zlmdb.Database(DBFILE, maxsize=2**30, readonly=False)
schema = MrealmSchema.attach(db)

gdb = zlmdb.Database(GDBFILE, maxsize=2**30, readonly=False)
gschema = GlobalSchema.attach(gdb)

with db.begin() as txn:
    with gdb.begin() as gtxn:
        cnt = schema.mnode_logs.count(txn)
        print('{} node log records so far'.format(cnt))

        cnt = gschema.usage.count(gtxn)
        print('{} usage records so far'.format(cnt))
        for key, rec in gschema.usage.select(gtxn, return_keys=True):
            pprint(rec.marshal())

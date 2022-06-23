DBFILE = '../cfc/.crossbar/.db-mrealm-41cc14b4-b8f2-401e-8736-8993d6daeb55'
GDBFILE = '../cfc/.crossbar/.db-controller'

import zlmdb
from crossbar.master.database.mrealmschema import MrealmSchema
from crossbar.master.database.globalschema import GlobalSchema

db = zlmdb.Database(DBFILE, maxsize=2**30, readonly=False)
schema = MrealmSchema.attach(db)

gdb = zlmdb.Database(GDBFILE, maxsize=2**30, readonly=False)
gschema = GlobalSchema.attach(gdb)

with db.begin() as txn:
    with gdb.begin() as gtxn:
        # self.schema.mnode_logs[txn, (mnode_log.timestamp, mnode_log.node_id)] = mnode_log
        cnt = schema.mnode_logs.count(txn)
        print('{} node log records so far'.format(cnt))

        print('owner, mrealm, node, time, #routers, #containers, #guests, #marketmakers')
        for ts, node_id in sorted(schema.mnode_logs.select(txn, return_values=False)):

            # log -> node -> mrealm -> user
            rec = schema.mnode_logs[txn, (ts, node_id)]
            node = gschema.nodes[gtxn, node_id]
            mrealm = gschema.mrealms[gtxn, node.mrealm_oid]
            owner = gschema.users[gtxn, mrealm.owner]

            print(owner.email, mrealm.name, node.authid, ts,
                  rec.routers, rec.containers, rec.guests, rec.marketmakers)

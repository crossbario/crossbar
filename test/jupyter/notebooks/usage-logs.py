#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import os
import zlmdb
import numpy as np
from pprint import pprint

from crossbar.master.database.globalschema import GlobalSchema
from crossbar.master.database.mrealmschema import MrealmSchema

print('running zlmdb v{} in {}'.format(zlmdb.__version__, os.getcwd()))

DBFILE_GLOBAL = '../../cfc/.crossbar/.db-controller'

gdb = zlmdb.Database(DBFILE_GLOBAL, maxsize=2**30, readonly=False)
gschema = GlobalSchema.attach(gdb)

with gdb.begin() as txn:
    for mrealm in gschema.mrealms.select(txn, return_keys=False, limit=1):
        mrealm_id = mrealm.oid

DBFILE_MREALM = '../../cfc/.crossbar/.db-mrealm-{}'.format(mrealm_id)

db = zlmdb.Database(DBFILE_MREALM, maxsize=2**30, readonly=True)

schema = MrealmSchema.attach(db)


# In[ ]:


with db.begin() as txn:
    cnt = schema.mnode_logs.count(txn)
    print('{} mnodelog records stored'.format(cnt))

    cnt = schema.mworker_logs.count(txn)
    print('{} mworkerlog records stored'.format(cnt))

with gdb.begin() as txn:
    cnt = gschema.usage.count(txn)
    print('{} usage metering records stored. last one:\n'.format(cnt))
    for rec in gschema.usage.select(txn, limit=2, return_keys=False, reverse=True):
        pprint(rec.marshal())


# In[ ]:


from pprint import pprint

with db.begin() as txn:
    for rec in schema.mnode_logs.select(txn, limit=1, return_keys=False, reverse=True):
        pprint(rec.marshal())
    for rec in schema.mworker_logs.select(txn, limit=1, return_keys=False, reverse=True):
        pprint(rec.marshal())


# In[ ]:


ts_min = None
ts_max = None

with db.begin() as txn:
    for ts, _ in schema.mnode_logs.select(txn, return_values=False):
        if ts_min is None or ts < ts_min:
            ts_min = ts
        if ts_max is None or ts > ts_max:
            ts_max = ts

print(ts_min)
print(ts_max)


# In[ ]:


with db.begin() as txn:
    for ts, _ in schema.mnode_logs.select(txn, return_values=False, limit=1):
        ts_min = ts
    for ts, _ in schema.mnode_logs.select(txn, return_values=False, reverse=True, limit=1):
        ts_max = ts

print(ts_min)
print(ts_max)


# In[ ]:


with db.begin() as txn:
    for rec in schema.mnode_logs.select(txn, limit=20, return_keys=False, reverse=True):
        print(rec.timestamp, rec.node_id, rec.routers)


# Metering record from log `2019-06-24T18:29 - 2019-06-24T18:34` (all clients connected before, and conntected without interruption):
#
# ```
# 2019-06-24T20:34:08+0200 [Container    1070] Metering processing: aggregated and stored mrealm "a026d293-4db8-49aa-ae89-aeeef8ede03e" usage metering data for period ["2019-06-24T18:29:00.000000000", "2019-06-24T18:34:00.000000000"[:
# {'containers': 0,
#  'controllers': 0,
#  'count': 116,
#  'guests': 0,
#  'hostmonitors': 29,
#  'marketmakers': 0,
#  'mrealm_id': 'a026d293-4db8-49aa-ae89-aeeef8ede03e',
#  'mrealms': None,
#  'msgs_call': 583,
#  'msgs_error': 0,
#  'msgs_event': 1166,
#  'msgs_invocation': 583,
#  'msgs_publish': 583,
#  'msgs_published': 583,
#  'msgs_register': 0,
#  'msgs_registered': 0,
#  'msgs_result': 583,
#  'msgs_subscribe': 0,
#  'msgs_subscribed': 0,
#  'msgs_yield': 583,
#  'nodes': 2,
#  'processed': numpy.datetime64('2019-06-24T18:34:08.738467104'),
#  'proxies': 0,
#  'pubkey': None,
#  'routers': 87,
#  'sent': numpy.datetime64('2019-06-24T18:34:00.000000000'),
#  'seq': None,
#  'sessions': 203,
#  'status': 1,
#  'status_message': None,
#  'timestamp': numpy.datetime64('2019-06-24T18:29:00.000000000'),
#  'timestamp_from': None,
#  'total': 0}
# ```
#
# Metering record from log `2019-06-24T18:34 - 2019-06-24T18:39` (all clients initially disconnected, then connecting at the beginning of the interval and staying connected throughout):
#
# ```
# 2019-06-24T20:39:08+0200 [Container    1070] Metering processing: aggregated and stored mrealm "a026d293-4db8-49aa-ae89-aeeef8ede03e" usage metering data for period ["2019-06-24T18:34:00.000000000", "2019-06-24T18:39:00.000000000"[:
# {'containers': 0,
#  'controllers': 0,
#  'count': 120,
#  'guests': 0,
#  'hostmonitors': 30,
#  'marketmakers': 0,
#  'mrealm_id': 'a026d293-4db8-49aa-ae89-aeeef8ede03e',
#  'mrealms': None,
#  'msgs_call': 569,
#  'msgs_error': 0,
#  'msgs_event': 1134,
#  'msgs_invocation': 569,
#  'msgs_publish': 601,
#  'msgs_published': 569,
#  'msgs_register': 4,
#  'msgs_registered': 4,
#  'msgs_result': 569,
#  'msgs_subscribe': 4,
#  'msgs_subscribed': 4,
#  'msgs_yield': 569,
#  'nodes': 2,
#  'processed': numpy.datetime64('2019-06-24T18:39:08.729419458'),
#  'proxies': 0,
#  'pubkey': None,
#  'routers': 90,
#  'sent': numpy.datetime64('2019-06-24T18:39:00.000000000'),
#  'seq': None,
#  'sessions': 209,
#  'status': 1,
#  'status_message': None,
#  'timestamp': numpy.datetime64('2019-06-24T18:34:00.000000000'),
#  'timestamp_from': None,
#  'total': 0}
# ```

# In[ ]:


import numpy as np
from uuid import UUID
from crossbar.cfxdb.log import MWorkerLog

key1 = (np.datetime64('2019-06-24T18:29:00.000000000'), UUID(bytes=b'\x00' * 16), '')
key2 = (np.datetime64('2019-06-24T18:34:00.000000000'), UUID(bytes=b'\xff' * 16), '')

key1 = (np.datetime64('2019-06-24T18:34:00.000000000'), UUID(bytes=b'\x00' * 16), '')
key2 = (np.datetime64('2019-06-24T18:39:00.000000000'), UUID(bytes=b'\xff' * 16), '')

total = 0
sessions = 0
wres = {}

res = {
    'count': 0,
    'total': 0,
    'controllers': 0,
    'hostmonitors': 0,
    'routers': 0,
    'containers': 0,
    'guests': 0,
    'proxies': 0,
    'marketmakers': 0,
    'sessions': 0,
    'msgs_publish': 0,
    'msgs_event': 0,
    'msgs_subscribe': 0,
}

with db.begin() as txn:
    for (ts, node_id, worker_id), rec in schema.mworker_logs.select(txn, reverse=False, from_key=key1, to_key=key2):
        #print(rec.timestamp, rec.node_id, rec.worker_id, rec.type, rec.router_sessions, rec.recv_subscribe)
        total += 1
        sessions += rec.router_sessions

        worker_type = MWorkerLog.WORKER_TYPENAMES[rec.type]
        res['{}s'.format(worker_type)] += 1
        res['count'] += 1

        wkey = (node_id, worker_id)
        if wkey not in wres:
            wres[wkey] = {
                'sessions': 0,
                'msgs_publish_min': 0,
                'msgs_publish_max': 0,
                'msgs_event_min': 0,
                'msgs_event_max': 0,
                'msgs_subscribe_min': 0,
                'msgs_subscribe_max': 0,
            }

        wres[wkey]['sessions'] += rec.router_sessions

        if rec.recv_publish > wres[wkey]['msgs_publish_max']:
            wres[wkey]['msgs_publish_max'] = rec.recv_publish
        if not wres[wkey]['msgs_publish_min'] or rec.recv_publish < wres[wkey]['msgs_publish_min']:
            wres[wkey]['msgs_publish_min'] = rec.recv_publish

        if rec.sent_event > wres[wkey]['msgs_event_max']:
            wres[wkey]['msgs_event_max'] = rec.sent_event
        if not wres[wkey]['msgs_event_min'] or rec.sent_event < wres[wkey]['msgs_event_min']:
            wres[wkey]['msgs_event_min'] = rec.sent_event

        if rec.recv_subscribe > wres[wkey]['msgs_subscribe_max']:
            wres[wkey]['msgs_subscribe_max'] = rec.recv_subscribe
        if not wres[wkey]['msgs_subscribe_min'] or rec.recv_subscribe < wres[wkey]['msgs_subscribe_min']:
            wres[wkey]['msgs_subscribe_min'] = rec.recv_subscribe


for wkey in wres:
    res['sessions'] += wres[wkey]['sessions']
    res['msgs_publish'] += wres[wkey]['msgs_publish_max'] - wres[wkey]['msgs_publish_min']
    res['msgs_event'] += wres[wkey]['msgs_event_max'] - wres[wkey]['msgs_event_min']
    res['msgs_subscribe'] += wres[wkey]['msgs_subscribe_max'] - wres[wkey]['msgs_subscribe_min']

pprint(wres)
pprint(res)

heartbeat_secs = 10
print('=' * 100)
# print('Total records: {}'.format(total))
print('Sessions: {} seconds'.format(sessions * heartbeat_secs))
print('Routers: {} seconds'.format(res['routers'] * heartbeat_secs))


# In[ ]:


5 * 60 / 10 == 30, 30 * 7 == 210, 30 * 3 == 90, 5 * 60 / 2 * 4 == 600


# In[ ]:


from crossbar.master.database.globalschema import GlobalSchema

DBFILE_GLOBAL = '/home/oberstet/scm/crossbario/crossbar/test/cfc/.crossbar/.db-controller'

gdb = zlmdb.Database(DBFILE_GLOBAL, maxsize=2**30, readonly=False)

gschema = GlobalSchema.attach(gdb)

with gdb.begin() as txn:
    cnt = gschema.mrealms.count(txn)
    print('{} mrealms records'.format(cnt))

    cnt = gschema.usage.count(txn)
    print('{} usage records'.format(cnt))

    for mrealm in gschema.mrealms.select(txn, return_keys=False):
        pprint(mrealm.marshal())

    for mrealm in gschema.mrealms.select(txn, return_keys=False, limit=1):
        print(mrealm.oid)


# In[ ]:


from pprint import pprint

with gdb.begin() as txn:
    for rec in gschema.usage.select(txn, limit=1, return_keys=False, reverse=True):
        pprint(rec.marshal())


# In[ ]:





# In[ ]:


with db.begin() as txn:
    for rec in schema.mnode_logs.select(txn, limit=20, return_keys=False, reverse=True):
        #pprint(rec.marshal())
        print(rec.timestamp, rec.node_id, rec.routers, rec.cpu_freq, rec.cpu_system, rec.cpu_user)


# In[ ]:


with db.begin() as txn:
    for rec in schema.mworker_logs.select(txn, return_keys=False, reverse=True):
        if rec.worker_id == 'worker002':
            pprint(rec.marshal())
            break


# In[ ]:


import uuid
import binascii

node_id = uuid.UUID('9e604eff-029b-4ce6-bbd7-962bf541fb63')

with gdb.begin() as txn:
    node = gschema.nodes[txn, node_id]
    if node:
        pubkey = binascii.a2b_hex(node.pubkey)
        rec = gschema.idx_last_usage_by_pubkey[txn, pubkey]
        if rec:
            pprint(rec.marshal())
        else:
            print('node found, but no usage found!')
    else:
        print('node not found!')


# In[ ]:


from uuid import UUID
import numpy as np

key1 = (np.datetime64('2019-06-23T00:00:00.00000000'), UUID(bytes=b'\x00' * 16))
key2 = (np.datetime64('2019-06-24T00:00:00.00000000'), UUID(bytes=b'\xff' * 16))

with db.begin() as txn:
    cnt = schema.mnode_logs.count_range(txn, from_key=key1, to_key=key2)
    print('cnt=', cnt)
    for key in schema.mnode_logs.select(txn, limit=5, return_values=False, from_key=key1, to_key=key2, reverse=False):
        print(key)
    #    #pprint(rec.marshal())
    #    print(rec.timestamp, rec.node_id, rec.routers)


# In[ ]:


with gdb.begin() as txn:
    for rec in gschema.usage.select(txn, limit=1, return_keys=False, reverse=True):
        #print(rec.timestamp, rec.timestamp_from, rec.processed, rec.routers)
        pprint(rec.marshal())


# In[ ]:


import numpy as np
import uuid
from pprint import pprint

from_ts = np.datetime64('2019-06-25T09:57:00.000000000')
until_ts = np.datetime64('2019-06-25T10:02:00.000000000')

# compute aggregate sum
res = {
    'count': 0,
    'nodes': 0,
    'routers': 0,
    'containers': 0,
    'guests': 0,
    'proxies': 0,
    'marketmakers': 0,
    'hostmonitors': 0,
    'controllers': 0,
}
nodes = set()
with db.begin() as txn:
    for (ts, node_id) in schema.mnode_logs.select(
            txn,
            from_key=(from_ts, uuid.UUID(bytes=b'\x00' * 16)),
            to_key=(until_ts, uuid.UUID(bytes=b'\xff' * 16)),
            return_values=False,
            reverse=False):

        rec = schema.mnode_logs[txn, (ts, node_id)]

        #pprint(rec.marshal())
        #print(rec.mrealm_id, rec.node_id, rec.routers, rec.period)

        if node_id not in nodes:
            nodes.add(node_id)

        res['count'] += 1
        res['nodes'] += rec.period
        res['routers'] += rec.routers * rec.period
        res['containers'] += rec.containers * rec.period
        res['guests'] += rec.guests * rec.period
        res['proxies'] += rec.proxies * rec.period
        res['marketmakers'] += rec.marketmakers * rec.period
        res['hostmonitors'] += rec.hostmonitors * rec.period
        res['controllers'] += rec.controllers * rec.period

pprint(res)


# In[ ]:


with db.begin() as txn:
    for rec in schema.mnode_logs.select(
            txn,
            return_keys=False,
            reverse=True,
            limit=20):
        print(rec.timestamp, rec.mrealm_id, rec.node_id, rec.controllers, rec.routers, rec.hostmonitors)


# In[ ]:


with gdb.begin() as txn:
    print('timestamp|mrealm_id|status|node seconds|controller seconds|hostmonitor seconds|router seconds|session seconds|calls')
    print('-'*120)
    for rec in gschema.usage.select(
            txn,
            return_keys=False,
            reverse=True,
            limit=10):
        print(rec.timestamp, rec.mrealm_id, rec.status, rec.nodes, rec.controllers,
              rec.hostmonitors, rec.routers, rec.sessions, rec.msgs_call)

    print()
    print('timestamp|mrealm_id|aggregation period|processing lag')
    print('-'*120)
    for rec in gschema.usage.select(
            txn,
            return_keys=False,
            reverse=True,
            limit=10):
        print(rec.timestamp, rec.mrealm_id, np.timedelta64(rec.timestamp - rec.timestamp_from, 's'),
              np.timedelta64(rec.processed - rec.timestamp, 'ms'))


# In[ ]:





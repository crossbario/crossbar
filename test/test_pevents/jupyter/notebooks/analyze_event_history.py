#!/usr/bin/env python
# coding: utf-8

# In[ ]:


# import crossbar-zlmdb and open event history example database
import zlmdb
from cfxdb.schema import ZdbSchema

db = zlmdb.Database('../testdb', maxsize=2**30, readonly=True)

schema = ZdbSchema.attach(db)

print(schema)


# In[ ]:


# get a single event from event history by publication ID

with db.begin() as txn:
    # get the first event ID
    for pub_id in schema.event_archive.select(txn, limit=1, return_values=False):
        # get event by ID
        evt = schema.event_archive[txn, pub_id]
        print(evt.marshal())


# In[ ]:


# count all events in event history

with db.begin() as txn:
    cnt = schema.event_archive.count(txn)
    print(cnt)


# In[ ]:


# count all events, grouped by authid

from pprint import pprint
authids = {}

with db.begin() as txn:
    for evt in schema.event_archive.select(txn, limit=100000, return_keys=False):
        if evt.authid not in authids:
            authids[evt.authid] = 0
        authids[evt.authid] += 1

pprint(authids)


# In[ ]:


import time

def doit():
    res = {}
    total = 0
    sum = 0

    with db.begin() as txn:
        i = 0
        for evt in schema.event_archive.select(txn, limit=1000000-1, return_keys=False):
            if evt.topic.startswith('com.example.geoservice.'):
                e = evt.args[0]
                x, y, category = e['x'], e['y'], e['category']
                value1, value2, value3 = e['value1'], e['value2'], e['value3']
                d = (x, y)
                if d not in res:
                    res[d] = (0, 0)
                res[d] = (res[d][0] + 1, res[d][1] + value2)
                total += 1

                if False:
                    if i < 10 or res[d][0] > 14:
                        print('({}, {}): {}. category="{}"  topic="{}"'.format(x, y, res[d], category, evt.topic))
                    elif i == 10:
                        print('...')
                i += 1
    return total

started = time.perf_counter()
total = doit()
ended = time.perf_counter()
recs_per_sec = int(float(total) / (ended - started))
print('{} records in {:.2} secs ({} records per sec)'.format(total, ended - started, recs_per_sec))


# In[ ]:


from pprint import pprint
session_ids = {}

with db.begin() as txn:
    for evt in schema.event_archive.select(txn, limit=100000, return_keys=False):
        if evt.session_id not in session_ids:
            session_ids[evt.session_id] = 0
        session_ids[evt.session_id] += 1

pprint(session_ids)


# In[ ]:


total = 0

with db.begin() as txn:
    for evt in schema.event_archive.select(txn, limit=100000, return_keys=False):
        if evt.topic.startswith('com.example.geoservice.'):
            total += 1

print(total)


# In[ ]:


get_ipython().run_line_magic('autoawait', 'asyncio')


# In[ ]:


import aiohttp
import asyncio

async def fetch(session, url):
    async with session.get(url) as response:
        return await response.text()

async with aiohttp.ClientSession() as session:
    html = await fetch(session, 'https://crossbar.io')
    print(html.find('Crossbar'))


# In[ ]:


from autobahn.asyncio.component import Component, run
from autobahn.wamp.types import RegisterOptions

import asyncio


component = Component(
    transports=[
        {
            "type": "websocket",
            "url": "ws://crossbar:8080/ws",
            "endpoint": {
                "type": "tcp",
                "host": "crossbar",
                "port": 8080
            }
        },
    ],
    realm="realm1",
)


async def add2(x, y, details):
    print("add2(x={}, y={}, details={})".format(x, y, details))
    return x + y


@component.on_join
async def join(session, details):
    print("joined {}".format(details))
    await session.register(add2, u"foobar.add3", options=RegisterOptions(details_arg='details'))
    print("component ready!")

    # await run([component])

await component.start()


# In[ ]:


1


# In[ ]:


import lmdb

#db = lmdb.open('testdb2', readonly=True, subdir=True)
db = lmdb.open('../.testdb', readonly=True, subdir=True, lock=False)
#db = lmdb.open('.', readonly=False, subdir=True)
print(db)


# In[ ]:


import os
os.listdir('../.testdb')


# In[ ]:





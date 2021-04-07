#!/usr/bin/env python
# coding: utf-8

# In[ ]:


# import stuff we need

get_ipython().run_line_magic('matplotlib', 'inline')

import math
import numpy as np
import pandas as pd
import seaborn as sns

import zlmdb
from cfxdb.schema import ZdbSchema


# In[ ]:


# attach to our crossbar event database
db = zlmdb.Database('../testdb', maxsize=2**30, readonly=False)
schema = ZdbSchema.attach(db)

# load our data into plain python lists
vec_x = []
vec_y = []
vec_category = []
vec_value2 = []

map_categories = {'null': 0, 'alert': 1, 'warning': 2, 'info': 3, 'ad': 4, 'other': 5}

with db.begin() as txn:
    i = 0
    # query event store and get geo events ..
    for evt in schema.event_archive.select(txn, limit=1000000-1, return_keys=False):
        if evt.topic.startswith('com.example.geoservice.'):
            e = evt.args[0]
            vec_x.append(e['x'])
            vec_y.append(e['y'])
            vec_category.append(map_categories.get(e['category'], 0))
            vec_value2.append(e['value2'])
        i += 1
        if i % 10000 == 0:
            print('processed {} records ..'.format(i))

print('finished: collected vectors of length {}'.format(len(vec_x)))

# create pandas dataframes from data collected in lists
df = pd.DataFrame({
    'x': np.asarray(vec_x, dtype='uint16'),
    'y': np.asarray(vec_y, dtype='uint16'),
    'category': np.asarray(vec_category, dtype='uint8'),
    'value2': np.asarray(vec_value2, dtype='float32')
})

# compute some basic statistics
df.describe()


# In[ ]:


# helper to truncate x/y coordinates
def trunc(val):
    return int(val / 20)

# apply truncate and compute aggregate
df2 = pd.DataFrame({
    'x': df['x'].apply(trunc),
    'y': df['y'].apply(trunc),
    'value': df['value2'],
}).pivot_table(index='x', columns='y', values='value', aggfunc=np.median)

df2


# In[ ]:


# draw heatmap
sns.heatmap(df2, annot=True, fmt=".3f")


# In[ ]:





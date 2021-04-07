#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import sys
print('Python {}'.format(sys.version))


# In[ ]:


# attach to crossbar event store
import zlmdb
from cfxdb.schema import ZdbSchema

db = zlmdb.Database('../testdb', maxsize=2**30, readonly=False)

schema = ZdbSchema.attach(db)

print(db)


# In[ ]:


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


# In[ ]:


import numpy as np
import pandas as pd

# create pandas dataframe from data collected in lists
df = pd.DataFrame({
    'x': np.asarray(vec_x, dtype='uint16'),
    'y': np.asarray(vec_y, dtype='uint16'),
    'category': np.asarray(vec_category, dtype='uint8'),
    'value2': np.asarray(vec_value2, dtype='float32')
})

# compute some basic statistics
df.describe()


# In[ ]:


get_ipython().run_line_magic('matplotlib', 'inline')

import seaborn as sns

# scatterplot of the first 100 data points
sns.jointplot(data=df[:100], x='x', y='y', kind='scatter', color='r')


# In[ ]:


# compute truncated dataset
import math

def trunc(val):
    return int(val / 20)

df3 = pd.DataFrame({
    'x': df['x'].apply(trunc),
    'y': df['y'].apply(trunc),
    'value': df['value2'],
})

# compute aggregate
df4 = df3.pivot_table(index='x', columns='y', values='value', aggfunc=np.median)


# In[ ]:


# plot heatmap of truncated/aggregated data
sns.heatmap(df4, annot=True, fmt=".3f")


# In[ ]:





Using Numpy with memory views
.............................

.. code-block:: python

    b = bytearray([1, 2, 3])
    m = memoryview(b)
    a = np.ndarray((3,), buffer=m, dtype='uint8')

.. code-block:: python

    a = np.ndarray(shape=(2, 3, 4), dtype='float16', order='F')
    a.nbytes

.. code-block:: python

    with env.begin(db=db1, read_only=True, buffers=True) as txn:
        with txn.cursor() as cur:
            cur.first()
            for key, value in cur:
                print(key, value)

Using LMDB
..........

Write some key-value data pairs to LMDB:

.. code-block:: python

    import os
    import binascii
    import lmdb

    dbfile = '/tmp/mydb.db'

    env = lmdb.Environment(dbfile, max_dbs=5, subdir=False)

    db1_key = 'db1'.encode('utf8')
    db1 = env.open_db(db1_key)

    key1 = 'key1'
    key2 = 'key2-höllölöllölö'

    with env.begin(db=db1, write=True) as txn:
        value = 'Hello, world!'
        txn.put(key1.encode(), value.encode())
        print('WRITE: key={}, value={}'.format(key1, value))

        value = os.urandom(32)
        txn.put(key2.encode('utf8'), value)
        print('WRITE: key={}, value={}'.format(key2, binascii.b2a_hex(value).decode()))

    env.sync()
    print('data written to db')


Read some key-value data pairs from LMDB:

.. code-block:: python

    with env.begin(db=db1, buffers=True) as txn:
        value = txn.get(key1.encode())
        print('READ: key={}, value={}'.format(key1, value))

        value = txn.get(key2.encode('utf8'))
        print('READ: key={}, value={}'.format(key2, binascii.b2a_hex(value).decode()))

    print('data read from db')


Using LMDB with native Pandas data frames
.........................................

.. note::

    This require PyArrow version 0.9 or higher.

In a first Jupyter Python 3 notebook, run the following code to store a native Pandas data frame in LDMB:

.. code:: python

    import numpy as np
    import pandas as pd
    import pyarrow as pa
    import lmdb

    db_file = '/data/scratch/test1.db'
    db1_name = 'db1'.encode()

    env = lmdb.Environment(db_file, max_dbs=5, map_size=16*(2**20), writemap=False, meminit=False, subdir=False)
    db1 = env.open_db(db1_name)

.. code:: python

    df = pd.DataFrame(np.random.randn(8, 4), columns=['A','B','C','D'])
    df


.. raw:: html

    <div>
    <style scoped>
        .dataframe tbody tr th:only-of-type {
            vertical-align: middle;
        }

        .dataframe tbody tr th {
            vertical-align: top;
        }

        .dataframe thead th {
            text-align: right;
        }
    </style>
    <table border="1" class="dataframe">
      <thead>
        <tr style="text-align: right;">
          <th></th>
          <th>A</th>
          <th>B</th>
          <th>C</th>
          <th>D</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <th>0</th>
          <td>0.775582</td>
          <td>0.463226</td>
          <td>-1.574271</td>
          <td>-0.772137</td>
        </tr>
        <tr>
          <th>1</th>
          <td>-0.895177</td>
          <td>-0.379844</td>
          <td>0.254416</td>
          <td>-0.556199</td>
        </tr>
        <tr>
          <th>2</th>
          <td>-2.135782</td>
          <td>0.958833</td>
          <td>-0.290822</td>
          <td>-1.486390</td>
        </tr>
        <tr>
          <th>3</th>
          <td>1.231065</td>
          <td>0.404586</td>
          <td>0.576380</td>
          <td>0.670212</td>
        </tr>
        <tr>
          <th>4</th>
          <td>-1.174481</td>
          <td>-0.454036</td>
          <td>-1.002825</td>
          <td>-1.054515</td>
        </tr>
        <tr>
          <th>5</th>
          <td>-0.487858</td>
          <td>0.919453</td>
          <td>0.774587</td>
          <td>-0.206856</td>
        </tr>
        <tr>
          <th>6</th>
          <td>1.190229</td>
          <td>0.181721</td>
          <td>1.208325</td>
          <td>-1.169974</td>
        </tr>
        <tr>
          <th>7</th>
          <td>-1.337162</td>
          <td>0.270978</td>
          <td>0.377153</td>
          <td>-0.333179</td>
        </tr>
      </tbody>
    </table>
    </div>


.. code:: python

    key1 = 'key1'.encode()
    value1 = pa.serialize(df).to_buffer()

    with env.begin(db=db1, write=True) as txn:
        txn.put(key1, value1)

    env.sync()
    print('transaction {} complete.'.format(env.info()['last_txnid'] - 1))

.. parsed-literal::

    transaction 2 complete.


In a second Jupyter Python 3 notebook, run the following code to read the Pandas data frame persisted in LMDB.

.. note::

    The read access is zero-copy, and will share the data natively via the mmap'ed LMDB database file.


.. code:: python

    import lmdb
    import numpy as np
    import pyarrow as pa

    db_file = '/data/scratch/test1.db'
    db1_name = 'db1'.encode()

    env = lmdb.Environment(db_file, max_dbs=5, readonly=True, subdir=False)
    db1 = env.open_db(db1_name)

.. code:: python

    key1 = 'key1'.encode()

    with env.begin(db=db1, buffers=True) as txn:
        data_buffer = txn.get(key1)
        df = pa.deserialize(data_buffer)

.. code:: python

    df


.. raw:: html

    <div>
    <style scoped>
        .dataframe tbody tr th:only-of-type {
            vertical-align: middle;
        }

        .dataframe tbody tr th {
            vertical-align: top;
        }

        .dataframe thead th {
            text-align: right;
        }
    </style>
    <table border="1" class="dataframe">
      <thead>
        <tr style="text-align: right;">
          <th></th>
          <th>A</th>
          <th>B</th>
          <th>C</th>
          <th>D</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <th>0</th>
          <td>0.775582</td>
          <td>0.463226</td>
          <td>-1.574271</td>
          <td>-0.772137</td>
        </tr>
        <tr>
          <th>1</th>
          <td>-0.895177</td>
          <td>-0.379844</td>
          <td>0.254416</td>
          <td>-0.556199</td>
        </tr>
        <tr>
          <th>2</th>
          <td>-2.135782</td>
          <td>0.958833</td>
          <td>-0.290822</td>
          <td>-1.486390</td>
        </tr>
        <tr>
          <th>3</th>
          <td>1.231065</td>
          <td>0.404586</td>
          <td>0.576380</td>
          <td>0.670212</td>
        </tr>
        <tr>
          <th>4</th>
          <td>-1.174481</td>
          <td>-0.454036</td>
          <td>-1.002825</td>
          <td>-1.054515</td>
        </tr>
        <tr>
          <th>5</th>
          <td>-0.487858</td>
          <td>0.919453</td>
          <td>0.774587</td>
          <td>-0.206856</td>
        </tr>
        <tr>
          <th>6</th>
          <td>1.190229</td>
          <td>0.181721</td>
          <td>1.208325</td>
          <td>-1.169974</td>
        </tr>
        <tr>
          <th>7</th>
          <td>-1.337162</td>
          <td>0.270978</td>
          <td>0.377153</td>
          <td>-0.333179</td>
        </tr>
      </tbody>
    </table>
    </div>


--------------

* `IPython 7.0, Async REPL <https://blog.jupyter.org/ipython-7-0-async-repl-a35ce050f7f7>`__
* `curio - concurrent I/O <https://github.com/dabeaz/curio>`__
* `Trio: async programming for humans and snake people <https://trio.readthedocs.io/en/latest/>`__




Using one of the Jupyter Docker Stacks requires two choices:

    Which Docker image you wish to use
    How you wish to start Docker containers from that image


https://jupyter-docker-stacks.readthedocs.io/en/latest/using/selecting.html#jupyter-tensorflow-notebook

jupyter/tensorflow-notebook includes popular Python deep learning libraries.

    Everything in jupyter/scipy-notebook and its ancestor images
    tensorflow and keras machine learning libraries


https://jupyter-docker-stacks.readthedocs.io/en/latest/using/running.html#using-the-docker-cli

You can launch a local Docker container from the Jupyter Docker Stacks using the Docker command line interface.


docker build --rm -t my-crossbarfx-notebook .

docker run -p 8888:8888 my-crossbarfx-notebook



Slidedecks from Notebooks:

jupyter nbconvert --to slides index.ipynb --reveal-prefix=reveal.js --SlidesExporter.reveal_theme=serif 
--SlidesExporter.reveal_scroll=True 
--SlidesExporter.reveal_transition=none


https://medium.com/learning-machine-learning/present-your-data-science-projects-with-jupyter-slides-75f20735eb0f
http://veekaybee.github.io/2016/04/20/presentations-the-hard-way/
https://github.com/datitran/jupyter2slides/blob/master/static/css/custom.css
https://medium.freecodecamp.org/how-to-build-interactive-presentations-with-jupyter-notebook-and-reveal-js-c7e24f4bd9c5
http://myslides-on-cf.cfapps.io/

:orphan:


WSGI Host Service
=================

Crossbar.io is able to host
`WSGI <http://legacy.python.org/dev/peps/pep-0333/>`__ based Python
applications, such as `Flask <http://flask.pocoo.org/>`__,
`Pyramid <http://www.pylonsproject.org/projects/pyramid/about>`__ or
`Django <https://docs.djangoproject.com/>`__. This allows whole systems
to be built and run from Crossbar.io, where classic Web parts are served
from the former established Web frameworks, and running reactive parts
of the application as WAMP components.

The WSGI Web application runs on a pool of worker threads, unmodified
and as all WSGI applications in a synchronous, blocking mode. The WSGI
application cannot directly interact with the WAMP router, due to the
difference in synchronous versus asynchronous operation. However, full
bidirectional WAMP integration can be achieved using the :doc:`HTTP
Bridge <HTTP-Bridge>`.

Configuration
-------------

To configure a WSGI Web service, attach a dictionary element to a path
in your :doc:`Web transport <Web-Transport-and-Services>`: :

+------------------+---------------------------------------+
| attribute        | description                           |
+==================+=======================================+
| **``type``**     | Must be ``"wsgi"``.                   |
+------------------+---------------------------------------+
| **``module``**   | The WSGI app Python module to load.   |
+------------------+---------------------------------------+
| **``object``**   | The WSGI app Python object to use.    |
+------------------+---------------------------------------+

Example
-------

See `here <https://github.com/crossbario/crossbar-examples/tree/master/wsgi>`_ 
for a complete example.

Here is a minimal example using Flask. The overall files involved are:

.. code:: text

    myapp.py
    templates/index.html
    .crossbar/config.json

Create a file ``myapp.py`` with your Flask application object:

.. code:: python

    from flask import Flask, render_template

    ##
    ## Our WSGI application .. in this case Flask based
    ##
    app = Flask(__name__)


    @app.route('/')
    def page_home():
       return render_template('index.html', message = "Hello from Crossbar.io")

Create a Jinja template file ``templates/index.html`` (note the
``templates`` subfolder):

.. code:: html

    <!DOCTYPE html>
    <html>
       <body>
          <h1>{{ message }}</h1>
       </body>
    </html>

Add a **Web Transport** with a **WSGI Host Service** on a subpath within
your node configuration:

.. code:: javascript

    {
       "controller": {
       },
       "workers": [
          {
             "type": "router",
             "options": {
                "pythonpath": [".."]
             },
             "transports": [
                {
                   "type": "web",
                   "endpoint": {
                      "type": "tcp",
                      "port": 8080
                   },
                   "paths": {
                      "/": {
                         "type": "wsgi",
                         "module": "myapp",
                         "object": "app"
                      },
                      "ws": {
                         "type": "websocket"
                      }
                   }
                }
             ]
          }
       ]
    }


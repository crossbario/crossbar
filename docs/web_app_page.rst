Web App Pages
=============

**Web App Pages** is a CrossbarFX Web service that dynamically renders HTML templates (Jinja2) into HTML (or JSON).

The crucial feature of **Web App Pages** is: the Jinja2 input template to be rendered gets data that comes from calling a configurable WAMP procedure.

This combination allows to build Web or RESTful frontends for WAMP applications very quickly.


Configuration
-------------

Given a Jinja2 template ``"greeting.html"``

.. code-block:: html+jinja

    <html>
        <title>Greeting</title>
        <body>
            <h1>Greeting</H1>
            <p>
                Hi {{ name }}! This is your personalized greeting message:
            </p>
            <strong>{{ message }}</strong>
        </body>
    </html>

and a WAMP procedure registered under ``"com.example.greeting"``

.. code-block:: python

    class GreetingsBackend(ApplicationSession):

        def __init__(self, config):
            ApplicationSession.__init__(self, config)
            self._counter = 0

        @inlineCallbacks
        def onJoin(self, details):
            yield self.register(self, options=RegisterOptions(details_arg='details'))

        @wamp.register('com.example.greeting')
        def greeting(self, name, details=None):
            self._counter += 1
            result = {
                'name': name,
                'message': 'Hello, "{}"! (counter={})'.format(name, self._counter)
            }
            return result

a **Web App Page** service can be configured like this:

.. code-block:: json

    {
        "type": "wap",
        "templates": "../templates",
        "sandbox": true,
        "routes": [
            {
                "path": "/greeting/<name>",
                "method": "GET",
                "call": "com.example.greeting",
                "render": "greeting.html"
            }
        ],
        "wamp": {
            "realm": "realm1"
        }
    }

The **Web App Page** service configuration refers to above two parts via
the called WAMP procedure URI ``"com.example.greeting"`` and via
the name of the Jinja2 template file ``"greeting.html"``, and connects
both to a Web route, here ``"/greeting/<name>"``.

==============  ===========     ===========
Parameter       Type            Description
==============  ===========     ===========
``type``        string          Type of store, must be ``"wap"`` (for "Web Application").
``templates``   string          Path to templates directory relative to node directory.
``sandbox``     bool            Sandbox Jinja2 rendering run-time environment.
``routes``      list            A list with route definitions (see below).
``wamp``        dict            A dictionary with WAMP session configuration information (see below).
==============  ===========     ===========

The ``routes`` configuration item ist a list with route definitions:

==============  ===========     ===========
Parameter       Type            Description
==============  ===========     ===========
``path``        string          The HTTP URL matching rule (Werkzeug syntax, see below)
``method``      string          The matching HTTP request method, eg ``"GET"``.
``call``        string          The WAMP procedure to call when a matching HTTP request was received.
``render``      string          The template file name (within the ``templates`` directory) that is used to render the client response.
==============  ===========     ===========

The route matching for HTTP URL (``routes.path``) to WAMP procedure is based on
`Werkzeug URL Routing <http://werkzeug.pocoo.org/docs/dev/routing/#werkzeug.routing.MapAdapter.match>`__.

When a match is found, the WAMP procedure configured in ``routes.call`` is called,
and the procedure is expected to return a ``dict``, which is passed as input data
to the template configured in ``routes.render``.
The HTML output returned from the Jinja2 template rendering is returned to
the HTTP client.

The ``wamp`` configuration item configures the WAMP side:

==============  ===========     ===========
Parameter       Type            Description
==============  ===========     ===========
``realm``       string          The realm in which the WAMP procedure mapped from the HTTP URL is looked after and called within.
==============  ===========     ===========


Example
-------

Here is a complete node configuration example:

FIXME:

.. code-block:: json

    {
        "$schema": "https://raw.githubusercontent.com/crossbario/crossbar/master/crossbar.json",
        "version": 2,
        "controller": {
            "fabric": {
                "transport": null
            }
        }
    }

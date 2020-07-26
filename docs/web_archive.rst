Web Archives
============

CrossbarFX includes a full featured Web server that allows dynamic configuration of Web service trees
providing services such as serving static Web content.

For serving static Web content, a Web service of type ``static`` can be used which serves static
Web files from a node local directory (on the host that runs CrossbarFX).

The new ``archive`` Web service in CrossbarFX now allows to serve sets of static Web files directly from
ZIP archives, and those archive files can (optionally) be automatically downloaded from an origin URL
when the Web service is started in CrossbarFX.

This allows to effectively run continuous deployment (CD) pipelines where eg an application frontend
developers team builds, bundles and publishes the application UI as a single ZIP file. The ops team
can then just configure an ``archive`` Web service in CrossbarFX pointing to the ZIP file origin.

.. contents:: :local:

----------


Configuration
-------------

To configure a Web Archive service, add a configuration element to a Web transport:

.. code-block:: json

    {
        "type": "archive",
        "archive": "../app-ui.zip",
        "default_object": "index.html"
    }

This will serve the files from the local ZIP archive ``$CBDIR/../app-ui.zip``. When no (sub)path
is included in a HTTP/GET request, the ``default_object`` will be assumed.

To have the ZIP automatically downloaded from an origin URL and to cache archive files
contents in memory:

.. code-block:: json

    {
        "type": "archive",
        "archive": "../app-ui.zip",
        "origin": "https://example.com/app-ui.zip",
        "cache": true,
        "default_object": "index.html"
    }

By caching archive files contents in memory, requests can be immediately served without
any disk IO or additional CPU load for decompression.

For infrequently accessed content, disabling the caching will just access the requested files
by loading and decompressing the ZIP archive on the fly.

Multiple instances of the Web Archive service can be inserted into a Web transport tree,
eg to separate the regular static Web content and the bundled app UIs:

.. code-block:: json

    {
        "/": {
            "type": "static",
            "directory": "../web",
        },
        "ws": {
            "type": "websocket"
        },
        "/app1": {
            "type": "archive",
            "archive": "../ui/app1.zip",
            "default_object": "index.html",
        }
        "/app2": {
            "type": "archive",
            "archive": "../ui/app2.zip",
            "default_object": "index.html",
        }
        "/app3": {
            "type": "archive",
            "archive": "../ui/app3.zip",
            "default_object": "index.html",
        }
    }



Default Object and File
.......................

The ``default_object`` is the path assumed *when no path* was contained in the HTTP/GET request.

The ``default_file`` is the file served (from the archive) *when an unknown path* was contained
in the HTTP/GET request. Any attempt to access to an unknown path (into the archive) will deliver
the file instead of resulting in a 404.

.. code-block:: json

    {
        "type": "archive",
        "archive": "../test.zip",
        "default_object": "index.html",
        "options": {
            "default_file": "index.html"
        }
    }


MIME Types
..........

The Web Archive service will return files from the ZIP archive to clients
over HTTP, and the ``Content-Type`` HTTP header signals the file type to the
receiving side (usually a Web browser).

The MIME types known and built into the Web Archive service can be extended
and reconfigured using the ``mime_types`` attribute, which must be a dict
mapping file extension to MIME type name:

.. code-block:: json

    {
        "type": "archive",
        "archive": "app-ui.zip",
        "origin": "https://example.com/app-ui.zip",
        "cache": true,
        "default_object": "index.html",
        "mime_types": {
            ".ttf": "font/ttf",
            ".woff": "font/woff",
            ".woff2": "font/woff2"
        }
    }


Content Verification
....................

For added level of security, the archive origin should be hosted on secure HTTP, unless
network level restrictions are in place.

However, even then, this only protects against third parties receiving or modifying
the transferred archive file - it does not protect against the file being compromised
already on the archive file origin server.

This attack can happen for different reasons, and to protect against,
CrossbarFX Web Archive service supports archive file contents verification by matching 
the SHA256 fingerprint of the downloaded file against a list of user configured, known
good fingerprints:

.. code-block:: json

    {
        "type": "archive",
        "archive": "crossbarfx-ui-latest.zip",
        "origin": "https://download.crossbario.com/crossbarfx-ui/crossbarfx-ui-latest.zip",
        "cache": true,
        "hashes": [
            "380e40f5e164c57a93260676e861f3f01de333b8d8fe6ac44c4aed79870a71fd",
            "b055455eebe4157fe51e3cf06b07ae466deb103e245eaa8002f4261728e57577"
        ]
    }

Above will

1. download the archive file from ``https://download.crossbario.com/crossbarfx-ui/crossbarfx-ui-latest.zip`` and stores it as ``$CBDIR/crossbarfx-ui-latest.zip``
2. verify that the SHA256 (hex string) fingerprint of the downloaded file matches on of the hashes configured
3. serves HTTP/GET requests from the file



Example
-------

Here is a complete node configuration example:

.. code-block:: json

    {
        "$schema": "https://raw.githubusercontent.com/crossbario/crossbar/master/crossbar.json",
        "version": 2,
        "controller": {
            "fabric": {
                "transport": null
            }
        },
        "workers": [
            {
                "type": "router",
                "transports": [
                    {
                        "type": "web",
                        "endpoint": {
                            "type": "tcp",
                            "port": 8080
                        },
                        "paths": {
                            "/": {
                                "type": "archive",
                                "archive": "../test.zip",
                                "origin": "https://download.crossbario.com/crossbarfx-ui/crossbarfx-ui-latest.zip",
                                "cache": true,
                                "hashes": [
                                    "380e40f5e164c57a93260676e861f3f01de333b8d8fe6ac44c4aed79870a71fd",
                                    "b055455eebe4157fe51e3cf06b07ae466deb103e245eaa8002f4261728e57577"
                                ],
                                "default_object": "index.html",
                                "options": {
                                    "default_file": "index.html"
                                },
                                "mime_types": {
                                    ".ttf": "font/ttf",
                                    ".woff": "font/woff",
                                    ".woff2": "font/woff2",
                                    ".jgz": "text/javascript"
                                }
                            }
                        }
                    }
                ]
            }
        ]
    }

Crossbar.io
===========

*Decentralized Middleware*

`Crossbar.io <https://crossbar.io>`__ is an open source networking platform for distributed and microservice applications. It implements the open Web Application Messaging Protocol (WAMP), is feature rich, scalable, robust and secure. Let Crossbar.io take care of the hard parts of messaging so you can focus on your app's features.

| |Version| |Test| |Deploy (wheels)| |Deploy (docs)| |Docs|

Resources
---------

-  Download from `PyPI <https://pypi.org/project/crossbar/>`__
-  Read more on the `Project Homepage <https://crossbar.io>`__
-  Jump into the `Getting Started <https://crossbar.io/docs/Getting-Started/>`__
-  Read the reference `Documentation <https://crossbar.io/docs/>`__
-  Join the `User forum <https://crossbar.discourse.group/>`__
-  Ask a question on `StackOverflow <https://stackoverflow.com/questions/ask?tags=crossbar,wamp>`__
-  Read our `Legal Notes <https://github.com/crossbario/crossbar/blob/master/legal/README.md>`__

Docker images
-------------

* `amd64 <https://hub.docker.com/r/crossbario/crossbar>`_
* `armv7 <https://hub.docker.com/r/crossbario/crossbar-armhf>`_
* `armv8 <https://hub.docker.com/r/crossbario/crossbar-aarch64>`_

JSON Schema for Crossbar.io Configuration File Format
-----------------------------------------------------

We now have a JSON Schema file available for **config.json**, if you're using VSCode you can make
use of this by adding the following to your VSCode settings; (File -> Preferences -> Settings)

.. code-block:: json

    "json.schemas": [
        {
            "fileMatch": [
                "/config.json",
                "/.config.json"
            ],
            "url": "https://raw.githubusercontent.com/crossbario/crossbar/master/crossbar.json"
        }
    ],

Alternatively, the generic approach is to insert a "$schema" line at the top of your file;

.. code-block:: json

    {
        "$schema": "https://raw.githubusercontent.com/crossbario/crossbar/master/crossbar.json",
        "version": 2,

This file is currently experimental, but it should give you contextual auto-completion on
all Crossbar **config.json** syntax, use CTRL+Space in VSCode to activate IntelliSense.

--------------

*Copyright (C) 2013-2021 Crossbar.io Technologies GmbH. All rights reserved.
WAMP, Crossbar.io and XBR are trademarks of Crossbar.io Technologies GmbH.*

.. |Version| image:: https://img.shields.io/pypi/v/crossbar.svg
   :target: https://pypi.python.org/pypi/crossbar

.. |Test| image:: https://github.com/crossbario/crossbar/workflows/main/badge.svg
   :target: https://github.com/crossbario/crossbar/actions?query=workflow%3Amain

.. |Deploy (wheels)| image:: https://github.com/crossbario/crossbar/workflows/deploy-wheels/badge.svg
   :target: https://github.com/crossbario/crossbar/actions?query=workflow%3Adeploy-wheels

.. |Deploy (docs)| image:: https://github.com/crossbario/crossbar/workflows/deploy-docs/badge.svg
   :target: https://github.com/crossbario/crossbar/actions?query=workflow%3Adeploy-docs

.. |Docs| image:: https://img.shields.io/badge/docs-latest-brightgreen.svg?style=flat
   :target: https://crossbar.io/docs/

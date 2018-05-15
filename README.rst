Crossbar.io
===========

`Crossbar.io <http://crossbar.io>`__ is an open source networking platform for distributed and microservice applications. It implements the open Web Application Messaging Protocol (WAMP), is feature rich, scalable, robust and secure. Let Crossbar.io take care of the hard parts of messaging so you can focus on your app's features.

| |Version| |Build Status| |Coverage| |Docker| |Snap Status|

Resources
---------

-  Read more on the `Project Homepage <http://crossbar.io>`__
-  Jump into the `Getting Started <http://crossbar.io/docs/Getting-Started/>`__
-  Checkout the complete `Documentation <http://crossbar.io/docs/>`__
-  Join the `Mailing List <https://groups.google.com/forum/#!forum/crossbario>`__
-  Follow us on `Twitter <https://twitter.com/crossbario>`__
-  Ask a question on `StackOverflow <http://stackoverflow.com/questions/ask?tags=crossbar,wamp>`__
-  Read our `Legal Notes <https://github.com/crossbario/crossbar/blob/master/legal/README.md>`__

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


.. |Version| image:: https://img.shields.io/pypi/v/crossbar.svg
   :target: https://pypi.python.org/pypi/crossbar

.. |Build Status| image:: https://travis-ci.org/crossbario/crossbar.svg?branch=master
   :target: https://travis-ci.org/crossbario/crossbar

.. |Coverage| image:: https://img.shields.io/codecov/c/github/crossbario/crossbar/master.svg
   :target: https://codecov.io/github/crossbario/crossbar

.. |Docs| image:: https://img.shields.io/badge/docs-latest-brightgreen.svg?style=flat
   :target: http://crossbar.io/docs/

.. |Docker| image:: https://img.shields.io/badge/docker-ready-blue.svg?style=flat
   :target: https://github.com/crossbario/crossbar-docker#crossbar

.. |Snap Status| image:: https://build.snapcraft.io/badge/crossbario/crossbar.svg
   :target: https://build.snapcraft.io/user/crossbario/crossbar

.. |Bounty 45173769| image:: https://api.bountysource.com/badge/issue?issue_id=45173769
   :target: https://www.bountysource.com/issues/45173769-register-option-to-kick-existing-registration

.. |Bounty 44253224| image:: https://api.bountysource.com/badge/issue?issue_id=44253224
   :target: https://www.bountysource.com/issues/44253224-kerberos-authentication

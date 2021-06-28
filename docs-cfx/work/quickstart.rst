Quickstart
==========

Templates
---------

The service scaffolding built into **cbsh** is based on `cookiecutter <https://cookiecutter.readthedocs.io/>`_ and the templates currently integrated can be found here:

* `Crossbar.io OSS <https://github.com/crossbario/cookiecutter-crossbar>`_
* `Crossbar.io Fabric <https://github.com/crossbario/cookiecutter-crossbar-fabric>`_
* `Autobahn Python <https://github.com/crossbario/cookiecutter-autobahn-python>`_
* `Autobahn JavaScript <https://github.com/crossbario/cookiecutter-autobahn-js>`_
* `Autobahn Java <https://github.com/crossbario/cookiecutter-autobahn-java>`_
* `Autobahn C++ <https://github.com/crossbario/cookiecutter-autobahn-cpp>`_

.. note::

    If you are an implementor of a WAMP client library and would like to get a cookiecutter for your library integrated into cbsh, awesome! Get in touch, or best, submit a PR adding it, we definitely wanna have it=)


Workflow patterns
-----------------

1. Developer scaffolds a XBR API project

    cbsh quickstart api

This collects information such as:

    <project>
    <api_author>
    <api_license>
    <uri_namespace>
    ...

The collected information is used to generate the following files:

    README
    LICENSE
    package.json
    schema.fbs
    index.rst

and two (empty) subdirectories for more FlatBuffer and ReST files
to be included from the main schema.fbs and index.rst files:

    include/..      # .fbs include files (optional)
    docs/..         # .rst include files (optional)

2. Developer fills in his API, editing above files, optionally adding more.

3. Developer compiles the API project

    cbsh bundle api

This checks (via embedded flatc compiler and embedded Sphinx)
that all files are valid and creates a file archive,
an API package:

    <project>.zip


3. Developer imports the API package into local design repository:

    cbsh import api

3.1 Load Schema data

Next, the LSP server, notified of the filesystem change on the path

    $HOME/.cbsh/api/schema

will



3.2 Generate API documentation

This loads the (parsed) content of files from the archive:

    package.json
    index.rst
    docs/..

into files/directories in

    $HOME/.cbsh/api/docs/<project>/

and inserts a reference to

    $HOME/.cbsh/api/docs/<project>/index.rst

into

    $HOME/.cbsh/api/docs/index.rst

Next, the embedded Sphinx with our Sphinx extension to render the .rst files

    $HOME/.cbsh/api/docs

to HTML files in

    $HOME/.cbsh/api/docs/_build

The Sphinx extension is written in Python, and accesses the schema data in LMDB to resolve
references to FlatBuffer definitions.



5. Developer publishes the API library

    cbsh publish api


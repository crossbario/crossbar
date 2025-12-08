Contributing
============

We welcome contributions to **Crossbar.io**! This guide explains how to get involved.

Getting in Touch
----------------

* **GitHub Issues**: Report bugs or request features at
  https://github.com/crossbario/crossbar/issues
* **GitHub Discussions**: Ask questions and discuss at
  https://github.com/crossbario/crossbar/discussions

See also :doc:`Contributing-FAQ` for frequently asked questions about contributing.

Reporting Issues
----------------

When reporting issues, please include:

1. Python version (``python --version``)
2. Crossbar.io version (``crossbar version``)
3. Operating system and version
4. Crossbar.io node configuration (sanitized)
5. Minimal steps to reproduce the issue
6. Full traceback if applicable

Contributing Code
-----------------

1. **Fork the repository** on GitHub
2. **Create a feature branch** from ``master``
3. **Make your changes** following the code style
4. **Add tests** for new functionality
5. **Run the test suite** to ensure nothing is broken
6. **Submit a pull request** referencing any related issues

Development Setup
-----------------

.. code-block:: bash

    git clone https://github.com/crossbario/crossbar.git
    cd crossbar
    pip install -e .[dev]

Running Tests
-------------

.. code-block:: bash

    # Run all tests
    tox

    # Run tests for specific Python version
    tox -e py312

Code Style
----------

* Follow PEP 8
* Use meaningful variable and function names
* Add docstrings for public APIs
* Keep lines under 100 characters

License
-------

By contributing to Crossbar.io, you agree that your contributions will be
licensed under the project's license. See :doc:`Crossbar-License` for details.

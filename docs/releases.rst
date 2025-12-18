Release Notes
=============

This page provides links to release artifacts for each version of Crossbar.io.

For detailed changelog entries, see :doc:`changelog`.

23.1.2
------

* `GitHub Release <https://github.com/crossbario/crossbar/releases/tag/v23.1.2>`__
* `PyPI Package <https://pypi.org/project/crossbar/23.1.2/>`__
* `Documentation <https://crossbar.readthedocs.io/en/v23.1.2/>`__

23.1.1
------

* `GitHub Release <https://github.com/crossbario/crossbar/releases/tag/v23.1.1>`__
* `PyPI Package <https://pypi.org/project/crossbar/23.1.1/>`__
* `Documentation <https://crossbar.readthedocs.io/en/v23.1.1/>`__

22.6.1
------

* `GitHub Release <https://github.com/crossbario/crossbar/releases/tag/v22.6.1>`__
* `PyPI Package <https://pypi.org/project/crossbar/22.6.1/>`__

22.5.1
------

* `GitHub Release <https://github.com/crossbario/crossbar/releases/tag/v22.5.1>`__
* `PyPI Package <https://pypi.org/project/crossbar/22.5.1/>`__

22.4.1
------

* `GitHub Release <https://github.com/crossbario/crossbar/releases/tag/v22.4.1>`__
* `PyPI Package <https://pypi.org/project/crossbar/22.4.1/>`__

22.3.1
------

* `GitHub Release <https://github.com/crossbario/crossbar/releases/tag/v22.3.1>`__
* `PyPI Package <https://pypi.org/project/crossbar/22.3.1/>`__

22.2.1
------

* `GitHub Release <https://github.com/crossbario/crossbar/releases/tag/v22.2.1>`__
* `PyPI Package <https://pypi.org/project/crossbar/22.2.1/>`__

22.1.1
------

* `GitHub Release <https://github.com/crossbario/crossbar/releases/tag/v22.1.1>`__
* `PyPI Package <https://pypi.org/project/crossbar/22.1.1/>`__

21.3.1
------

* `GitHub Release <https://github.com/crossbario/crossbar/releases/tag/v21.3.1>`__
* `PyPI Package <https://pypi.org/project/crossbar/21.3.1/>`__

21.2.1
------

* `GitHub Release <https://github.com/crossbario/crossbar/releases/tag/v21.2.1>`__
* `PyPI Package <https://pypi.org/project/crossbar/21.2.1/>`__

--------------

See Also
--------

* :doc:`changelog` - Detailed technical changelog
* :doc:`Compatibility-Policy` - Version compatibility information
* `GitHub Releases <https://github.com/crossbario/crossbar/releases>`_ - All releases

--------------

.. _release-workflow:

Release Workflow (for Maintainers)
----------------------------------

This section documents the release process for maintainers.

Prerequisites
^^^^^^^^^^^^^

Before releasing, ensure you have:

* Push access to the repository
* PyPI credentials configured (or trusted publishing via GitHub Actions)
* ``just`` and ``uv`` installed

Step 1: Draft the Release
^^^^^^^^^^^^^^^^^^^^^^^^^

Generate changelog and release note templates:

.. code-block:: bash

   # Generate changelog entry from git history (for catching up)
   just prepare-changelog <version>

   # Generate release draft with templates for both files
   just draft-release <version>

This will:

* Add a changelog entry template to ``docs/changelog.rst``
* Add a release entry template to ``docs/releases.rst``
* Update the version in ``pyproject.toml``

Step 2: Edit Changelog
^^^^^^^^^^^^^^^^^^^^^^

Edit ``docs/changelog.rst`` and fill in the changelog details:

* **New**: New features and capabilities
* **Fix**: Bug fixes
* **Other**: Breaking changes, deprecations, other notes

Step 3: Validate the Release
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Ensure everything is in place:

.. code-block:: bash

   just prepare-release <version>

This validates:

* Changelog entry exists for this version
* Release entry exists for this version
* Version in ``pyproject.toml`` matches
* All tests pass
* Documentation builds successfully

Step 4: Disable Git Hooks (if needed)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   git config core.hooksPath /dev/null
   git config core.hooksPath

Step 5: Commit and Tag
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   git add docs/changelog.rst docs/releases.rst pyproject.toml
   git commit -m "Release <version>"
   git tag v<version>
   git push && git push --tags

Step 6: Enable Git Hooks (if previously disabled)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   git config core.hooksPath .ai/.githooks
   git config core.hooksPath

Step 7: Automated Release
^^^^^^^^^^^^^^^^^^^^^^^^^

After pushing the tag:

1. GitHub Actions builds and tests the release
2. Wheels and source distributions are uploaded to GitHub Releases
3. PyPI publishing is triggered via trusted publishing (OIDC)
4. Read the Docs builds documentation for the tagged version

Manual PyPI Upload (if needed)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If automated publishing fails:

.. code-block:: bash

   just download-github-release v<version>
   just publish-pypi "" v<version>

:orphan:
  
.. _installation:


Installation
============

Below are different ways of installing Crossbar.io. We recommend our
`Docker images`_ 

If you have an installation related question, please also check the  :doc:`Installation-FAQ <Installation-FAQ>` .

Docker Images
-------------

We provide official Docker images for Crossbar.io in different flavors.
This is both a quick way getting started with Crossbar.io and a good
approach going to production:

*  :doc:`Getting Started <../Getting-Started>`  


Other Platforms
---------------

We provide installation instructions for setting up Crossbar.io on your
own systems for different operating systems or environments.

*  :doc:`Installation on Linux <Installation-on-Linux>`  
*  :doc:`Installation on Mac OS X <Installation-on-Mac-OS-X>`
*  :doc:`Installation on Windows <Installation-on-Windows>`


Verifying a release
-------------------

Every file of a Crossbar.io release on PyPI carries a
`PEP 740 <https://peps.python.org/pep-0740/>`__ attestation. To check that a file was
uploaded by this project's release workflow:

.. code-block:: console

    $ pip install pypi-attestations
    $ pypi-attestations verify pypi --repository https://github.com/crossbario/crossbar \
          pypi:crossbar-26.7.1-py3-none-any.whl
    OK: crossbar-26.7.1-py3-none-any.whl

This proves that the file was uploaded to PyPI through Trusted Publishing by a GitHub
Actions workflow of ``github.com/crossbario/crossbar``. It does not prove how the file was
built.

From a source checkout, ``just verify-pypi 26.7.1`` checks every file of a release this
way (the wheel and the source distribution).

Setup in the Cloud
------------------

Crossbar.io runs great on *Infrastructure-as-a-Service (Iaas)* providers
like `Amazon EC2 <http://aws.amazon.com/ec2/>`__ or `Microsoft
Azure <http://azure.microsoft.com/>`__. As an example, there's

*  :doc:`Setup on Amazon EC2 <Setup-on-Amazon-EC2>`

Additionally, Crossbar.io can be run on *Platform-as-a-Service (PaaS)*
providers:

*  :doc:`Setup on Heroku <Setup-on-Heroku>`
*  :doc:`Setup on OpenShift <Setup-on-OpenShift>`

Demo Instance
-------------

For light-weight testing purposes, you might also use our public demo
instances of Crossbar.io:

*  :doc:`Demo Instance <Demo-Instance>`

    The public demo instances of Crossbar.io is provided as a
    convenience, and for free. Please only use it for development and
    testing purposes. We don't make any guarantees whatsoever, and the
    service might be restricted in the future.

Try without Installation
------------------------

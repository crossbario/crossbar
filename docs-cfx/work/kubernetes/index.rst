Sample Kubernetes Build
=======================

This specific procedure will work to varying extents on other Kubernetes implementations, however it would seem that different implementations can have different feature-sets, so a catch-all Helm script that works out of the box on every possible combination might prove to be quite an elusive goal. I would expect for example this to be pretty close on a fully implemented Kubernetes cluster running on AWS, however it's not going to work out-of-the-box on a local / on-premises installation because it's relying on load-balancers that typically aren't available on private-cloud deployments.

The Helm charts I'm using are available here; https://crossbar-charts.storage.googleapis.com/cfc/ , and the tweaked Crossbarfx docker images are here; eu.gcr.io/cfcfx-212110/cfc , eu.gcr.io/cfcfx-212110/fx

Assuming your cluster is setup and working, all you should need to do is;

.. code-block:: shell

    helm repo add crossbar-charts https://crossbar-charts.storage.googleapis.com/cfc/
    helm install --name fx crossbar-charts/edge --set image.repository="eu.gcr.io/cfcfx-212110/fx" 
    helm install --name cfc crossbar-charts/master --set image.repository="eu.gcr.io/cfcfx-212110/cfc" 

to enable the MAILGUN email service (for automatically emailing out activation codes) you will need a [free] MAILGUN account from https://www.mailgun.com, then add the following to the end of the helm install commands;

.. code-block:: shell

    --set mailgun.key="${KEY}" --set mailgun.from="${FROM}" --set mailgun.url="${URL}"

where KEY is set to your MAILGUN API key, URL is your MAILGUN API url, and FROM is the address you would like to see the emails coming 'from'. (let me know if you need examples of any of these)

Building
--------

To build the Kubernetes scripts required, do;

.. code-block:: shell

    make build-edge build-master package

Which will generate a couple of compressed tar archives, and an index, these filles then need to be copied up to your Helm repository. If
you follow that with a;

.. code-block:: shell

    make deploy

If you have all your environment variables correctly pointing at a live environment, this will roll out an entire CFC/FX/etcd deployment.

NOTE
----

When adding this to the crossbarfx repo, the binaries used in the sample deployment were removed. Before attempting any of the above
you will need to copy the crossbarfx binary you want to use intp the docker-edge and docker-master folder, and a copy of the ui into
the docker-master folder.

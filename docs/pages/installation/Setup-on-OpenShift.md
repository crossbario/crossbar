[Documentation](.) > [Installation](Installation) > [Setup in the Cloud](Setup in the Cloud) > Setup on OpenShift

# Setup on OpenShift

[OpenShift](https://www.openshift.com/) is Red Hat's Platform-as-a-Service (PaaS), focused on hosting web applications.  Resources are mapped as "Gears" and application setup is provided by "Cartridges". Cartridges are the plug-ins that house the framework or components that can be used to create and run an application.

Crossbar.io can be run on OpenShift since they provide a [beta WebSocket](https://blog.openshift.com/paas-websockets/) support on HTTP (8000) and HTTPS (8443).


## Pre-requisites

- An [account](https://www.openshift.com/app/account/new) on OpenShift.
- OpenShift's [client tool](https://developers.openshift.com/en/getting-started-overview.html) (`rhc`) properly configured.


## Crossbar.io on OpenShift

To run crossbar.io on OpenShift you will have to use a [DIY](https://developers.openshift.com/en/diy-overview.html) cartridge.  That is because [Python cartridges](https://developers.openshift.com/en/python-overview.html) are based on `Apache+mod_wsgi` so they won't handle Websockets.  Using `DIY` the request is passed from the [Openshift Websocket proxy](https://github.com/openshift/origin-server/tree/master/node-proxy) directly into you application [local port](https://developers.openshift.com/en/managing-port-binding-routing.html).

There are two options for deploying Crossbar.io:

1. Use a a base application to start with
2. Create your DIY application from scratch

This howto uses option `(1.)`.

## Use a a base application to start with

There is an OpenShift [application](https://github.com/jvdm/openshift-crossbar) which you can use as a starting point for your Crossbar.io installation.  This base application was created to provide a minimal setup to run a standard Crossbar.io installation (based on `crossbar init`) using `Python-3.5`.

It also provide a way to easy customize the Crossbar.io instance by editing its configuration file `config.{yaml,json}`.

To use it you can:

1. Call `rhc app create` passing `--from-code https://github.com/jvdm/openshift-crossbar`.
2. Use the web console interface on the *Add Application* page, select *Do-It-Yourself 0.1* and set the *Source Code* field.

## Crossbar.io configuration

Crossbar.io configuration on OpenShift can't be static: that's because the ip address and port used must match the ones OpenShift is expecting you to use.  OpenShift provides this information through environment variables: `OPENSHIFT_DIY_IP` and `OPENSHIFT_DIY_PORT`.

The application will use `config.{json,yaml}` files in the project's root as a template to create `.crossbar/config.{json,yaml}`, by evaluating any shell variable expansion inside the file.  That's how you have a dynamic crossbar configuration on crossbar.io startup.

If you want to change crossbar.io configuration, you just need to edit the `config.yaml` file on the project's root.  You can change its name to `config.json` if you prefer working with JSON.  But this file will be used only as a "template": the crossbar instance will be run using `.crossbar` as `CROSSBAR_DIR`, so adjust your paths.

## What will you get

After application deploy (which is done by a `git push`), you should be able to access the web worker on `http://<app-name>-<domain-name>.rhcloud.com`.

To connect to the router using websockets you will need to use port `:8000`: `http://<app-name>-<domain-name>.rhcloud.com:8000/ws`.

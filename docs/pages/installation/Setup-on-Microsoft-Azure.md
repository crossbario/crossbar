title: Setup on Microsoft Azure
toc: [Documentation, Installation, Setup on Microsoft Azure]

# Setup on Microsoft Azure

We provide a [**Crossbar on Azure Virtual Machine Image**](http://azure.microsoft.com/en-us/marketplace/partners/tavendo/crossbar-on-azure-ubuntu1404-free/) in the  [Azure Marketplace](http://azure.microsoft.com/en-us/marketplace/) to make setup on [Microsoft Azure](http://azure.microsoft.com/) as simple as possible. The image has Crossbar.io running on [Ubuntu Server 14.04 LTS](https://insights.ubuntu.com/2014/04/17/whats-new-in-ubuntu-server-14-04-lts/).

Use of this image is free (but Azure billings for running the VM apply).

If you want to install Crossbar.io from scratch, or run it on a different OS, see the [instructions for installation](Home#Installation).


## Creating the Virtual Machine

1. Go to the [image](http://azure.microsoft.com/en-us/marketplace/partners/tavendo/crossbar-on-azure-ubuntu1404-free/) in the Azure Marketplace (or search for 'crossbar').
2. Click on "Create Virtual Machine".
3. This takes you to the Azure portal (possibly with an intermediate login screen if you're not currently logged in to Azure) and starts the creation of the machine.
4. Enter the required information:
   + "Host Name" (pick anything you like)
   + "User Name": needs to be 'ubuntu'
   + We suggest using an SSH public key instead of a password.
5. Defaults for other settings are OK. Necessary ports are already configured.
6. Click "Create".
7. On the purchasing information screen click "Buy".
8. Wait for the machine setup to finish.


## Running the VM

Crossbar.io automatically starts up once the machine is started. This runs with a default configuration which is maximally permissive for testing and development purposes. A single realm (`realm1`) is preconfigured, and accepts any clients.

On first startup, the system and Crossbar.io are automatically updated. Because of this the first startup may take a little while. Further updates are under your control.


## Testing functionality

To check whether Crossbar.io is up, get the public IP of your instance from the Azure dashboard, and point your browser to it.

> Note: If you want to test the actual Crossbar.io core functionality, i.e. WAMP routing, you can run any of the [Crossbar.io examples](https://github.com/crossbario/crossbarexamples). For these you need to adapt the connection data.

We suggest you use the [Votes Browser Demo](https://github.com/crossbario/crossbarexamples/tree/master/demos/votes/browser), since this runs entirely in the browser. To run this

* Get a local copy of the repository. You can clone it using [git](http://www.git-scm.com/), or download the repository as a [zip file](https://github.com/crossbario/crossbarexamples/archive/master.zip).
* Set the appropriate connection data, i.e. in 'crossbarexamples/votes/browser/js' you need to modify both 'backend.js' and 'frontend.js' so that 'wsuri' is the IP of your Azure instance, with port 80.
E.g. for an Azure IP of '178.34.23.89', you would add 'wsuri = 'ws://178.34.23.89:80';' after line 21 in both files.
Additionally, you need to change the realm to `realm1`, which is the only realm configured in the image as a default.

```javascript
wsuri = 'ws://178.34.23.89:80/ws'; // add this!

var connection = new autobahn.Connection({
   url: wsuri,
   realm: 'realm1'} // change me!
);
```

## Start developing

We provide [getting started guides](Getting Started) for various languages. WAMP client libraries may be available for languages not covered there. Check the [WAMP implementations list](http://wamp.ws/implementations) for the most current overview of supported languages.

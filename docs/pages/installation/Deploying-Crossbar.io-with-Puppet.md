[Documentation](.) > [Installation](Installation) > [Deploying Crossbar.io](Deploying Crossbar.io) > Deploying Crossbar.io with Puppet

# Install Crossbar.io from Puppetforge 

With Puppet you can provision Crossbar.io WAMP Router on your systems with standalone agent, Puppet Server or Puppet Enteprise.

We provide a module on [Puppetforge](https://forge.puppet.com/bluesman/crossbar).

For an overview of all feature supported and more technical details, see the [GitHub repository](https://github.com/blues-man/crossbar-puppet).


## Usage

Installation:

```console
puppet module install bluesman-crossbar
```

To run:

```console
puppet apply -e 'include crossbar'
```

This will start and init a Crossbar.io server with default configuration. To check things are running, point your browser to http://machine-ip:8080. This should show a custom 404 page.


## OS Support

Currently, only these Operating System are supported

* CentOS 7


## Next

Ready to go? Then [choose your language or device of choice](Choose your Weapon).

[Documentation](.) > [Programming Guide](Programming Guide) > Try out without Installation

# Try out without installation

You can try out what WAMP & Crossbar.io can do right now, in your browser, without the need for any installation. 

Download the following two HTML pages (right click & save)

* [Component 1](https://raw.githubusercontent.com/crossbario/crossbardemo/master/crossbardemo/crossbardemo/web/demo/minimal/component_01.html)
* [Component 2](https://raw.githubusercontent.com/crossbario/crossbardemo/master/crossbardemo/crossbardemo/web/demo/minimal/component_02.html)

and open them in your browser (double click on the file).

They connect to an online demo instance of Crossbar.io. Each registers a procedure, calls a procedure on the other, subscribes to one topic, and publishes to another.

Open the browser console to see the output. Open the files in your editor to see how little code is needed.

**Note**: If more than a single person tries this at the same time, then 

* the procedure calls will be received by the last component to register the procedure
* every component will receive PubSub events from all other components

## Using the Crossbar.io demo instance for your own testing

The Crossbar.io demo instance is there for you to use for your experiments.
This is currently a micro instance on EC2, and also serves the [Crossbar.io live demos](https://demo.crossbar.io/). 

The connection data for this is:

`wss://demo.crossbar.io/ws`

with realm

`realm1`

The rules for this are common sense:

* Use only for testing, not for production.
* There's only one realm, so namespace your URIs sensibly to avoid conflict with other users.
* Don't constantly hammer the router (others also want to play).
* Keep traffic to a sensible level (we pay by the GB).
* We make no guarantees about performance or availability.

Once you've decided that Crossbar.io is something you want, go install it yourself!


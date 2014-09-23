# Using Crossbar with Express

This example shows how to use Crossbar.io together with [Express](http://expressjs.com/), a more classic Web application framework for Node.

## Prerequisites

Obviously you will need Node. Then install required Node modules by doing

	npm install -g express nunjucks autobahn

Make sure Node can find your globally installed modules by setting `NODE_PATH` appropriately.

E.g. on Windows (replacing "oberstet" with you username)

	export NODE_PATH="C:\Users\oberstet\AppData\Roaming\npm\node_modules

and Linux

	export NODE_PATH=/usr/local/lib/node_modules

## Running the Demo

Start Crossbar.io by doing

	crossbar start

in a first terminal from the demo root directory.

In a second terminal, change to the `express` subdirectory and do

	node server.js

Now open [http://localhost:8080](http://localhost:8080) in your browser.

Open [http://localhost:8080/monitor](http://localhost:8080/monitor) in a second browser window and reload the first window a couple of times. You should see the visit count increase in real-time in the monitor window.

## How it works

The Crossbar.io node configuration included with the demo will start a Crossbar.io node only running a single worker process with a WAMP router listening on port 9000.

The Express application has all it's code in `server.js`. This code will render pages on routes using [Nunjucks](http://mozilla.github.io/nunjucks/), a [Jinja2](http://jinja.pocoo.org/docs/dev/)-like templating engine that works with Express.

However, the code will *also* connect to Crossbar.io as a WAMP application component. Doing so allows us to publish real-time events to Crossbar.io, which in turn will forward the events to WAMP subscribers. We also register a procedure so that it can be called remotely from any WAMP client.

The monitor HTML page is rendered by Express (as any other page), but the JavaScript in the HTML page connects to Crossbar.io. It then subscribes to receive events, and it also calls the procedure we registered in `server.js`.

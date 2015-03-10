# Tessel WAMP demo application

This directory contains a demo for use of the Tessel as part of a WAMP application.

You need to have Node.js and the node package manager (npm) installed, with your Tessel set up and working.

TO install `wamp-tessel`, in the demo directory do

```
npm install
```

Once you've got these prerequisites, start Crossbar.io from the demo directory by doing

```
crossbar start
```

You can then access to the browser component (which is served by Crossbar.io) under `http://localhost:8080`.

For the Tessel component, connect your Tessel, connect it to a wi-fi network which the computer running Crossbar.io is also connected to.

You then need to open `tessel/hello.js` and edit the URL for the WAMP connection to use the IP for the computer running Crossbar.io.

Then run the code on the Tessel by doing

```
cd tessel
tessel run hello.js
```

The two components each subscribe to a topic + publish to a topic, register a procedure and call a procedure, logging events in connection with these actions to the console.

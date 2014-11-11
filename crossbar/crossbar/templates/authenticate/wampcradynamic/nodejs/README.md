This example demonstrates how to authenticate WAMP clients using WAMP-CRA and a custom authentication procedure written in JavaScript (running under Node).

The `authenticator.js` provides a single procedure `com.example.authenticate`. This procedure is configured in Crossbar.io node configuration to be called whenever a WAMP client is connecting to the router via `ws://<router hostname>:8080/ws`. Within this procedure, you can hook up to any user database you already have.

The custom authenticator *itself* is also authenticated via WAMP-CRA to the router, but using a static authentication configuration (the credentials are defined in the node configuration).

The `backend.js` is another example backend component written in JS that is authenticated via WAMP-CRA and static authentication information.

The `client.js` essentially does the same as the JS in `index.html`, but can be run from Node instead of browser.

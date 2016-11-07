title: Crossbar.io Code License
toc: [Documentation, Crossbar License]

# Crossbar.io Code License

## Code

The Crossbar.io [source code](https://github.com/crossbario/crossbar/tree/master/crossbar) is licensed under the [GNU AGPL 3.0](http://www.gnu.org/licenses/agpl-3.0.html). You can find a copy of the license in the repository [here](https://github.com/crossbario/crossbar/blob/master/LICENSE) and references to this license at the top of each source code file.

All rights to the Crossbar.io source code remain exclusively with [Crossbar.io Technologies GmbH](http://crossbario.com/). All [external contributors](https://github.com/crossbario/crossbar/blob/master/legal/contributors.md) need to sign a **contributor assignment agreement (CAA)** when [contributing to the project](https://github.com/crossbario/crossbar/blob/master/CONTRIBUTING.md).

The Crossbar.io [application templates](https://github.com/crossbario/crossbar/tree/master/crossbar/templates) and instances of code generated from these templates are licensed under the [BSD 2-clause](http://opensource.org/licenses/BSD-2-Clause) license.

## WAMP clients as separate works

We see any code which connects to Crossbar.io via WAMP as a separate work. The Crossbar.io license (the AGPL v3) does not apply to WAMP clients. This applies irrespective of where these run, i.e. also to components which are run side-by-side within an native worker of type router, which are run in a native worker of type container or in a guest worker. We promise to stand by this view of the license.
If you need further assurance, you can email us at contact@crossbario.com for a signed letter asserting the above promise.

We release all our client libraries (those provided by the [Autobahn project](http://autobahn.ws/) under non-copyleft licenses, which allow their use for closed-source & commercial software. For other client libraries see their respective licenses (these appear to be universally non-copyleft as well).

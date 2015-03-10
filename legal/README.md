# Copyright

The following sections provide information about legal aspects related to Crossbar.io.

## Code

The Crossbar.io [source code](https://github.com/crossbario/crossbar/tree/master/crossbar) is licensed under the [GNU AGPL 3.0](http://www.gnu.org/licenses/agpl-3.0.html). You can find a copy of the license in the repository [here](https://github.com/crossbario/crossbar/blob/master/crossbar/LICENSE) and references to this license at the top of each source code file.

All rights to the Crossbar.io source code remain exclusively with [Tavendo](http://tavendo.com/). All (external) contributors sign a [Contributor Assignement Agreement](https://github.com/crossbario/crossbar/wiki/Contributing%20to%20the%20project)

The Crossbar.io [application templates](https://github.com/crossbario/crossbar/tree/master/crossbar/crossbar/templates) and instances of code generated from these templates are licensed under the [BSD 2-clause](http://opensource.org/licenses/BSD-2-Clause) license. 

## WAMP clients as separate works

We see any code which connects to Crossbar.io via WAMP as a separate work. The Crossbar.io license (the AGPL v3) does not apply to WAMP clients. This applies irrespective of where these run, i.e. also to components which are run side-by-side within an native worker of type router, which are run in a native worker of type container or in a guest worker. We promise to stand by this view of the license.
If you need further assurance, you can email us at service@tavendo.de for a signed letter asserting the above promise.

We release all our client libraries (those provided by the [Autobahn project](http://autobahn.ws/) under non-copyleft licenses, which allow their use for closed-source & commercial software. For other client libraries see their respective licenses (these appear to be universally non-copyleft as well).

## Templates

Crossbar.io is able to generate applications from application templates. The code for application templates within this folder (and folders beneath) is licensed under the [BSD 2-clause open-source license](http://opensource.org/licenses/BSD-2-Clause) or the [Apache 2.0 license](http://www.apache.org/licenses/LICENSE-2.0).

The same licenses applie to the code *generated* from the application templates. E.g., when you do

    crossbar init --template hello:python --appdir $HOME/hello

Crossbar.io will generate a new WAMP application in the `$HOME/hello` directory from the application template in [hello/python](hello/python). All files generated in `$HOME/hello` are licensed under above licenses.

The licenses allow you to use the template code and generated code in your own applications, including closed-source and commercial applications.

## Documentation

The Crossbar.io [documentation](https://github.com/crossbario/crossbar/wiki) is licensed under a [Creative Commons](http://creativecommons.org/) license: the [CC BY-SA 3.0](http://creativecommons.org/licenses/by-sa/3.0/).

# Trademarks

"WAMP", "Crossbar.io" and "Tavendo" are trademarks of Tavendo GmbH.

The Crossbar.io symbol

![](legal/crossbar_icon.png)

and the Crossbar.io logo

![](legal/crossbar_text_vectorized.png)

and the Crossbar.io extended logo

![](legal/crossbar_icon_and_text_vectorized.png)

are design marks of Tavendo.

All rights to above trademarks remain with Tavendo and any use of these requires prior written agreement by Tavendo.

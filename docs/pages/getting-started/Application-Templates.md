[Documentation](.) > Application Templates

# Application Templates

Crossbar.io offers the possibility to initialize a Crossbar.io instance using an **application template**. Using these, on startup Crossbar runs a small demo application which allows you to check that everything is working properly and gives you a basis for hacking your own applications.

## Available Templates

Once you've installed Crossbar, you can get a list of the available application templates by doing

    crossbar templates

The 'default' template sets up Crossbar.io with a WebSocket transport and a static Web server. Just doing `crossbar init` without any further arguments uses the default template.

The 'Hello' templates show both RPC and PubSub functionality. A backend offers a simple addition as a procedure to be called, and publishes a counter as a PubSub event. A HTML5 frontend, served by Crossbar's integrated Web server, calls the procedure, and subscribes to the counter event.

The backend is available for the following languages & runtimes:

* Python (using [Autobahn|Python](http://autobahn.ws/python))
* Node.js (using [Autobahn|JS](http://autobahn.ws/js))
* C++ (using [Autobahn|CPP](http://autobahn.ws/cpp))
* C# (using [WampSharp](https://github.com/Code-Sharp/WampSharp))
* Erlang (using [Erwa](https://github.com/bwegh/erwa))
* PHP (using [Thruway](https://github.com/voryx/Thruway))
* Java (using [jawampa](https://github.com/Matthias247/jawampa))
* JavaScript on the [Tessel](https://tessel.io/) microcontroller

## Initializing an application template

To initialize a Crossbar instance with an application template, do

    crossbar init --template [template-name]

This creates the Crossbar configuration and copies the necessary files into the present directory.

You can additionally use the option to create a subdirectory and to do the initialization in this

    crossbar init --template [template-name] --appdir [name-of-subdirectory]

Once you've initialized the Crossbar instance, depending on the template, you may have to do some additional, language-dependent setup for the backend component. You'll find instructions for this in the console output of the above init command.

After you've finished with setup, you can start Crossbar.io it from within the directory by

    crossbar start

Once Crossbar has started you can access the HTML5 client under `http://localhost:8080`.


## Use of templates for you own applications

All application templates are licensed either under the BSD 2-clause license or under Apache 2.0. Both licenses allow you to use the code in your own applications, including closed-source and commercial applications.


## Additional Examples and Demos

In addition to the simple 'Hello' templates, there are a lot of [examples](https://github.com/crossbario/crossbarexamples).

This ranges from simple examples which provide working code illustrating various aspects and features of using Crossbar.io to [demos](https://github.com/crossbario/crossbarexamples/tree/master/demos) mini-applications.

To use the examples or demos, just clone the repo, and do `crossbar start` in the respective folder in the repo. For the demos, there's also a launcher (do `crossbar start` in the `_demo_launcher` directory).

More information can be found on the [examples page](Examples).

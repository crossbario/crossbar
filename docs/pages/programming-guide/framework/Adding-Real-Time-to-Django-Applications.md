title: Adding Real Time to Django Applications
toc: [Documentation, Programming Guide, Adding Real Time to Django Applications]

# Adding Real-Time to Django Applications

WAMP has a [lot of potential](http://crossbario.com/blog/post/is-crossbar-the-future-of-python-web-apps/), but it's asynchronous and most current Python Web stacks are synchronous.

Still, you may want to benefit from WAMP realtime notifications right now in your synchronous applications.

Crossbar.io enables you to trigger realtime notifications from your synchronous Python Web stack since it comes with a HTTP Pusher service: just configure a few lines of JSON in the Crossbar.io config file, and Crossbar.io provides a HTTP REST endpoint so that you can publish to a WAMP topic with a simple POST request.

```javascript
"transports": [
    {
       "type": "web",
       "endpoint": {
          "type": "tcp",
          "port": 8080
       },
       "paths": {
          ...
          "notify": {
             "type": "pusher",
             "realm": "realm1",
             "role": "anonymous"
          }
       }
    }
]
```

Publishing to an example topic "great_topic" is then just:


```python
import requests
requests.post("http://router_ip/notify",
                  json={
                      'topic': 'great_topic'
                      'args': [some, params, to, pass, along, if, you, need, to]
                  })
```

This sends a POST request to an endpoint at the path `notify`, and Crossbar.io dispatches a WAMP PubSub event based on it.

In order to illustrate this, I'm going to show you how to build a little monitoring service with Crossbar.io and Django. To follow this article, you'll need:

* a basic knowledge of JS.
* an understanding of the basic WAMP concepts.
* to know how to install Python 2.7 libs with C extensions on your machine.
* to know Django. (Even if the concepts of the tutorial apply to Flask, Pyramid and others.)

You can get the source code from the [Crossbar.io examples repo](https://github.com/crossbario/crossbarexamples/tree/master/django/realtimemonitor).

First steps
============

Our goal is to have a little WAMP monitoring client that we run on each machine we wish to monitor. It will retrieve CPU, RAM and disk usage every X seconds and then publish this data using WAMP.

The client will talk to a server with a Django Website containing a model for each monitored machine, with values to say whether we are interested in the CPU, the RAM or the disk usage, and the currently set publishing interval for the data.

A web page displays all readings for all machines in real time. When we change a model in the Django admin, the page reflects the change immediately.

So, we will need Django

```sh
pip install django
```

requests

```sh
pip install requests
```

and [psutil](http://pythonhosted.org/psutil/)

"psutil" is the Python lib which will enable us to retrieve all the values for the RAM, the disk and the CPU. It uses C extensions, so you'll need a compiler and Python headers. Under Ubuntu, you'll need to do:


```sh
sudo apt-get install gcc python-dev
```

For CentOS, that would be:

```sh
yum groupinstall "Development tools"
yum install python-devel
```

In Mac, Python headers should be included, but you'll need GCC. If you have xcode, you already have a compiler, otherwise, there is a <a href="https://github.com/kennethreitz/osx-gcc-installer#readme">light installer</a> for it.

Windows installer is a wheel, so you don't need to do anything in particular.

Then you can

```sh
pip install psutil
```

At last, we will need to [install Crossbar.io](/docs/Installation/). The basic install can be done by doing

```sh
pip install crossbar
```
but note that Windows users will need to install [PyWin32](http://sourceforge.net/projects/pywin32/files/pywin32/Build%20219/) first. Also, as usual, make sure you got your Python installation directories added in your system PATH otherwise none of the commands will be found.

The HTML
========

The monitoring front end is just a single page. Since this article is framework agnostic, it's written using pure JS, not jQuery or AngularJS, which makes it verbose.

```html

<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />

    <!-- Some style to easily hide a block -->
    <style type="text/css">
        .hide {display:none;}
    </style>

    <!--
        The JS lib allowing to speak WAMP.

        Here I'm assuming we are using a browser with Websocket support.
        It's possible to fall back to flash or long poll, but that
        would require additional dependencies.

        library can be found at https://github.com/crossbario/autobahn-js-built
    -->
    <script src="autobahn.min.jgz"
           type="text/javascript"></script>


    <!-- All our client code, inlined for easy reading -->
    <script type="text/javascript">

      /* When the page is loaded, run our code. */
      window.addEventListener("load", function(){

        /* Connection configuration to our WAMP router */
        var connection = new autobahn.Connection({
           url: 'ws://127.0.0.1:8080/ws',
           realm: 'realm1'
        });

        /* When the connection is opened, execute this code */
        connection.onopen = function(session) {

          var clients = document.getElementById("clients");

          /* When we receive the 'clientstats' event, run this function */
          session.subscribe('clientstats', function(args){
            var stats = args[0];
            var serverNode = document.getElementById(stats.ip);

            /*
                Create a LI containing a H2 and a DL for this client if
                it's not in the page already.
            */
            if (!serverNode){
                serverNode = document.createElement("li");
                serverNode.id = stats.ip;
                serverNode.appendChild(document.createElement("h2"));
                serverNode.appendChild(document.createElement("dl"));
                serverNode.firstChild.innerHTML = stats.name + " (" + stats.ip + ")";
                clients.appendChild(serverNode);

                // Hide the informations for this machine if it's been
                // disabled.
                session.subscribe('clientconfig.' + stats.ip, function(args){
                    var config = args[0];
                    if (config.disabled){
                        var serverNode = document.getElementById(config.ip);
                        serverNode.className = "hide";
                    }
                });

            }

            // Reset the client's LI content
            serverNode.className = "";
            var dl = serverNode.lastChild;
            while (dl.hasChildNodes()) {
                dl.removeChild(dl.lastChild);
            }

            // If we got CPU data, display it
            if (stats.cpus){
                var cpus = document.createElement("dt");
                cpus.innerHTML = "CPUs:";
                dl.appendChild(cpus);
                for (var i = 0; i < stats.cpus.length; i++) {
                    var cpu = document.createElement("dd");
                    cpu.innerHTML = stats.cpus[i];
                    dl.appendChild(cpu);
                };
            }

            // If we got disk usage data, display it
            if (stats.disks){
                var disks = document.createElement("dt");
                disks.innerHTML = "Disk usage:";
                dl.appendChild(disks);
                for (key in stats.disks) {
                    var disk = document.createElement("dd");
                    disk.innerHTML = "<strong>" + key + "</strong>: " + stats.disks[key];
                    dl.appendChild(disk);
                };
            }

            // If we got memory data, display it
            if (stats.memory){
                var memory = document.createElement("dt");
                memory.innerHTML = "Memory:";
                dl.appendChild(memory);
                var memVal = document.createElement("dd");
                memVal.innerHTML = stats.memory;
                dl.appendChild(memVal);
            }

          });

        };

        // Open the WAMP connection with the router.
        connection.open();

      });
    </script>

    <title> Monitoring</title>
</head>
<body>
    <h1> Monitoring </h1>
    <ul id="clients"></ul>
</body>

</html>
```

As you can see, most of it is ordinary JS, and DOM manipulations. The only WAMP specific parts are:

```javascript
var connection = new autobahn.Connection({
           url: 'ws://127.0.0.1:8080/ws',
           realm: 'realm1'
        });
connection.onopen = function(session) {
...
}
connection.open();
```

which etablishes the connection to the router, and

```javascript
session.subscribe('clientstats', function(args){
...
}
```

which subscribes us to the topic `clientstats` and provides the function to extecute on each WAMP publication to this topic.

Client monitoring
==================

This is the code that will run on each machine we want to monitor:

```python
# -*- coding: utf-8 -*-

from __future__ import division

import socket

import requests
import psutil

from autobahn.twisted.wamp import Application
from autobahn.twisted.util import sleep

from twisted.internet.defer import inlineCallbacks

def to_gib(bytes, factor=2**30, suffix="GiB"):
    """ Convert a number of bytes to Gibibytes

        Ex : 1073741824 bytes = 1073741824/2**30 = 1GiB
    """
    return "%0.2f%s" % (bytes / factor, suffix)

def get_stats(filters={}):
    """ Returns the current values for CPU/memory/disk usage.

        These values are returned as a dict such as:

            {
                'cpus': ['x%', 'y%', etc],
                'memory': "z%",
                'disk':{
                    '/partition/1': 'x/y (z%)',
                    '/partition/2': 'x/y (z%)',
                    etc
                }
            }

        The filter parameter is a dict such as:

            {'cpus': bool, 'memory':bool, 'disk':bool}

        It's used to decide to include or not values for the 3 types of
        ressources.
    """

    results = {}

    if (filters.get('show_cpus', True)):
        results['cpus'] = tuple("%s%%" % x for x in psutil.cpu_percent(percpu=True))

    if (filters.get('show_memory', True)):
        memory = psutil.phymem_usage()
        results['memory'] = '{used}/{total} ({percent}%)'.format(
            used=to_gib(memory.used),
            total=to_gib(memory.total),
            percent=memory.percent
        )

    if (filters.get('show_disk', True)):
        disks = {}
        for device in psutil.disk_partitions():
            # skip mountpoint not actually mounted (like CD drives with no disk on Windows)
            if device.fstype != "":
                usage = psutil.disk_usage(device.mountpoint)
                disks[device.mountpoint] = '{used}/{total} ({percent}%)'.format(
                    used=to_gib(usage.used),
                    total=to_gib(usage.total),
                    percent=usage.percent
                )
        results['disks'] = disks

    return results

# We create the WAMP client.
app = Application('monitoring')

# This is my set to localhost to enable running a first
# test client instance on the machine that Crossbar.io & Django
# are running on. You should change this value
# to the pulbic IP of the machine for external clients.
SERVER = '127.0.0.1'

# First, we use a trick to know the public IP for this
# machine.
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(("8.8.8.8", 80))
# We attach a dict to the app, so that its
# reference is accessible from anywhere.
app._params = {'name': socket.gethostname(), 'ip': s.getsockname()[0]}
s.close()


@app.signal('onjoined')
@inlineCallbacks
def called_on_joinded():
    """ Loop sending the state of this machine using WAMP every x seconds.

        This function is executed when the client joins the router, which
        means it's connected and authenticated, ready to send WAMP messages.
    """
    print("Connected")

    # Then we make a POST request to the server to notify it we are active
    # and to retrieve the configuration values for our client.
    response = requests.post('http://' + SERVER + ':8080/clients/', data={'ip': app._params['ip']})
    if response.status_code == 200:
        app._params.update(response.json())
    else:
        print("Could not retrieve configuration for client: {} ({})".format(response.reason, response.status_code))


    # The we loop for ever.
    print("Entering stats loop ..")
    while True:
        print("Tick")
        try:
            # Every time we loop, we get the stats for our machine
            stats = {'ip': app._params['ip'], 'name': app._params['name']}
            stats.update(get_stats(app._params))

            # If we are requested to send the stats, we publish them using WAMP.
            if not app._params['disabled']:
                app.session.publish('clientstats', stats)
                print("Stats published: {}".format(stats))

            # Then we wait. Thanks to @inlineCallbacks, using yield means we
            # won't block here, so our client can still listen to WAMP events
            # and react to them.
            yield sleep(app._params['frequency'])
        except Exception as e:
            print("Error in stats loop: {}".format(e))
            break


# We subscribe to the "clientconfig" WAMP event.
@app.subscribe('clientconfig.' + app._params['ip'])
def update_configuration(args):
    """ Update the client configuration when Django asks for it. """
    app._params.update(args)


# We start our client.
if __name__ == '__main__':
    app.run(url="ws://%s:8080/ws" % SERVER, debug=False, debug_wamp=False)

```

`app = Application('monitoring')` creates a WAMP client, and `@app.signal('onjoined')` tells us how to start the function when our client is connected and ready to send events. `@inlineCallbacks` is a specific feature of Twisted allowing us to write asynchronous code without using explicit callbacks everywhere: instead of them, we use `yield`.

All the work of our client happens in the loop: `app.session.publish('clientstats', infos)` publishes new stats for the CPU/RAM/Disk via WAMP, then waits for some time (`yield sleep(app._params['frequency']`) before doing it again. Waiting is not blocking, thanks to the `sleep()` from Twisted.

Let's not forget:

```python
@app.subscribe('clientconfig.' + app._params['ip'])
def update_configuration(args):
    app._params.update(args)
```

The `update_configuration()` function is called every time a WAMP publication is made to the topic "clientconfig.&lt;client_ip&gt;". Our function only updates the client configuration, which is a dict, looking like:

```python
{'cpus': True,
'memory': False,
'disk': True,
'disabled': False,
'frequency': 1}
```

It's this dict which is used by `get_stats()` to choose which values to retrieve, and also in the loop to know how many seconds to wait until the next measurements or if we send the stats at all.

The initial value for this dict is retrieved when the client starts, by doing:

```python
app._params.update(requests.post('http://' + SERVER + ':8080/clients/',
                                    data={'ip': app._params['ip']}).json())
```

`requests.post(server_url, data={'ip': app._params['ip']}).json()` does a POST request to a Django URL which we'll see later, returning the client's configuration matching this IP, as JSON.

We use HTTP once to get the values at the beginning, then WAMP for all future udpates. WAMP and HTTP are not excluding each other: they are complementary.

A little digression:

```python
SERVER = '192.168.0.104'

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(("8.8.8.8", 80))
app._params = {'name': socket.gethostname(), 'ip': s.getsockname()[0]}
s.close()
```

As you can see I hard coded the IP of the Crossbar.io and Django server out of pure laziness. But in production this should, obviously, be a parameter or an environment variable.

Remember you can get this IP on Linux and Mac doing (from the server machine):

```sh
ifconfig
```

And on Windows:

```sh
ipconfig
```

Then, since I need to identify my client, I do it with its IP address too. So I need its public IP, which I get by using a little trick involving opening a connection to some reliable external IP (here the Google DNS 8.8.8.8) and by closing it right after that. This lets me know how other machines see me from the outside world.

<h2>The Django Web site</h2>

Since this article requires that you know Django, this will be easier.

We create a project and an app:

```sh
django-admin startproject django_project
./manage.py startapp django_app
```

And we add the app to `settings.INSTALLED_APPS`.

Then we write a small model containing the configuration for each client (remember our dict ? This is where it comes from):

```python
# -*- coding: utf-8 -*-

import requests

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.forms.models import model_to_dict


class Client(models.Model):
    """ Our client configuration """

    # Client unique identifier
    ip = models.GenericIPAddressField()

    # What data to send to the dashboard
    show_cpus = models.BooleanField(default=True)
    show_memory = models.BooleanField(default=True)
    show_disk = models.BooleanField(default=True)

    # Stop sending data
    disabled = models.BooleanField(default=False)

    # Data refresh frequency
    frequency = models.IntegerField(default=1)

    def __unicode__(self):
        return self.ip


@receiver(post_save, sender=Client, dispatch_uid="server_post_save")
def notify_server_config_changed(sender, instance, **kwargs):
    """ Notifies a client that its config has changed.

        This function is executed when we save a Client model, and it
        makes a POST request on the WAMP-HTTP bridge, allowing us to
        make a WAMP publication from Django.
    """
    requests.post("http://127.0.0.1:8080/notify",
                  json={
                      'topic': 'clientconfig.' + instance.ip,
                      'args': [model_to_dict(instance)]
                  })
```

The model part is known territory. The fun part is actually:

```python
@receiver(post_save, sender=Client, dispatch_uid="server_post_save")
def notify_server_config_changed(sender, instance, **kwargs):
    requests.post("http://127.0.0.1:8080/notify",
                  json={
                      'topic': 'clientconfig.' + instance.ip,
                      'args': [model_to_dict(instance)]
                  })
```

Here we use Django signals, a framework feature allowing us to trigger a function when something happens. In our case, we say 'run this function when one Client model is modified'.

So `notify_server_config_changed()` is executed when a client configuration is modified, such as when using the Django admin, and will receive the modified object as the "instance" parameter.

Now we make a small POST request to `http://127.0.0.1:8080/notify`, which is the URL we will later use to configure our PUSH service. By doing a request to it, we are asking Crossbar.io to turn this HTTP request into a WAMP publication about the 'clientconfig.&lt;client_ip&gt;' topic. For all intents and purposes, we are publishing a WAMP message from Django.

This works from anywhere, not just Django. From the shell, from Flask, from any place you can make an HTTP request you can publish using the Crossbar.io push service.

The message we sent is going to be received by our clients, whereever they are, since they are all connected to the same WAMP router. Indeed, our client did:

```python
@app.subscribe('clientconfig.' + app._params['ip'])
def update_configuration(args):
    app._params.update(args)
```

So it will receive the message, the content of `args`: `[model_to_dict(instance)]`, meaning the new configuration which has just changed in the data base. This way it can update itself immediately.

To illustrate this, we add the model in our Django admin:

```python
from django.contrib import admin

# Register your models here.

from django_app.models import Client

admin.site.register(Client)
```

Doing this makes the client configurations editable from the Django admin, and when clicking the "save" button, it sends our WAMP publication, which triggers the right client update.

The rest is just small tweaks:

```python
# -*- coding: utf-8 -*-

import json

from django.http import HttpResponse
from django_app.models import Client
from django.views.decorators.csrf import csrf_exempt
from django.forms.models import model_to_dict

@csrf_exempt
def clients(request):
    """ Retrieve a client config from DB and send it back to the client """
    ip = request.POST.get('ip', None)
    try:
        client, created = Client.objects.get_or_create(ip=ip)
        data = model_to_dict(client)
    except Exception as e:
        print("Could not retrieve client config for IP '{}': {}".format(ip, e))
    else:
        print("Client config for retrieved for IP '{}'".format(ip, data))
        return HttpResponse(json.dumps(data), content_type='application/json')
```

We disable the CSRF protection for the demo, but once again, in production, you should do that in a clean way, with `@login_required `, protected views and CSRF token exchanges.

This view retrieves the client configuration matching this IP (creating it if needed), and returns it as JSON. Remember, this allows our client to do:

```python
app._params.update(requests.post('http://' + SERVER + ':8080/clients/',
                                    data={'ip': app._params['ip']}).json())
```

So at startup it declares itself in the database, and gets its config back.

You plug all the moving parts in urls.py:

```python
from django.conf.urls import patterns, include, url
from django.contrib import admin
from django.views.generic import TemplateView

urlpatterns = patterns('',
    url(r'^admin/', include(admin.site.urls)),
    url(r'^clients/', 'django_app.views.clients'),
    url(r'^$', TemplateView.as_view(template_name='dashboard.html')),
)
```

This contains the routes for the admin, our new view, and some generic code to serve the HTML we saw at the beginning of this article.

Then you need to create your database and collect static files :

```sh
./manage.py syncdb
./manage.py collectstatic
```

Crossbar.io
===========

Finally, we just need to configure Crossbar.io. On the command line go to your project's base directory and do

```
crossbar init
```

This creates the `.crossbar` directory which contains a `config.json` file. We need to edit this to look like:

```javascript
{
   "workers": [
      {
         "type": "router",
         "options": {
            "pythonpath": [".."]
         },
         "realms": [
            {
               "name": "realm1",
               "roles": [
                  {
                     "name": "anonymous",
                     "permissions": [
                        {
                           "uri": "*",
                           "allow": {
                              "publish": true,
                              "subscribe": true,
                              "call": true,
                              "register": true
                           }
                        }
                     ]
                  }
               ]
            }
         ],
         "transports": [
            {
               "type": "web",
               "endpoint": {
                  "type": "tcp",
                  "port": 8080
               },
               "paths": {
                  "/": {
                     "type": "wsgi",
                     "module": "django_project.wsgi",
                     "object": "application"
                  },
                  "ws": {
                     "type": "websocket",
                     "debug": false
                  },
                  "notify": {
                     "type": "pusher",
                     "realm": "realm1",
                     "role": "anonymous"
                  },
                  "static": {
                     "type": "static",
                     "directory": "../static"
                  }
               }
            }
         ]
      }
   ]
}
```

The first part is more or less Crossbar.io's equivalent of chmod 777:

```javascript
 "type": "router",
         "realms": [
            {
               "name": "realm1",
               "roles": [
                  {
                     "name": "anonymous",
                     "permissions": [
                        {
                           "uri": "*",
                           "allow":{
                              "publish": true,
                              "subscribe": true,
                              "call": true,
                              "register": true
                           }
                        }
                     ]
                  }
               ]
            }
         ]
```

"Set me up a router with an access named 'realm1' authorizing anonymous clients to do anything". A realm is security notion in Crossbar.io used to isolate connected clients and give them permissions, but we are going to put them all in the same realm to make the demo simple.

Then we add transports for each desired technology. We are going to group them all under the "8080" port as Twisted can listen to HTTP and Websocket on a single port at the same time.

```javascript
"transports": [
{
   "type": "web",
   "endpoint": {
      "type": "tcp",
      "port": 8080
   }
```

The root URL will serve our Django app:

```javascript
"/": {
 "type": "wsgi",
 "module": "django_project.wsgi",
 "object": "application"
}
```

Yes, Crossbar.io can server your Django app. It's not mandatory, but it will exempt you from needing Gunicorn and Nginx. The Web server in Twisted can take a real life traffic load without problems.

For our example, we use Crossbar.io for everything, making the setup easier. To do that, we just need to tell it which variable (application) from which WSGI file (django_project/wsgi.py) to load.

On '/ws', we listen for Websocket traffic:

```javascript
"ws": {
 "type": "websocket"
}
```

This is where WAMP comes in, and that's why our clients connect to the router by doing `app.run(url="ws://%s:8080/ws" % SERVER)` and `autobahn.Connection({url: 'ws://127.0.0.1:8080/ws', realm: 'realm1'})`.

Then, '/notify' is for our WAMP-HTTP bridge:

```javascript
"notify": {
     "type": "pusher",
     "realm": "realm1",
     "role": "anonymous"
  }
```

All anonymous clients from `realm1` can use the HTTP REST endpoint created by this. It's thanks to this that we were able to do this in our Django signal:

```python
requests.post("http://127.0.0.1:8080/notify",
                  json={
                      'topic': 'clientconfig.' + instance.ip,
                      'args': [model_to_dict(instance)]
                  })
```

and publish a WAMP message via a HTTP POST.

At last, we serve Django static files:

```javascript
"static": {
 "type": "static",
 "directory": "../static"
}
```

Now that everything is in place, we can start Crossbar.io:

```sh
crossbar start
```

Let's visit http:127.0.0.1:8080/ to see your Django template dashboard.The HTML comes to life!

For each machine running a client (`python client.py`), new stats appear on the dashboard, and are be updated in real time. (Remember to change the server IP to the one your Django/Crossbar.io instance are on!)

Now if you open a new tab to http:127.0.0.1:8080/admin/ and change a client's configuration, our client adapts, and our dashboard updates automatically.

<h2>Last words</h2>

In the end our project looks like this:

```sh
.
client.py
.crossbar
    config.json
db.sqlite3
django_app
    admin.py
    __init__.py
    models.py
    templates
        dashboard.html
    views.py
django_project
    __init__.py
    settings.py
    urls.py
    wsgi.py
static
manage.py
```

You can get the source code from the [Crossbar.io examples repo](https://github.com/crossbario/crossbarexamples/tree/master/django/realtimemonitor).

As you can see, we used very little WAMP code: a few lines for the JS part, and a few lines for the Python client. The only thing linking WAMP to Django is the Crossbar.io configuration which adds the HTTP pusher service and our POST request in `models.py`.

This solution is not limited to Django, and works well for all synchronous technologies unable to run WAMP clients directly. For now, the HTTP-WAMP bridge only allows publishes, not subscriptions or RPC. But having real time notifications available everywhere is already a nice touch, and the other actions will be implemented by the Crossbar.io team in the near future.

At moment you can already see that we can mix HTTP, WAMP, Python, clients, servers and build our own architecture to fit our needs. Crossbar.io can also serve the WSGI app, and actually could manage any WAMP client life cycle on the same machine, or if needed, any command line process (such as NodeJS).

We could have written the client in Python 3 since it's on other machines. In fact, if we run Django by itself (not using Crossbar.io), then Django can be coded using Pyton 3 too. Crossbar.io is the only bit still needing Python 2.7 (because Twisted doesn't run on Python 3 yet). Still, this is just a component which we configure and then forget about.

I tried this small system with several docker images running Python clients inside them and it's great to see the machines being added in real time. The immediate feedback you get by seeing any changes applied to the Django admin reflected on the page is also a nice touch.

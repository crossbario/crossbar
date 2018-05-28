title: Setup on Heroku
toc: [Documentation, Installation, Setup on Heroku]

# Setup on Heroku

[Heroku](https://www.heroku.com/) is a Platform-as-a-Service cloud vendor that allows to run applications in so-called *Dynos*, which are like glorified [OS containers](http://en.wikipedia.org/wiki/Operating_system%E2%80%93level_virtualization).

## Application Setup

Crossbar.io can be run on Heroku. Here we describe what you need to do.
This walkthrough assumes that you have created an account on Heroku and have installed the Heroku tool belt.

To sign up for a free Heroku account go [here](https://signup.heroku.com/).

Once you've created an account install the Heroku toolbelt. You can find the tool belt [here](https://toolbelt.heroku.com/).

Heroku also has very thorough [walkthroughs](https://devcenter.heroku.com/start) for creating apps using a variety of languages.

Installing a Crossbar.io project on Heroku is pretty straightforward once you're familiar with the above but here is a step by step guide in case you need some extra guidance.

1. Create project folder
2. Create virtual environment (Optional but strongly recommended): You can find out more about virtual environments [here](http://docs.python-guide.org/en/latest/dev/virtualenvs/) to create a virtual environment:
	1. Install virtual env: If you haven't already, install virtualenv through pip: `pip install virtualenv`
	2. Go to your project: Open a terminal window and navigate to your project folder: `cd my_project`
	3. Create the virtual environment: `virtualenv venv`
	4. Activate the virtual environment: `source venv/bin/activate`
3. Install Crossbar: `pip install crossbar`
4. Create project (hello:python template): `crossbar init --template hello:python`
6. Freeze requirements: Create a requirements file  so that Heroku knows what to install for your project: `pip freeze > requirements.txt`
7. Create Procfile: Heroku uses a Procfile to determine what commands to use to start your app: `echo "web: crossbar start" > Procfile`
9. Modify Config file: Heroku uses a dynamic urls and ports so you'll need to use config file like the one described in the Crossbar.io configuration below (or copy the one below). You can find your config file in the `.crossbar` directory of your project folder (assuming you followed the steps above)
10. Create git repo: You deploy to Heroku via Git. If you don't have Git installed you can find out how to do so [here](http://git-scm.com/book/en/v2/Getting-Started-Installing-Git). To create a git repository:
	1. `cd my_project_path`
	2. `git init`
	3. `git add .`
	4. `git commit -m "Initial commit"`
11. Create the app on Heroku: Now you should be all set to create an instance of the app: `heroku create` (NOTE: check the output of this command, on the second line it will tell you the URL of your app - it should be something like `random-heroku-assigned-name.herokuapp.com`. You can also find it through your account page on Heroku)
12. Deploy: to deploy and start the app you push it using Git and Heroku should take care of the rest: `git push heroku master`
13. You can check the logs of your application once it's deployed by using the logs command: `heroku logs --tail`
14. Point your browser to the address that Heroku assigned to your app and you should see the Hello WAMP! page (see the hello:python template for more information). (NOTE: Use `http` instead of `https` to access the page.)

## Crossbar.io configuration

Crossbar.io can create a complete node configuration and "Hello, world". Here is how you would create a Python based "Hello, world" application:

    crossbar init --template hello:python

The configuration generated will make Crossbar.io listen on the *fixed* port 8080 for incoming Web and WebSocket connections.

However, Heroku does not allow to expose *fixed* ports from Dynos to the outside world, but routes HTTP (and WebSocket) request coming in from the Internet via a Heroku frontend load-balancer to Dynos - to a **dynamically assigned port**. Read more [here](https://devcenter.heroku.com/articles/http-routing).

When a Dyno starts, the Dyno will get assigned an externally visible port, and inside the Dyno, the environment variable `PORT` will allow you to access the assigned port number.

Because of this, we need to modify the Crossbar.io node configuration:

1. In the Web transport, insted of `8080`, we configure the value `"$PORT"`. This will make Crossbar.io read the value dynamically upon startup from the environment variable.
2. Since the main transport is now listening on a dynamic port, we start a second (WebSocket) transport on our router on fixed port `9000` for the container worker to connect to

Here is a complete, working configuration:

```json
{
    "controller": {
    },
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
                               "call": true,
                               "register": true,
                               "publish": true,
                               "subscribe": true
                            }
                         }
                      ]
                   }
                ]
             }
          ],
          "transports": [
             {
                "type": "websocket",
                "endpoint": {
                   "type": "tcp",
                   "port": 9000
                }
             },
             {
                "type": "web",
                "endpoint": {
                   "type": "tcp",
                   "port": "$PORT"
                },
                "paths": {
                   "/": {
                      "type": "static",
                      "directory": "../hello/web"
                   },
                   "ws": {
                      "type": "websocket"
                   }
                }
             }
          ]
       },
       {
          "type": "container",
          "options": {
             "pythonpath": [".."]
          },
           "components": [
             {
                "type": "class",
                "classname": "hello.hello.AppSession",
                "realm": "realm1",
                "transport": {
                   "type": "websocket",
                   "url": "ws://127.0.0.1:9000",
                   "endpoint": {
                      "type": "tcp",
                      "host": "127.0.0.1",
                      "port": 9000
                  }
                }
             }
          ]
       }
    ]
}
```

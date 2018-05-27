title: CGI Script Service
toc: [Documentation, Administration, Web Services, CGI Script Service]

# CGI Script Service

Crossbar.io's Web server allows you to serve plain old CGI scripts. This can be useful if you have some legacy or other scripts that you want to run as part of a Crossbar.io node.

## Configuration

To configure a CGI Script Service, attach a dictionary element to a path in your [Web transport](Web Transport and Services):

attribute | description
---|---
**`type`** | Must be `"cgi"`.
**`directory`** | The CGI base directory containing your scripts. The path can be absolute or relative to the Crossbar.io node directory
**`processor`** | The CGI script processor to use. This MUST be a fully qualified path to an executable.


## Example

Here is a complete example. First, create a new Crossbar.io node

    cd ~
    mkdir test1
    cd test1
    crossbar init

Now activate CGI. Add the following snippet to configuration file at **~/test1/.crossbar./config.json**

```javascript
"myscripts": {
   "type": "cgi",
   "directory": "../cgi",
   "processor": "/usr/bin/python"
}
```

so your complete configuration file looks like

```javascript
{
   "type": "web",
   "endpoint": {
      "type": "tcp",
      "port": 8080
   },
   "paths": {
      "/": {
         "type": "static",
         "directory": ".."
      },
      "ws": {
         "type": "websocket",
         "url": "ws://localhost:8080/ws"
      },
      "myscripts": {
         "type": "cgi",
         "directory": "../cgi",
         "processor": "/usr/bin/python"
      }
   }
}
```

This configuration starts a Web Transport that includes a CGI processor on a subpath.

Now create an example CGI directory `~/test1/cgi` and create a script file `~/test1/cgi/foo` with this contents:

```python
import sys

print("Content-Type: text/html\n\n")

print("""<!doctype html>
<html>
   <body>
      <p>This is {} running {}</p>
   </body>
</html>
""".format(sys.executable, __file__))
```

Then start Crossbar.io

    crossbar start

and open the page `http://localhost:8080/myscripts/foo` in your browser. You should see a hello from the Python CGI script.

---

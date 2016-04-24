[Documentation](.) > [Administration](Administration) > [Web Services](Web Services) > Static Web Service

# Static Web Service

When serving HTML5 Web clients from Crossbar.io, the **static web assets** for your frontends like HTML, JavaScript and image files need to be hosted somewhere as well.

You can host static content on your existing (external) Web server or a static hosting service like Amazon S3. It does not matter if your Crossbar.io nodes reside on domain names different from the static content.

But you can also let Crossbar.io host the static assets. This is useful and convenient, since you then don't need an external Web server just to serve your static content.

## Configuration

The **Static Web Service** is configured on a subpath of a **Web Transport** and allows to expose static Web content.

The Web content served can come from two sources:

* directories on the filesystem
* resources within Python packages

To configure a Static Web Service, attach a dictionary element to a path in your [Web transport](Web Transport and Services):

attribute | description
---|---
**`type`** | must be `"static"`
**`directory`** | absolute or node relative directory to serve files from or `null` when serving a Python resource (see next)
**`package`** | when serving a Python resource, the Python package name the resource comes from
**`resource`** | the resource name as exported by the referenced Python package - the imported resource is then used as a file source
**`options`** | dictionary with options (see below)

> either the `directory` attribute must be present or both the `package` and `resource` attributes, not both, and not none.

with `options`:

option | description
---|---
**`enable_directory_listing`** | set to `true` to enable rendering of directory listings (default: **false**). If a file `index.html` is present in the directory, this will render instead of the listing.
**`mime_types`** | a dictionary of (additional) MIME types to set, e.g. `{".jgz": "text/javascript", ".svg": "image/svg+xml"}` (default: **{}**)
**`cache_timeout`** | int


## Example - Serving from Directories

Here is an example **Web Transport** configuration that includes a **Static Web Service**:

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
      }
   }
}
```

This will make the subpath **/ws** into a WebSocket transport. All other paths (other than **/ws**) will serve static assets from the directory specified. The directory path can be absolute or relative to the node directory (`.crossbar`). Unless a HTML file is specified, the server will attempt to serve a file "index.html" from the specified directory.

A **Static Web Service** has a couple of options you can configure using an `options` dictionary:

```javascript
"/": {
   "type": "static",
   "directory": "..",
   "options": {
      "enable_directory_listing": true,
      "mime_types": {
         ".svg": "image/svg+xml"
      }
   }
}
```

You can also put (another) **Static Web Service** on a **subpath** serving assets from a directory and this directory can be different from the base directory of the containing **Web Transport**:

```javascript
"paths": {
   "/": {
      "type": "static",
      "directory": ".."
   },
   "ws": {
      "type": "websocket"
   },
   "download": {
      "type": "static",
      "directory": "/var/download"
   }
}
```

Here, the **Web Transport** has it's base path `/` configured to be `static` and pointing to directory `..` relative to the node directory. Whereas the *subpath* `download` is configured to be of type `static` and pointing to the directory `/var/download`.

---

## Example - Serving from Python Packages

Python packages can contain "resources" (non-Python file assets) and the **Static Web Service** can serve assets directly from any Python package installed (in the Python installation that Crossbar.io runs from).

Say you are creating a **`foobar`** package that contains static Web resources:

```text
setup.py
MANIFEST.in
foobar/__init__.py
foobar/web/index.html
```

with the 4 files having the following contents:

**`setup.py`**:

```python
from setuptools import setup

setup(
   name = 'foobar',
   version = '0.0.1',
   packages = ['foobar'],
   include_package_data = True,
   zip_safe = False
)
```

**`MANIFEST.in`**:

```text
recursive-include foobar/web *
```

**`foobar/__init__.py`**:

```python
__version__ = '0.0.1'
```

**`foobar/web/index.html`**:

```html
<!doctype html>
<html>
   <body>
      <h1>The awesome Foobar content</h1>
   </body>
</html>
```

After installing the package locally (`python setup.py install`), you can configure your resources to be served like this:

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
         "package": "foobar",
         "resource": "web"
      },
      "ws": {
         "type": "websocket",
         "url": "ws://localhost:8080/ws"
      }
   }
}
```

When you start Crossbar.io, you should see log lines similar to:

```console
...
2014-03-20 10:37:28+0100 [Worker 3528] Loaded static Web resource 'web' from module 'foobar 0.0.1' (filesystem path c:\Python27\lib\site-packages\foobar-0.0.1-py2.7.egg\foobar\web)
2014-03-20 10:37:28+0100 [Worker 3528] Site starting on 8080
...
```

Point your browser to `http://localhost:8080`. You should see an "awesome" message;)

Note that you can also put (another) **Static Web Service** on a **subpath** serving assets from a Python package resource.

---

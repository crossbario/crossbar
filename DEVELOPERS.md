# Developer Guide

This guide is for developers of the Crossbar.io code itself, not for application developers creating Crossbar.io based applications.

## Roadmap

### 0.11.0

[Milestone for 0.11.0](https://github.com/crossbario/crossbar/milestones/0.11.0)

* **Python 3** - Crossbar.io runs on Python 3 now!
* **new logging** - All the code uses a completely new logging system. Lots of improvements to logged information amount and selection.
* **various improvements in error handling**
* **File Upload service** - A Web service that provides file upload from browser that works with large files and can be resumed.
* **Web hook service** - This feature allows Crossbar.io receive Web hook requests from Web services like GitHub and inject WAMP events. The service would work generic enough to digest requests from various Web services.
* **various bug fixes and enhancement** - Really a lot. In particular startup, shutdown and failure behavior, treatment of errors originating in user code and so on.

### 0.12.0

[Milestone for 0.12.0](https://github.com/crossbario/crossbar/milestones/0.12.0)

* **PostgreSQL integration** - This is about extending WAMP right into PostgreSQL procedural languages. The Publisher role needs some finishing touches. The Callee role we had in the past in WebMQ, and this needs to be rewritten. The Subscriber role would work similar to Callee, wheras the Caller role we can do using the HTTP bridge.
* **RawSocket ping/pong** - This is just a feature from the spec we are missing in the Autobahn implementation. And once we have it there, we need to expose the related ping/pong knobs in the config.
* **Reverse Proxy service** - This is a feature request for a Web service which can be configured on a path and provides reverse proxying of HTTP traffic to a backend server. Essentially, expose the Twisted Web resource that is available.
* **various bug fixes and enhancement**

### 0.13.0

[Milestone for 0.13.0](https://github.com/crossbario/crossbar/milestones/0.13.0)

* **Call Cancelling**
* **Timeouts at different levels**
* **Various authentication features**
* **Reflection**
* **API docs generation**
* **Payload validation**

### 0.14.0

[Milestone for 0.14.0](https://github.com/crossbario/crossbar/milestones/0.14.0)

* Multi-core support for routers (part 1: transport/routing service processes)


## Coding Style

> The rules and text here follows [Django](https://docs.djangoproject.com/en/1.8/internals/contributing/writing-code/coding-style/).

Please follow these coding standards when writing code for inclusion in Crossbar.io.

1. Unless otherwise specified, follow [PEP 8](https://www.python.org/dev/peps/pep-0008). However, remember that PEP 8 is only a guide, so respect the style of the surrounding code as a primary goal.
2. Use 4 spaces for indents.
3. Use CamelCase for classes and snake_case for variables, functions and members, and UPPERCASE for constants.
4. Everything that is not part of the public API must be prefixed with a single underscore.
5. Rules 3 and 4 apply to the public API exposed by AutobahnPython for **both** Twisted and asyncio users as well as everything within the library itself.
6. An exception to PEP 8 is our rules on line lengths. Don’t limit lines of code to 79 characters if it means the code looks significantly uglier or is harder to read. We allow up to 119 characters as this is the width of GitHub code review; anything longer requires horizontal scrolling which makes review more difficult. Documentation, comments, and docstrings should be wrapped at 79 characters, even though PEP 8 suggests 72.
7. Use hanging indents with each argument strictly on a separate line to limit line length (see also [here](http://stackoverflow.com/questions/15435811/what-is-pep8s-e128-continuation-line-under-indented-for-visual-indent/15435837#15435837) for an explanation why this is PEP8 compliant):

```python
raise ApplicationError(
    u"crossbar.error.class_import_failed",
    u"Session not derived of ApplicationSession"
)
```

Code must be checked for PEP8 compliance using [flake8](https://flake8.readthedocs.org/en/2.4.1/) with [pyflakes](https://pypi.python.org/pypi/pyflakes) and [pep8-naming](http://pypi.python.org/pypi/pep8-naming) plugins installed:

    flake8 --max-line-length=119 crossbar

There is no automatic checker for rule 4, hence reviewers of PRs should manually inspect code for compliance.

Note that AutobahnPython currently does not fully comply to above rules:

```console
(python279_1)oberstet@thinkpad-t430s:~/scm/crossbar/crossbar$ make flake8_stats
flake8 --statistics --max-line-length=119 -qq crossbar
382     E501 line too long (120 > 119 characters)
145     N802 function name should be lowercase
29      N803 argument name should be lowercase
82      N806 variable in function should be lowercase
make: *** [flake8_stats] Fehler 1
```

It also does not comply fully to rule 4. This will get addressed in the next major release (0.12).

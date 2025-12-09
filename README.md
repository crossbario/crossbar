# Crossbar.io

[![PyPI](https://img.shields.io/pypi/v/crossbar.svg)](https://pypi.python.org/pypi/crossbar)
[![Python](https://img.shields.io/pypi/pyversions/crossbar.svg)](https://pypi.python.org/pypi/crossbar)
[![CI](https://github.com/crossbario/crossbar/workflows/main/badge.svg)](https://github.com/crossbario/crossbar/actions?query=workflow%3Amain)
[![Docs](https://readthedocs.org/projects/crossbar/badge/?version=latest)](https://crossbar.readthedocs.io/en/latest/)
[![License](https://img.shields.io/pypi/l/crossbar.svg)](https://github.com/crossbario/crossbar/blob/master/LICENSE)
[![Downloads](https://img.shields.io/pypi/dm/crossbar.svg)](https://pypi.python.org/pypi/crossbar)

---

*Decentralized Middleware*

[Crossbar.io](https://crossbar.io) is an open source networking platform
for distributed and microservice applications. It implements the open
Web Application Messaging Protocol (WAMP), is feature rich, scalable,
robust and secure. Let Crossbar.io take care of the hard parts of
messaging so you can focus on your app\'s features.

## Resources

-   Download from [PyPI](https://pypi.org/project/crossbar/)
-   Read more on the [Project Homepage](https://crossbar.io)
-   Jump into the [Getting
    Started](https://crossbar.io/docs/Getting-Started/)
-   Read the reference [Documentation](https://crossbar.io/docs/)
-   Join the [User forum](https://crossbar.discourse.group/)
-   Ask a question on
    [StackOverflow](https://stackoverflow.com/questions/ask?tags=crossbar,wamp)
-   Read our [Legal
    Notes](https://github.com/crossbario/crossbar/blob/master/legal/README.md)

## Docker images

-   [amd64](https://hub.docker.com/r/crossbario/crossbar)
-   [armv7](https://hub.docker.com/r/crossbario/crossbar-armhf)
-   [armv8](https://hub.docker.com/r/crossbario/crossbar-aarch64)

## JSON Schema for Crossbar.io Configuration File Format

We now have a JSON Schema file available for **config.json**, if you\'re
using VSCode you can make use of this by adding the following to your
VSCode settings; (File -\> Preferences -\> Settings)

``` json
"json.schemas": [
    {
        "fileMatch": [
            "/config.json",
            "/.config.json"
        ],
        "url": "https://raw.githubusercontent.com/crossbario/crossbar/master/crossbar.json"
    }
],
```

Alternatively, the generic approach is to insert a \"\$schema\" line at
the top of your file;

``` json
{
    "$schema": "https://raw.githubusercontent.com/crossbario/crossbar/master/crossbar.json",
    "version": 2,
```

This file is currently experimental, but it should give you contextual
auto-completion on all Crossbar **config.json** syntax, use CTRL+Space
in VSCode to activate IntelliSense.

------------------------------------------------------------------------

*Copyright (C) 2013-2021 typedef int GmbH. All rights reserved. WAMP,
Crossbar.io and XBR are trademarks of typedef int GmbH.*

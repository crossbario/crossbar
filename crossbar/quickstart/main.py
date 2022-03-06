###############################################################################
#
# Crossbar.io Quickstart
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

import os
import uuid
import six

import click
import yaml
from cookiecutter.main import cookiecutter

from autobahn import util

README = """# Crossbar.io Quickstart Project

This project was generated using quickstart templates for Crossbar.io based services.

The services are [Docker](https://www.docker.com/) based, and the service bundling is
using [Docker Compose](https://docs.docker.com/compose/).

To build your services:

```console
make build
```

To check the service versions:

```console
make version
```

To start your services:

```console
make start
```

> Note: the latter is simply starting all services with `docker-compose up`. To start
the services in the background, type `docker-compose up --detach`.
"""

MAKEFILE = """
SUBDIRS = $(shell ls -d */)

default: start

version:
\tfor dir in $(SUBDIRS) ; do \
\t\techo "$$dir" ; \
\t\tcat $$dir/service.json ; \
\t\tmake -C  $$dir version ; \
\tdone

build:
\tdocker-compose build

# the following will automatically build the images from the Dockerfiles
# references in docker-compose.yml, and it will also rebuild those images
# and recreate containers as needed (eg when the Dockerfile or again a file
# referenced therein, such as your actual application source code files, changes)
#
start:
\tdocker-compose up --build
"""

readme_filename = 'README.md'
makefile_filename = 'Makefile'
docker_compose_filename = 'docker-compose.yml'

DEVMODE = False

if DEVMODE:
    CC1 = '/home/oberstet/scm/crossbario'
    CC2 = '/home/oberstet/scm/xbr'
else:
    CC1 = 'gh:crossbario'
    CC2 = 'gh:xbr'

# built-in cookiecutters.
#
_cookiecutters = [
    # Crossbar.io
    (None, 'Crossbar.io'),
    ('{}/cookiecutter-crossbar'.format(CC1), 'Create a Crossbar.io OSS app router'),
    ('{}/cookiecutter-crossbar-fabric'.format(CC1), 'Create a Crossbar.io app router'),
    ('{}/cookiecutter-crossbar-fabric-center'.format(CC1), 'Create a Crossbar.io cluster controller'),

    # XBR
    (None, 'XBR'),
    ('{}/cookiecutter-xbr-api'.format(CC2), 'Create a XBR API bundle'),
    ('{}/cookiecutter-crossbar-fabric-xbr'.format(CC1), 'Create a Crossbar.io XBR data market'),

    # Autobahn
    (None, 'Autobahn'),
    ('{}/cookiecutter-autobahn-python'.format(CC1), 'Create a Python based app or XBR service'),
    ('{}/cookiecutter-autobahn-js'.format(CC1), 'Create a JavaScript based app or XBR service'),
    ('{}/cookiecutter-autobahn-java'.format(CC1), 'Create a Java based app or XBR service'),
    ('{}/cookiecutter-autobahn-cpp'.format(CC1), 'Create a C++ based app or XBR service'),

    # Community project
    (None, 'Community'),
    ('{}/cookiecutter-wampsharp'.format(CC1), 'Create a WampSharp/C# based app service'),
    ('{}/cookiecutter-nexus-go'.format(CC1), 'Create a Nexus/Go based app service'),
]


def hl(text, color='yellow', bold=True):
    if not isinstance(text, six.text_type):
        text = '{}'.format(text)
    return click.style(text, fg=color, bold=bold)


def _initialize():
    if not os.path.isfile(readme_filename):
        with open(readme_filename, 'w') as fd:
            fd.write(README)
        click.echo('{} created'.format(readme_filename))

    if not os.path.isfile(makefile_filename):
        with open(makefile_filename, 'w') as fd:
            fd.write(MAKEFILE)
        click.echo('{} created'.format(makefile_filename))

    docker_compose_filename = 'docker-compose.yml'
    if not os.path.isfile(docker_compose_filename):
        docker_compose = {'version': '3.0', 'services': {}}
        with open(docker_compose_filename, 'w') as fd:
            fd.write(yaml.safe_dump(docker_compose))
        click.echo('{} created'.format(docker_compose_filename))

    docker_compose = None
    with open(docker_compose_filename) as fd:
        data = fd.read()
        docker_compose = yaml.safe_load(data)

    if not isinstance(docker_compose, dict):
        raise click.ClickException('invalid type {} found in {} for top level object'.format(
            type(docker_compose), docker_compose_filename))

    if 'services' not in docker_compose:
        raise click.ClickException(
            'no services attribute found in top level object for {}'.format(docker_compose_filename))

    return docker_compose


def run():
    click.echo('\n{cb} Project Quickstart\n'.format(cb=hl('Crossbar.io / XBR')))

    _templates = {}

    num = 0
    click.echo('  {}: Exit'.format(hl(num)))

    for template, desc in _cookiecutters:
        if template:
            num += 1
            _templates[num] = template
            template_disp = hl(template, bold=False)
            click.echo('  {num}: {desc:46s} [{template}]'.format(num=hl(str(num).ljust(3)),
                                                                 desc=desc,
                                                                 template=template_disp))
        else:
            click.echo('\n {}:\n'.format(hl(desc)))
    click.echo('')

    select = None
    while select not in range(0, num + 1):
        select = click.prompt('Please select', type=int, default='0')

    if select > 0:

        template = _templates[select]
        click.echo('Initializing cookiecutter {} ...'.format(template))

        # initialize services root directory and return contents of
        # docker-compose.py as object
        docker_compose = _initialize()

        extra_context = {
            'uid': os.getuid(),
            'service_uuid': str(uuid.uuid4()),
            'generated': util.utcnow(),
        }
        output_dir = '.'

        # cookiecutter returns the fully qualified path within which the template
        # was initialized.
        output_dir = cookiecutter(template, output_dir=output_dir, extra_context=extra_context)

        # the last part of the fully qualified output directory is the service name
        # that comes from "cookiecutter.json"
        service_name = os.path.basename(output_dir)

        # we expect the cookiecutter to produce a docker-compose-<service_name>.yml file
        service_docker_compose_filename = os.path.join(output_dir, 'docker-compose-{}.yml'.format(service_name))

        if not os.path.isfile(service_docker_compose_filename):
            raise click.ClickException(
                'docker-compose fragment for service was not generated by cookiecutter. missing file:\n{}'.format(
                    service_docker_compose_filename))

        # now load the docker-compose service fragment from the file generated by cookiecutter
        service_docker_compose = None
        with open(service_docker_compose_filename) as fd:
            data = fd.read()
            service_docker_compose = yaml.safe_load(data)

        # update the docker-compose object
        if service_name in docker_compose['services']:
            click.echo('updating service "{}" existing in docker-compose.yml'.format(service_name))
        else:
            click.echo('adding service "{}" to docker-compose.yml'.format(service_name))

        docker_compose['services'][service_name] = service_docker_compose

        # write out the docker-compose object to the file
        with open(docker_compose_filename, 'w') as fd:
            fd.write(yaml.safe_dump(docker_compose))
        click.echo('{} written'.format(docker_compose_filename))

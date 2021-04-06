import os
import sys
import venv
import json
from os.path import abspath
from os.path import join
from subprocess import check_call  # nosec

import click

from crossbar.quickstart.main import hl  # XXX "util" or similar instead?

__all__ = ('main', )


@click.command()
@click.option("--framework",
              prompt=True,
              type=click.Choice(['twisted', 'asyncio']),
              help="The Python networking framework to use",
              default="twisted")
@click.option(
    "--directory",
    prompt=True,
    default="./cbquickstart",
    help="Directory to create and put examples into",
    type=click.Path(exists=False),
)
@click.option(
    "--cfc",
    default=None,
    help="Master node connection",
    metavar="URI",
)
def main(framework, directory, cfc):
    """
    """
    directory = abspath(directory)
    if cfc is None:
        cfc = "ws://localhost:4444"

    click.echo('{cb} Project Quickstart (virtualenv)\n'.format(cb=hl('Crossbar.io / XBR'), ))
    click.echo("  Framework:  {fw}\n"
               "  Location:   {d}\n"
               "  CFC URI:    {fabric_uri}\n".format(
                   fw=framework,
                   d=directory,
                   fabric_uri=cfc,
               ))

    os.mkdir(directory)
    venv_location = join(directory, 'venv')
    _create_virtualenv(venv_location, framework)
    _create_applications(directory, venv_location, cfc)
    _create_makefile(directory, venv_location)

    click.echo("\n"
               "Quickstart Successful\n"
               "\n"
               "There is Makefile in '{mf}'\n"
               "Starting one shell per target, run these (in this order):\n"
               "  - make etcd\n"
               "  - make cfc\n"
               "  - make app0\n".format(mf=click.style(directory, bold=True, fg='yellow'), ))


def _create_makefile(directory, venv_location):
    template_args = {
        "top_level": directory,
        "venv": venv_location,
        "command_line": " ".join(sys.argv),
    }
    os.mkdir(join(directory, "etcd-data"))
    with open(join(directory, "Makefile"), "w") as makefile:
        makefile.write("""
# generated makefile used command:
# {command_line}

.PHONY: run cfc app0 etcd

run: etcd cfc app0
\techo "running"

etcd:
\tdocker run \
\t\t--rm \
\t\t-p 2379:2379 \
\t\t-p 2380:2380 \
\t\t-v /usr/share/ca-certificates/:/etc/ssl/certs \
\t\t-v {top_level}/etcd-data:/etcd-data \
\t\t--name etcd \
\t\t--net=host \
\t\tquay.io/coreos/etcd:latest \
\t\t\t/usr/local/bin/etcd \
\t\t\t--data-dir=/etcd-data \
\t\t\t--name cf-etcd \
\t\t\t--advertise-client-urls http://0.0.0.0:2379 \
\t\t\t--listen-client-urls http://0.0.0.0:2379

cfc:
\t{venv}/bin/crossbar master start --cbdir {top_level}/master/.crossbar

app0:
\t{venv}/bin/crossbar edge start --cbdir {top_level}/app0/.crossbar
""".format(**template_args))


def _create_applications(location, venv, cfc):
    cbfx = join(venv, "bin", "crossbar")
    app0 = join(location, "app0")
    master = join(location, "master")

    # create a CFC
    check_call([cbfx, "master", "init", "--appdir", master])  # nosec
    with open(join(master, ".crossbar", "config.json")) as f:
        data = json.load(f)
    data['workers'][0]['transports'][0]['endpoint']['port'] = 4444
    with open(join(master, ".crossbar", "config.json"), 'w') as f:
        json.dump(data, f, indent=4)

    # create an 'edge' node (application)
    check_call([cbfx, "edge", "init", "--appdir", app0])  # nosec
    # edit configuration
    with open(join(app0, ".crossbar", "config.json")) as f:
        data = json.load(f)

    if cfc:
        data['controller']['fabric'] = {
            'transport': {
                'url': cfc,
            }
        }
    with open(join(app0, ".crossbar", "config.json"), 'w') as f:
        json.dump(data, f, indent=4)


def _create_virtualenv(location, framework):
    """
    Create a new virtual environment.

    :param location: a non-existant directory (parent must exist though)
    """
    click.echo(click.style("\ncreating '{env}'\n".format(env=location), bold=True, fg="yellow"))
    venv.create(location, with_pip=True)

    pip = join(location, "bin", "pip")

    click.echo(click.style("\nupgrading pip\n", bold=True, fg="yellow"))
    check_call([pip, "install", "--upgrade", "pip"])  # nosec

    click.echo(click.style("\ninstalling software\n", bold=True, fg="yellow"))

    check_call([pip, "install", "autobahn[{}]".format(framework)])  # nosec
    check_call([pip, "install", "crossbar"])  # nosec

    # XXX I guess we just assume we're "in" a Fabric checkout, because
    # how else would you even be running this command?
    check_call([pip, "install", "--editable", "."])  # nosec
    # XXX FIXME why isn't ^ installing our dependencies??
    check_call([pip, "install", "-r", "requirements-min.txt"])  # nosec

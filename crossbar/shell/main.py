###############################################################################
#
# Crossbar.io Shell
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

import os
import re
import sys
import platform
import importlib
import hashlib
import json

import six
import click

# Notes:
#
# click does NOT allow to document CLI arguments! this is ridiculous, but true:
# https://github.com/pallets/click/issues/587
# to document, refer to arguments in UPPERCASE in the main command help. yeah, awesome.
# the justification is: "this has been the Unix way" - yeah, fuck that.

# this is for pyinstaller! otherwise it fails to find this dep.
# see: http://cffi.readthedocs.io/en/latest/cdef.html
import _cffi_backend  # noqa

# import and select network framework in txaio _before_ any further crossbar.shell imports
import txaio

txaio.use_twisted()  # noqa

from cfxdb.exporter import Exporter

from crossbar.shell import __version__, __build__  # noqa: E402
from crossbar.shell import command
from crossbar.shell.app import Application

_HEXKEY = re.compile(r'^[0-9a-fA-F]{64,64}$')

USAGE = """
Examples:
To start the interactive shell, use the "shell" command:

    cbf shell

You can run the shell under different user profile
using the "--profile" option:

    cbf --profile mister-test1 shell
"""

# the global, singleton app object
_app = Application()


def hl(text):
    if not isinstance(text, six.text_type):
        text = '{}'.format(text)
    return click.style(text, fg='yellow', bold=True)


class Config(object):
    """
    Command configuration object where we collect all the parameters,
    options etc for later processing.
    """
    def __init__(self, app, dotdir, profile, realm, role):
        self.app = app
        self.dotdir = dotdir
        self.profile = profile
        self.realm = realm
        self.role = role
        self.resource_type = None
        self.resource = None

    def __str__(self):
        return 'Config(resource_type={}, resource={})'.format(self.resource_type, self.resource)


@click.group(help="Crossbar.io Command Line", invoke_without_command=True)
@click.option(
    '--dotdir',
    envvar='CBF_DOTDIR',
    default=None,
    help="Set the dot directory (with config and profile) to be used",
)
@click.option(
    '--profile',
    envvar='CBF_PROFILE',
    default='default',
    help="Set the profile to be used",
)
@click.option(
    '--realm',
    envvar='CBF_REALM',
    default=None,
    help="Set the realm to join",
)
@click.option(
    '--role',
    envvar='CBF_ROLE',
    default=None,
    help="Set the role requested to authenticate as",
)
@click.option('--debug', is_flag=True, help='Enable debug output')
@click.pass_context
def cli(ctx, dotdir, profile, realm, role, debug):
    if debug:
        txaio.start_logging(level='info')

    ctx.obj = Config(_app, dotdir, profile, realm, role)

    # Allowing a command group to specifiy a default subcommand can be done using
    # https://github.com/click-contrib/click-default-group
    #
    # However, this breaks the click-repl integration for prompt-toolkit:
    #
    # https://github.com/pallets/click/issues/430#issuecomment-282015177
    #
    # Hence, we are using a different (probably less clean) trick - this works.
    #
    if ctx.invoked_subcommand is None:
        ctx.invoke(cmd_shell)


@cli.command(name='monitor', help='monitor master node')
@click.pass_context
def cmd_monitor(ctx):
    cfg = ctx.obj

    # key: userkey.UserKey
    # profile: config.Profile
    key, profile = ctx.obj.app.load_profile(profile=cfg.profile)

    from .monitor import run
    run(management_url=profile.url, privkey_file=profile.privkey)


@cli.command(name='version', help='print version information')
@click.pass_context
def cmd_version(ctx):
    def get_version(name_or_module):
        if isinstance(name_or_module, str):
            name_or_module = importlib.import_module(name_or_module)
        try:
            return name_or_module.__version__
        except AttributeError:
            return ''

    # Python (language)
    py_ver = '.'.join([str(x) for x in list(sys.version_info[:3])])

    # Python (implementation)
    if hasattr(sys, 'pypy_version_info'):
        pypy_version_info = getattr(sys, 'pypy_version_info')
        py_impl_str = '.'.join(str(x) for x in pypy_version_info[:3])
        py_ver_detail = "{}-{}".format(platform.python_implementation(), py_impl_str)
    else:
        py_ver_detail = platform.python_implementation()

    # Autobahn
    ab_ver = get_version('autobahn')

    # Pyinstaller (frozen EXE)
    py_is_frozen = getattr(sys, 'frozen', False)
    if py_is_frozen:
        m = hashlib.sha256()
        with open(sys.executable, 'rb') as fd:
            m.update(fd.read())
        fingerprint = m.hexdigest()
    else:
        fingerprint = None

    # Docker Compose
    try:
        import compose
    except ImportError:
        compose_ver = 'not installed'
    else:
        compose_ver = compose.__version__

    # Sphinx
    try:
        import sphinx
    except ImportError:
        sphinx_ver = 'not installed'
    else:
        sphinx_ver = sphinx.__version__

    platform_str = platform.platform(terse=True, aliased=True)

    click.echo()
    click.echo(hl("  Crossbar.io Shell") + ' - Command line tool for Crossbar.io')
    click.echo()
    click.echo('  {:<24}: {}'.format('Version', hl('{} (build {})'.format(__version__, __build__))))
    click.echo('  {:<24}: {}'.format('Platform', hl(platform_str)))
    click.echo('  {:<24}: {}'.format('Python (language)', hl(py_ver)))
    click.echo('  {:<24}: {}'.format('Python (implementation)', hl(py_ver_detail)))
    click.echo('  {:<24}: {}'.format('Autobahn', hl(ab_ver)))
    click.echo('  {:<24}: {}'.format('Docker Compose', hl(compose_ver)))
    click.echo('  {:<24}: {}'.format('Sphinx', hl(sphinx_ver)))
    click.echo('  {:<24}: {}'.format('Frozen executable', hl('yes' if py_is_frozen else 'no')))
    if py_is_frozen:
        click.echo('  {:<24}: {}'.format('Executable SHA256', hl(fingerprint)))
    click.echo()


@cli.command(name='init', help='create a new user profile / key-pair if none exists')
@click.option(
    '--yes',
    is_flag=True,
    default=False,
    help="Answer yes / use default for anything prompted",
)
@click.pass_context
def cmd_init(ctx, yes):
    cfg = ctx.obj
    cfg.yes_to_all = yes
    ctx.obj.app.run_context(ctx)


@cli.command(name='auth', help='authenticate user with Crossbar.io')
@click.option(
    '--code',
    default=None,
    help="Supply authentication code (received by email)",
)
@click.option(
    '--new-code',
    is_flag=True,
    default=False,
    help=  # noqa: E251
    "Request sending of a new authentication code (even though an old one is still pending)",
)
@click.option(
    '--yes',
    is_flag=True,
    default=False,
    help=  # noqa: E251
    "Answer yes / use default for anything prompted",
)
@click.pass_context
def cmd_auth(ctx, code, new_code, yes):
    cfg = ctx.obj
    cfg.code = code
    cfg.new_code = new_code
    cfg.yes_to_all = yes
    ctx.obj.app.run_context(ctx)


@cli.command(name='shell', help='run an interactive Crossbar.io Shell')
@click.pass_context
def cmd_shell(ctx):
    ctx.obj.app.run_context(ctx)


@cli.command(name='clear', help='clear screen')
def cmd_clear():
    click.clear()


@cli.command(name='help', help='general help')
@click.pass_context
def cmd_help(ctx):
    click.echo(ctx.parent.get_help())
    click.echo(USAGE)


@cli.group(name='set', help='change shell settings')
@click.pass_context
def cmd_set(ctx):
    pass


#
# set output-verbosity
#
@cmd_set.group(name='output-verbosity', help='command output verbosity')
@click.pass_context
def cmd_set_output_verbosity(ctx):
    pass


@cmd_set_output_verbosity.command(name='silent', help='swallow everything including result, but error messages')
@click.pass_context
def cmd_set_output_verbosity_silent(ctx):
    ctx.obj.app.set_output_verbosity('silent')


@cmd_set_output_verbosity.command(name='result-only', help='only output the plain command result')
@click.pass_context
def cmd_set_output_verbosity_result_only(ctx):
    ctx.obj.app.set_output_verbosity('result-only')


@cmd_set_output_verbosity.command(name='normal', help='output result and short run-time message')
@click.pass_context
def cmd_set_output_verbosity_normal(ctx):
    ctx.obj.app.set_output_verbosity('normal')


@cmd_set_output_verbosity.command(name='extended', help='output result and extended execution information.')
@click.pass_context
def cmd_set_output_verbosity_extended(ctx):
    ctx.obj.app.set_output_verbosity('extended')


#
# set output-format
#
@cmd_set.group(name='output-format', help='command output format')
@click.pass_context
def cmd_set_output_format(ctx):
    pass


def _make_set_output_format(output_format):
    @cmd_set_output_format.command(name=output_format, help='set {} output format'.format(output_format.upper()))
    @click.pass_context
    def f(ctx):
        ctx.obj.app.set_output_format(output_format)

    return f


for output_format in Application.OUTPUT_FORMAT:
    _make_set_output_format(output_format)


#
# set output-style
#
@cmd_set.group(name='output-style', help='command output style')
@click.pass_context
def cmd_set_output_style(ctx):
    pass


def _make_set_output_style(output_style):
    @cmd_set_output_style.command(name=output_style, help='set {} output style'.format(output_style.upper()))
    @click.pass_context
    def f(ctx):
        ctx.obj.app.set_output_style(output_style)

    return f


for output_style in Application.OUTPUT_STYLE:
    _make_set_output_style(output_style)


@cli.group(name='show', help='show resources')
@click.pass_context
def cmd_show(ctx):
    pass


@cmd_show.command(name='status', help='show domain or mrealm status')
@click.pass_context
def cmd_show_domain_status(ctx):
    _command = command.CmdGetDomainStatus(ctx.obj.realm)
    ctx.obj.app.run_context(ctx, _command)


@cmd_show.command(name='version', help='get domain controller software version')
@click.pass_context
def cmd_show_domain_version(ctx):
    _command = command.CmdGetDomainVersion(ctx.obj.realm)
    ctx.obj.app.run_context(ctx, _command)


@cmd_show.command(name='license', help='get domain software stack license')
@click.pass_context
def cmd_show_domain_license(ctx):
    _command = command.CmdGetDomainLicense(ctx.obj.realm)
    ctx.obj.app.run_context(ctx, _command)


@cmd_show.command(name='database', help='open and show embedded database details')
@click.argument('dbpath')
@click.option('--include-slots/--no-include-slots', default=False, type=bool, help='show database slots')
@click.pass_context
def cmd_show_database(ctx, dbpath, include_slots):
    exporter = Exporter(dbpath)
    exporter.print_config()
    exporter.print_stats(include_slots=include_slots)


@cli.group(name='export', help='export resources')
@click.pass_context
def cmd_export(ctx):
    pass


@cmd_export.command(name='database', help='export embedded database')
@click.argument('dbpath')
@click.option('--filename')
@click.option('--include-indexes/--no-include-indexes', default=False, type=bool, help='export index tables')
@click.option('--include-schemata',
              type=str,
              help='list of schemata to export (meta, globalschema, mrealmschema, xbr, xbrmm, xbrnetwork)')
@click.option('--exclude-tables', type=str)
@click.option('--use-json/--no-use-json', default=False, type=bool)
@click.option('--use-binary-hex-encoding/--no-use-binary-hex-encoding', default=False, type=bool)
@click.option('--quiet/--no-quiet', default=False, type=bool)
@click.pass_context
def cmd_export_database(ctx, dbpath, filename, include_indexes, include_schemata, exclude_tables, use_json,
                        use_binary_hex_encoding, quiet):
    if include_schemata:
        include_schemata = include_schemata.split(',')
    if exclude_tables:
        exclude_tables = exclude_tables.split(',')

    exporter = Exporter(dbpath)
    exporter.export_database(filename,
                             include_indexes=include_indexes,
                             include_schemata=include_schemata,
                             exclude_tables=exclude_tables,
                             use_json=use_json,
                             use_binary_hex_encoding=use_binary_hex_encoding,
                             quiet=quiet)


@cli.group(name='import', help='import resources')
@click.pass_context
def cmd_import(ctx):
    pass


@cmd_import.command(name='database', help='import embedded database')
@click.argument('dbpath')
@click.argument('filename')
@click.option('--include-indexes/--no-include-indexes', default=False, type=bool, help='import index tables')
@click.option('--include-schemata', type=str)
@click.option('--exclude-tables', type=str)
@click.option('--use-json/--no-use-json', default=False, type=bool)
@click.option('--use-binary-hex-encoding/--no-use-binary-hex-encoding', default=False, type=bool)
@click.option('--quiet/--no-quiet', default=False, type=bool)
@click.pass_context
def cmd_import_database(ctx, dbpath, filename, include_indexes, include_schemata, exclude_tables, use_json,
                        use_binary_hex_encoding, quiet):
    if include_schemata:
        include_schemata = include_schemata.split(',')
    if exclude_tables:
        exclude_tables = exclude_tables.split(',')

    exporter = Exporter(dbpath)
    exporter.print_stats()
    exporter.import_database(filename,
                             include_indexes=include_indexes,
                             include_schemata=include_schemata,
                             exclude_tables=exclude_tables,
                             use_json=use_json,
                             use_binary_hex_encoding=use_binary_hex_encoding,
                             quiet=quiet)
    exporter.print_stats()


@cli.group(name='add', help='add resources')
@click.pass_context
def cmd_add(ctx):
    pass


@cmd_add.command(name='principal', help='add a principal to an application realm')
@click.argument('realm')
@click.argument('principal')
@click.option('--config', type=str)
@click.pass_context
def cmd_add_principal(ctx, realm, principal, config=None):
    if config:
        config = json.loads(config)
    else:
        config = {}
    config['authid'] = principal
    cmd = command.CmdAddPrincipal(realm, principal, config)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_add.command(name='principal-credential', help='add a credential to a principal')
@click.argument('realm')
@click.argument('principal')
@click.option('--config', type=str)
@click.pass_context
def cmd_add_principal_credential(ctx, realm, principal, config=None):
    if config:
        config = json.loads(config)
    else:
        config = {}
    cmd = command.CmdAddPrincipalCredential(realm, principal, config)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_add.command(name='role-permission', help='add a permission to a role')
@click.argument('role')
@click.argument('uri')
@click.option('--config', type=str)
@click.pass_context
def cmd_add_role_permission(ctx, role, uri, config=None):
    if config:
        config = json.loads(config)
    else:
        config = {}
    config['uri'] = uri
    cmd = command.CmdAddRolePermission(role, uri, config)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_add.command(name='arealm-role', help='add a role to an application realm')
@click.argument('realm')
@click.argument('role')
@click.option('--config', type=str)
@click.pass_context
def cmd_add_realm_role(ctx, realm, role, config=None):
    if config:
        config = json.loads(config)
    cmd = command.CmdAddApplicationRealmRole(realm, role, config)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_add.command(name='routercluster-node', help='add a node to a routercluster')
@click.argument('cluster')
@click.argument('node', default='all')
@click.option('--config', type=str)
@click.pass_context
def cmd_add_routercluster_node(ctx, cluster, node, config=None):
    if config:
        config = json.loads(config)
    cmd = command.CmdAddRouterClusterNode(cluster, node, config)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_add.command(name='routercluster-workergroup', help='add a workergroup to a routercluster')
@click.argument('cluster')
@click.argument('workergroup')
@click.option('--config', type=str)
@click.pass_context
def cmd_add_routercluster_workergroup(ctx, cluster, workergroup, config=None):
    if config:
        config = json.loads(config)
    else:
        config = {}
    config['name'] = workergroup
    cmd = command.CmdAddRouterClusterWorkerGroup(cluster, workergroup, config)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_add.command(name='webcluster-node', help='add a node to a webcluster')
@click.argument('cluster')
@click.argument('node', default='all')
@click.option('--config', type=str)
@click.pass_context
def cmd_add_webcluster_node(ctx, cluster, node, config=None):
    if config:
        config = json.loads(config)
    cmd = command.CmdAddWebClusterNode(cluster, node, config)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_add.command(name='webcluster-service', help='add a web service to a webcluster')
@click.argument('cluster')
@click.argument('path')
@click.option('--config', type=str)
@click.pass_context
def cmd_add_webcluster_service(ctx, cluster, path, config=None):
    if config:
        webservice = json.loads(config)
    else:
        webservice = {}
        webservice['path'] = path
    cmd = command.CmdAddWebClusterService(cluster, path, webservice)
    ctx.obj.app.run_context(ctx, cmd)


@cli.group(name='create', help='create resources')
@click.pass_context
def cmd_create(ctx):
    pass


@cmd_create.command(name='mrealm', help='create a new management realm')
@click.argument('realm')
@click.pass_context
def cmd_create_management_realm(ctx, realm):
    cmd = command.CmdCreateManagementRealm(realm=realm)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_create.command(name='arealm', help='create a new application realm')
@click.argument('realm')
@click.option('--config', type=str)
@click.pass_context
def cmd_create_application_realm(ctx, realm, config=None):
    if config:
        config = json.loads(config)
    else:
        config = {}
    config['name'] = realm
    cmd = command.CmdCreateApplicationRealm(config)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_create.command(name='role', help='create a new role')
@click.argument('role')
@click.option('--config', type=str)
@click.pass_context
def cmd_create_role(ctx, role, config=None):
    if config:
        config = json.loads(config)
    else:
        config = {}
    config['name'] = role
    cmd = command.CmdCreateRole(config)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_create.command(name='routercluster', help='create a new routercluster')
@click.argument('cluster')
@click.option('--config', type=str)
@click.pass_context
def cmd_create_routercluster(ctx, cluster, config=None):
    if config:
        config = json.loads(config)
    else:
        config = {}
    config['name'] = cluster
    cmd = command.CmdCreateRouterCluster(config)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_create.command(name='webcluster', help='create a new webcluster')
@click.argument('cluster')
@click.option('--config', type=str)
@click.pass_context
def cmd_create_webcluster(ctx, cluster, config=None):
    if config:
        config = json.loads(config)
    else:
        config = {}
    config['name'] = cluster
    cmd = command.CmdCreateWebCluster(config)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_create.command(name='webservice', help='create a webservice within a webcluster')
@click.argument('cluster')
@click.argument('config')
@click.pass_context
def cmd_create_webservice(ctx, cluster, config):
    config = json.loads(config)
    cmd = command.CmdCreateWebService(cluster, config)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_create.command(name='docker-container', help='create a new Docker container on a node')
@click.argument('node')
@click.argument('image')
@click.option('--config', type=str)
@click.pass_context
def cmd_create_docker_container(ctx, node, image, config=None):
    if config:
        config = json.loads(config)
    else:
        config = {}
    cmd = command.CmdCreateDockerContainer(node, image, config)
    ctx.obj.app.run_context(ctx, cmd)


@cli.group(name='remove', help='remove resources')
@click.pass_context
def cmd_remove(ctx):
    pass


@cmd_remove.command(name='routercluster-node', help='remove a node from a routercluster')
@click.argument('cluster')
@click.argument('node')
@click.pass_context
def cmd_remove_routercluster_node(ctx, cluster, node):
    cmd = command.CmdRemoveRouterClusterNode(cluster, node)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_remove.command(name='routercluster-workergroup', help='remove a workergroup from a routercluster')
@click.argument('cluster')
@click.argument('workergroup')
@click.pass_context
def cmd_remove_routeercluster_workergroup(ctx, cluster, workergroup):
    cmd = command.CmdRemoveRouterClusterWorkerGroup(cluster, workergroup)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_remove.command(name='webcluster-node', help='remove a node from a webcluster')
@click.argument('cluster')
@click.argument('node')
@click.pass_context
def cmd_remove_webcluster_node(ctx, cluster, node):
    cmd = command.CmdRemoveWebClusterNode(cluster, node)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_remove.command(name='webcluster-service', help='remove a service from a webcluster')
@click.argument('cluster')
@click.argument('path')
@click.pass_context
def cmd_remove_webcluster_service(ctx, cluster, path):
    cmd = command.CmdRemoveWebClusterService(cluster, path)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_remove.command(name='arealm-principal', help='remove a principal from an application realm')
@click.argument('arealm')
@click.argument('principal')
@click.pass_context
def cmd_remove_arealm_principal(ctx, arealm, principal):
    cmd = command.CmdRemoveArealmPrincipal(arealm, principal)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_remove.command(name='principal-credential', help='remove credentials from a principal on an application realm')
@click.argument('arealm')
@click.argument('principal')
@click.argument('credential')
@click.pass_context
def cmd_remove_arealm_principal_credential(ctx, arealm, principal, credential):
    cmd = command.CmdRemoveArealmPrincipalCredential(arealm, principal, credential)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_remove.command(name='role-permission', help='remove a permission from a role')
@click.argument('role')
@click.argument('path')
@click.pass_context
def cmd_remove_role_permission(ctx, role, path):
    cmd = command.CmdRemoveRolePermission(role, path)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_remove.command(name='arealm-role', help='remove a role from an application realm')
@click.argument('arealm')
@click.argument('role')
@click.pass_context
def cmd_remove_arealm_role(ctx, arealm, role):
    cmd = command.CmdRemoveArealmRole(arealm, role)
    ctx.obj.app.run_context(ctx, cmd)


@cli.group(name='delete', help='delete resources')
@click.pass_context
def cmd_delete(ctx):
    pass


@cmd_delete.command(name='mrealm', help='Delete an existing management REALM by name.')
@click.argument('realm', type=str)
@click.option(
    '--cascade',
    is_flag=True,
    help=
    'Automatically unpair (but not delete) any nodes currently paired with and unassign (but not delete) any users currently assigned to the management realm to be deleted.'
)
@click.pass_context
def cmd_delete_management_realm(ctx, realm, cascade=False):
    cmd = command.CmdDeleteManagementRealm(realm, cascade)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_delete.command(name='routercluster', help='delete an existing webrouterclustercluster')
@click.argument('cluster')
@click.pass_context
def cmd_delete_routercluster(ctx, cluster):
    cmd = command.CmdDeleteRouterCluster(cluster)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_delete.command(name='webcluster', help='delete an existing webcluster')
@click.argument('cluster')
@click.pass_context
def cmd_delete_webcluster(ctx, cluster):
    cmd = command.CmdDeleteWebCluster(cluster)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_delete.command(name='arealm', help='delete an existing application realm')
@click.argument('arealm')
@click.option('--cascade', is_flag=True, help='Automatically delete dependent resources of the application realm.')
@click.pass_context
def cmd_delete_arealm(ctx, arealm, cascade=False):
    cmd = command.CmdDeleteApplicationRealm(arealm, cascade)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_delete.command(name='role', help='delete an existing application role')
@click.argument('role')
@click.pass_context
def cmd_delete_role(ctx, role):
    cmd = command.CmdDeleteRole(role)
    ctx.obj.app.run_context(ctx, cmd)


@cli.group(name='pair', help='pair nodes and devices')
@click.pass_context
def cmd_pair(ctx):
    pass


def _read_pubkey(pubkey):
    if not _HEXKEY.match(pubkey):
        fn = os.path.expanduser(pubkey)
        if not os.path.exists(fn):
            raise Exception('could not open node public key file {}'.format(fn))
        public_hex = None
        with open(fn, 'r') as f:
            data = f.read()
            for line in data.splitlines():
                if line.startswith('public-key-ed25519'):
                    public_hex = line.split(':')[1].strip()
                    break
        if not public_hex:
            raise Exception('no public key found in node public key file {}'.format(fn))
        pubkey = public_hex
    return pubkey


@cmd_pair.command(name='node', help='pair a node')
@click.argument('pubkey')
@click.argument('realm')
@click.argument('node_id')
@click.option('--authextra', type=str)
@click.pass_context
def cmd_pair_node(ctx, pubkey, realm, node_id, authextra=None):
    """

    :param ctx:
    :param pubkey: the public key of the node, a 32 bytes Ed25519 public key provided as a HEX string (64 characters),
        or alternatively a filename to read the public key from
    :param realm: management realm the node is to be paired with
    :param node_id: the ID of node assigned when the node is connecting
    :param authextra: authextra to be provided to the node when connecting, must be a JSON string
    :return:
    """
    assert type(pubkey) == str
    assert type(realm) == str
    assert type(node_id) == str
    assert authextra is None or type(authextra) == str

    pubkey = _read_pubkey(pubkey)

    if authextra:
        authextra = json.loads(authextra)

    cmd = command.CmdPairNode(pubkey=pubkey, realm=realm, node_id=node_id, authextra=authextra)
    ctx.obj.app.run_context(ctx, cmd)


@cli.group(name='unpair', help='unpair nodes and devices')
@click.pass_context
def cmd_unpair(ctx):
    pass


@cmd_unpair.command(name='node', help='unpair a node')
@click.argument('pubkey')
@click.pass_context
def cmd_unpair_node(ctx, pubkey):
    """

    :param ctx:
    :param pubkey:
    :return:
    """
    assert type(pubkey) == str

    pubkey = _read_pubkey(pubkey)

    cmd = command.CmdUnpairNode(pubkey=pubkey)
    ctx.obj.app.run_context(ctx, cmd)


@cli.group(name='start', help='start workers, components, ..')
@click.pass_context
def cmd_start(ctx):
    pass


# @cmd_start.command(name='worker', help='start a worker')
# @click.argument('node')
# @click.argument('worker')
# @click.argument('worker-type')
# @click.option('--options', help='worker options', default=None)
# @click.pass_context
# def cmd_start_worker(ctx, node, worker, worker_type, options=None):
#    cmd = command.CmdStartWorker(node, worker, worker_type, worker_options=options)
#    ctx.obj.app.run_context(ctx, cmd)
# from crossbar.shell.command import CmdStartContainerWorker, CmdStartContainerComponent


@cmd_start.command(name='docker-container', help='start a Docker container on a node')
@click.argument('node')
@click.argument('container')
@click.pass_context
def cmd_start_docker_container(ctx, node, container):
    cmd = command.CmdStartDockerContainer(node, container)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_start.command(name='container-worker', help='start a container worker')
@click.option('--process-title', help='worker process title (at OS level)', default=None)
@click.argument('node')
@click.argument('worker')
@click.pass_context
def cmd_start_container_worker(ctx, node, worker, process_title=None):
    cmd = command.CmdStartContainerWorker(node, worker, process_title=process_title)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_start.command(name='container-component', help='start a container component')
@click.argument('node')
@click.argument('worker')
@click.argument('component')
@click.pass_context
def cmd_start_container_component(ctx, node, worker, component):
    cmd = command.CmdStartContainerComponent(node, worker, component)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_start.command(name='router-worker', help='start a router worker')
@click.option('--process-title', help='worker process title (at OS level)', default=None)
@click.argument('node')
@click.argument('worker')
@click.pass_context
def cmd_start_router_worker(ctx, node, worker, process_title=None):
    cmd = command.CmdStartRouterWorker(node, worker, process_title=process_title)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_start.command(name='router-realm', help='start a router realm')
@click.argument('node')
@click.argument('worker')
@click.argument('realm')
@click.pass_context
def cmd_start_router_realm(ctx, node, worker, realm):
    cmd = command.CmdStartRouterRealm(node, worker, realm)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_start.command(name='router-transport', help='start a router transport')
@click.argument('node')
@click.argument('worker')
@click.argument('transport')
@click.option('--config', type=str)
@click.pass_context
def cmd_start_router_transport(ctx, node, worker, transport, config=None):
    if config:
        config = json.loads(config)
    cmd = command.CmdStartRouterTransport(node, worker, transport, config)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_start.command(name='webtransport-service', help='start a web-transport service')
@click.argument('node')
@click.argument('worker')
@click.argument('transport')
@click.argument('path')
@click.option('--config', type=str)
@click.pass_context
def cmd_start_web_transport_service(ctx, node, worker, transport, path, config=None):
    if config:
        config = json.loads(config)
    cmd = command.CmdStartWebTransportService(node, worker, transport, path, config)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_start.command(name='guest-worker', help='start a guest worker')
@click.argument('node')
@click.argument('worker')
@click.pass_context
def cmd_start_guest_worker(ctx, node, worker):
    cmd = command.CmdStartGuestWorker(node, worker)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_start.command(name='routercluster', help='start a routercluster')
@click.argument('cluster')
@click.pass_context
def cmd_start_routercluster(ctx, cluster):
    cmd = command.CmdStartRouterCluster(cluster)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_start.command(name='arealm', help='start an application realm on a router worker group')
@click.argument('arealm')
@click.argument('routercluster')
@click.argument('workergroup')
@click.argument('webcluster')
@click.pass_context
def cmd_start_arealm(ctx, arealm, routercluster, workergroup, webcluster):
    cmd = command.CmdStartApplicationRealm(arealm, routercluster, workergroup, webcluster)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_start.command(name='webcluster', help='start a webcluster')
@click.argument('cluster')
@click.pass_context
def cmd_start_webcluster(ctx, cluster):
    cmd = command.CmdStartWebCluster(cluster)
    ctx.obj.app.run_context(ctx, cmd)


@cli.group(name='stop', help='stop workers, components, ..')
@click.pass_context
def cmd_stop(ctx):
    pass


@cmd_stop.command(name='docker-container', help='stop a Docker container running on a node')
@click.argument('node')
@click.argument('container')
@click.pass_context
def cmd_stop_docker_container(ctx, node, container):
    cmd = command.CmdStopDockerContainer(node, container)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_stop.command(name='worker', help='stop a worker')
@click.argument('node')
@click.argument('worker')
@click.pass_context
def cmd_stop_worker(ctx, node, worker):
    cmd = command.CmdStopWorker(node, worker)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_stop.command(name='router-realm', help='stop a router realm')
@click.argument('node')
@click.argument('worker')
@click.argument('realm')
@click.pass_context
def cmd_stop_router_realm(ctx, node, worker, realm):
    cmd = command.CmdStopRouterRealm(node, worker, realm)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_stop.command(name='router-transport', help='stop a router transport')
@click.argument('node')
@click.argument('worker')
@click.argument('transport')
@click.pass_context
def cmd_stop_router_transport(ctx, node, worker, transport):
    cmd = command.CmdStopRouterTransport(node, worker, transport)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_stop.command(name='routercluster', help='stop a routercluster')
@click.argument('cluster')
@click.pass_context
def cmd_stop_routercluster(ctx, cluster):
    cmd = command.CmdStopRouterCluster(cluster)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_stop.command(name='webcluster', help='stop a webcluster')
@click.argument('cluster')
@click.pass_context
def cmd_stop_webcluster(ctx, cluster):
    cmd = command.CmdStopWebCluster(cluster)
    ctx.obj.app.run_context(ctx, cmd)


@cli.group(name='list', help='list resources')
@click.pass_context
def cmd_list(ctx):
    pass


@cmd_list.command(name='mrealms', help='list management realms')
@click.option('--names/--no-names', default=False, type=bool, help='return node names (authid) instead of object IDs')
@click.pass_context
def cmd_list_management_realms(ctx, names):
    cmd = command.CmdListManagementRealms(names=names)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_list.command(name='nodes', help='list nodes')
@click.option('--names/--no-names', default=False, type=bool, help='return node names (authid) instead of object IDs')
@click.option(
    '--online',
    is_flag=True,
    default=False,
    help=  # noqa: E251
    "List only nodes that are currently online",
)
@click.option(
    '--offline',
    is_flag=True,
    default=False,
    help=  # noqa: E251
    "List only nodes that are currently offline",
)
@click.pass_context
def cmd_list_nodes(ctx, names=None, online=None, offline=None):
    assert not (online and offline)
    cmd = command.CmdListNodes(online=online, offline=offline, names=names)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_list.command(name='workers', help='list workers')
@click.argument('node')
@click.pass_context
def cmd_list_workers(ctx, node):
    cmd = command.CmdListWorkers(node)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_list.command(name='router-realms', help='list router realms')
@click.argument('node')
@click.argument('worker')
@click.pass_context
def cmd_list_router_realms(ctx, node, worker):
    cmd = command.CmdListRouterRealms(node, worker)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_list.command(name='router-transports', help='list router transports')
@click.argument('node')
@click.argument('worker')
@click.pass_context
def cmd_list_router_transports(ctx, node, worker):
    cmd = command.CmdListRouterTransports(node, worker)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_list.command(name='arealms', help='list application realms')
@click.option('--names/--no-names',
              default=False,
              type=bool,
              help='return application realm names instead of object IDs')
@click.pass_context
def cmd_list_arealms(ctx, names):
    cmd = command.CmdListARealms(names=names)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_list.command(name='arealm-roles', help='list roles associated with application realm')
@click.argument('arealm')
@click.option('--names/--no-names', default=False, type=bool, help='return role names instead of object IDs')
@click.pass_context
def cmd_list_arealm_roles(ctx, arealm, names):
    cmd = command.CmdListARealmRoles(arealm, names=names)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_list.command(name='roles', help='list roles')
@click.option('--names/--no-names', default=False, type=bool, help='return role names instead of object IDs')
@click.pass_context
def cmd_list_roles(ctx, names):
    cmd = command.CmdListRoles(names=names)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_list.command(name='role-permissions', help='list role permissions')
@click.argument('role')
@click.pass_context
def cmd_list_role_permissions(ctx, role):
    cmd = command.CmdListRolePermissions(role)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_list.command(name='principals', help='list principals')
@click.argument('arealm')
@click.option('--names/--no-names', default=False, type=bool, help='return principals names instead of object IDs')
@click.pass_context
def cmd_list_principals(ctx, arealm, names):
    cmd = command.CmdListPrincipals(arealm, names=names)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_list.command(name='principal-credentials', help='list credentials of a principal')
@click.argument('arealm')
@click.argument('principal')
@click.pass_context
def cmd_list_principal_credentials(ctx, arealm, principal):
    cmd = command.CmdListPrincipalCredentials(arealm, principal)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_list.command(name='routerclusters', help='list routerclusters')
@click.option('--names/--no-names', default=False, type=bool, help='return routerclusters names instead of object IDs')
@click.pass_context
def cmd_list_routerclusters(ctx, names):
    cmd = command.CmdListRouterClusters(names=names)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_list.command(name='routercluster-nodes', help='list nodes of a routercluster')
@click.argument('cluster')
@click.option('--names/--no-names',
              default=False,
              type=bool,
              help='return routercluster nodes names (= authid) instead of object IDs')
@click.option('--filter-status',
              default=None,
              type=str,
              help='filter nodes returned by node status given, eg "online"')
@click.pass_context
def cmd_list_routercluster_nodes(ctx, cluster, names, filter_status):
    cmd = command.CmdListRouterClusterNodes(cluster, names=names, filter_status=filter_status)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_list.command(name='routercluster-workergroups', help='list workergroups of a routercluster')
@click.argument('cluster')
@click.option('--names/--no-names',
              default=False,
              type=bool,
              help='return routercluster workergroup names instead of object IDs')
@click.option('--filter-status',
              default=None,
              type=str,
              help='filter workergroups returned by workergroup status given, eg "online"')
@click.pass_context
def cmd_list_routercluster_workergroups(ctx, cluster, names, filter_status):
    cmd = command.CmdListRouterClusterWorkerGroups(cluster, names=names, filter_status=filter_status)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_list.command(name='webclusters', help='list webclusters')
@click.option('--names/--no-names', default=False, type=bool, help='return webcluster names instead of object IDs')
@click.pass_context
def cmd_list_webclusters(ctx, names):
    cmd = command.CmdListWebClusters(names=names)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_list.command(name='webcluster-nodes', help='list nodes of a webcluster')
@click.argument('cluster')
@click.option('--names/--no-names',
              default=False,
              type=bool,
              help='return webcluster nodes names (= authid) instead of object IDs')
@click.option('--filter-status',
              default=None,
              type=str,
              help='filter nodes returned by node status given, eg "online"')
@click.pass_context
def cmd_list_webcluster_nodes(ctx, cluster, names, filter_status):
    cmd = command.CmdListWebClusterNodes(cluster, names=names, filter_status=filter_status)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_list.command(name='webcluster-services', help='list webservices of a webcluster')
@click.argument('cluster')
@click.pass_context
def cmd_list_webcluster_webservices(ctx, cluster):
    cmd = command.CmdListWebClusterWebService(cluster)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_list.command(name='docker-images', help='list Docker images available on a node')
@click.argument('node')
@click.pass_context
def cmd_list_docker_images(ctx, node):
    cmd = command.CmdListDockerImages(node)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_list.command(name='docker-containers', help='list Docker containers on a node')
@click.argument('node')
@click.pass_context
def cmd_list_docker_containers(ctx, node):
    cmd = command.CmdListDockerContainers(node)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_show.command(name='fabric', help='show fabric')
@click.pass_context
def cmd_show_fabric(ctx):
    cmd = command.CmdShowFabric()
    ctx.obj.app.run_context(ctx, cmd)


@cmd_show.command(name='mrealm', help='show management realm (for domains)')
@click.argument('realm', default='any')
@click.pass_context
def cmd_show_mrealm(ctx, realm):
    cmd = command.CmdShowManagementRealm(realm)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_show.command(name='docker', help='show Docker information')
@click.argument('node')
@click.pass_context
def cmd_show_docker(ctx, node):
    cmd = command.CmdShowDocker(node)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_show.command(name='docker-image', help='show Docker image information')
@click.argument('node')
@click.argument('image')
@click.pass_context
def cmd_show_docker_image(ctx, node, image):
    cmd = command.CmdShowDockerImage(node, image)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_show.command(name='docker-container', help='show Docker container information')
@click.argument('node')
@click.argument('container')
@click.pass_context
def cmd_show_docker_container(ctx, node, container):
    cmd = command.CmdShowDockerContainer(node, container)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_show.command(name='node', help='show node')
@click.argument('node', default='all')
@click.pass_context
def cmd_show_node(ctx, node):
    cmd = command.CmdShowNode(node)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_show.command(name='worker', help='show worker')
@click.argument('node')
@click.argument('worker')
@click.pass_context
def cmd_show_worker(ctx, node, worker):
    cmd = command.CmdShowWorker(node, worker)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_show.command(name='transport', help='show transport (for router workers)')
@click.argument('node')
@click.argument('worker')
@click.argument('transport')
@click.pass_context
def cmd_show_transport(ctx, node, worker, transport):
    cmd = command.CmdShowTransport(node, worker, transport)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_show.command(name='realm', help='show realm (for router workers)')
@click.argument('node')
@click.argument('worker')
@click.argument('realm')
@click.pass_context
def cmd_show_realm(ctx, node, worker, realm):
    cmd = command.CmdShowRealm(node, worker, realm)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_show.command(name='component', help='show component (for container and router workers)')
@click.argument('node')
@click.argument('worker')
@click.argument('component')
@click.pass_context
def cmd_show_component(ctx, node, worker, component):
    cmd = command.CmdShowComponent(node, worker, component)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_show.command(name='arealm', help='show application realm')
@click.argument('arealm', default='all')
@click.pass_context
def cmd_show_arealm(ctx, arealm):
    cmd = command.CmdShowApplicationRealm(arealm)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_show.command(name='principal', help='show principal')
@click.argument('realm')
@click.argument('principal')
@click.pass_context
def cmd_show_principal(ctx, realm, principal):
    cmd = command.CmdShowPrincipal(realm, principal)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_show.command(name='role', help='show role')
@click.argument('role')
@click.pass_context
def cmd_show_role(ctx, role):
    cmd = command.CmdShowRole(role)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_show.command(name='role-permission', help='show role permission')
@click.argument('role')
@click.argument('uri')
@click.pass_context
def cmd_show_role_permission(ctx, role, uri):
    cmd = command.CmdShowRolePermission(role, uri)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_show.command(name='arealm-role', help='show arealm-role association')
@click.argument('arealm')
@click.argument('role')
@click.pass_context
def cmd_show_arealm_role(ctx, arealm, role):
    cmd = command.CmdShowARealmRole(arealm, role)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_show.command(name='routercluster', help='show routercluster')
@click.argument('cluster', default='all')
@click.pass_context
def cmd_show_routercluster(ctx, cluster):
    cmd = command.CmdShowRouterCluster(cluster)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_show.command(name='routercluster-node', help='show routercluster node')
@click.argument('cluster')
@click.argument('node', default='all')
@click.pass_context
def cmd_show_routercluster_node(ctx, cluster, node):
    cmd = command.CmdShowRouterClusterNode(cluster, node)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_show.command(name='routercluster-workergroup', help='show routercluster workergroup')
@click.argument('cluster')
@click.argument('workergroup')
@click.pass_context
def cmd_show_routercluster_workergroup(ctx, cluster, workergroup):
    cmd = command.CmdShowRouterClusterWorkerGroup(cluster, workergroup)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_show.command(name='webcluster', help='show webcluster')
@click.argument('cluster', default='all')
@click.pass_context
def cmd_show_webcluster(ctx, cluster):
    cmd = command.CmdShowWebCluster(cluster)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_show.command(name='webcluster-node', help='show webcluster node')
@click.argument('cluster')
@click.argument('node', default='all')
@click.pass_context
def cmd_show_webcluster_node(ctx, cluster, node):
    cmd = command.CmdShowWebClusterNode(cluster, node)
    ctx.obj.app.run_context(ctx, cmd)
    ctx.obj.app.run_context(ctx, cmd)


@cmd_show.command(name='webcluster-service', help='show webcluster webservice')
@click.argument('cluster')
@click.argument('webservice', default=None)
@click.pass_context
def cmd_show_webcluster_service(ctx, cluster, webservice):
    cmd = command.CmdShowWebClusterWebService(cluster, webservice)
    ctx.obj.app.run_context(ctx, cmd)


@cli.command(name='current', help='currently selected resource')
@click.pass_context
def cmd_current(ctx):
    _app.print_selected()


@cli.group(name='select', help='change current resource')
@click.pass_context
def cmd_select(ctx):
    pass


@cmd_select.command(name='node', help='change current node')
@click.argument('resource')
@click.pass_context
def cmd_select_node(ctx, resource):
    _app.current_resource_type = 'node'
    _app.current_resource = resource
    _app.print_selected()


@cmd_select.command(name='worker', help='change current worker')
@click.argument('resource')
@click.pass_context
def cmd_select_worker(ctx, resource):
    _app.current_resource_type = 'worker'
    _app.current_resource = resource
    _app.print_selected()


@cmd_select.command(name='transport', help='change current transport')
@click.argument('resource')
@click.pass_context
def cmd_select_transport(ctx, resource):
    _app.current_resource_type = 'transport'
    _app.current_resource = resource
    _app.print_selected()


def run():
    """
    Main entry point into CLI.
    """
    cli()  # pylint: disable=E1120


if __name__ == '__main__':
    run()

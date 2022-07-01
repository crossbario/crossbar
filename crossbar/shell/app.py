###############################################################################
#
# Crossbar.io Shell
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

import os
import sys
import json
import yaml
from pprint import pformat

import click

from pygments import highlight, lexers, formatters
from pygments.token import Token
from pygments.styles import get_all_styles

from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import style_from_pygments_dict

from twisted.python.failure import Failure
from twisted.internet.task import react

import txaio
from txaio import make_logger

from autobahn.websocket.util import parse_url
from autobahn.wamp.types import ComponentConfig
from autobahn.wamp.exception import ApplicationError
from autobahn.twisted.wamp import ApplicationRunner
from autobahn.xbr import UserKey

from crossbar.common.twisted.endpoint import _create_tls_client_context

from crossbar.shell.util import (style_crossbar, style_finished_line, style_error, style_ok, localnow)
from crossbar.shell import (client, config, __version__)

if 'CROSSBAR_FABRIC_URL' in os.environ:
    _DEFAULT_CFC_URL = os.environ['CROSSBAR_FABRIC_URL']
else:
    _DEFAULT_CFC_URL = 'wss://master.xbr.network/ws'


class WebSocketURL(click.ParamType):
    """
    WebSocket URL validator.
    """

    name = 'WebSocket URL'

    def __init__(self):
        click.ParamType.__init__(self)

    def convert(self, value, param, ctx):
        try:
            parse_url(value)
        except Exception as e:
            self.fail(style_error(str(e)))
        else:
            return value


def _prompt_for_url(yes_to_all):
    """
    Prompt user for CFC URL to create a new ~/.crossbar/config.ini file
    """
    if yes_to_all:
        value = _DEFAULT_CFC_URL
    else:
        value = click.prompt('Management service URL', type=WebSocketURL(), default=_DEFAULT_CFC_URL)
    return value


# default configuration stored in $HOME/.crossbar/config.ini
_DEFAULT_CONFIG = """[default]

url={url}
privkey=default.priv
pubkey=default.pub
"""


class Application(object):

    OUTPUT_FORMAT_PLAIN = 'plain'
    OUTPUT_FORMAT_JSON = 'json'
    OUTPUT_FORMAT_JSON_COLORED = 'json-color'
    OUTPUT_FORMAT_YAML = 'yaml'
    OUTPUT_FORMAT_YAML_COLORED = 'yaml-color'

    OUTPUT_FORMAT = [
        OUTPUT_FORMAT_PLAIN, OUTPUT_FORMAT_JSON, OUTPUT_FORMAT_JSON_COLORED, OUTPUT_FORMAT_YAML,
        OUTPUT_FORMAT_YAML_COLORED
    ]

    OUTPUT_VERBOSITY_SILENT = 'silent'
    OUTPUT_VERBOSITY_NORMAL = 'normal'
    OUTPUT_VERBOSITY_VERBOSE = 'verbose'
    OUTPUT_VERBOSITY_EXTENDED = 'extended'
    OUTPUT_VERBOSITY_RESULT_ONLY = 'results-only'

    OUTPUT_VERBOSITY = [
        OUTPUT_VERBOSITY_SILENT, OUTPUT_VERBOSITY_NORMAL, OUTPUT_VERBOSITY_VERBOSE, OUTPUT_VERBOSITY_EXTENDED,
        OUTPUT_VERBOSITY_RESULT_ONLY
    ]

    # list of all available Pygments styles (including ones loaded from plugins)
    # https://www.complang.tuwien.ac.at/doc/python-pygments/styles.html
    OUTPUT_STYLE = list(get_all_styles())

    WELCOME = """
    Welcome to {title} v{version}

    Press Ctrl-C to cancel the current command, and Ctrl-D to exit the shell.
    Type "help" to get help. Try TAB for auto-completion.
    """.format(title=style_crossbar('Crossbar.io Shell'), version=__version__)

    CONNECTED = """    Connection:

        url         : {url}
        authmethod  : {authmethod}
        realm       : {realm}
        authid      : {authid}
        authrole    : {authrole}
        session     : {session}
    """

    log = make_logger()

    def __init__(self):
        self.current_resource_type = None  # type: str
        self.current_resource = None
        self.session = None
        self._history = FileHistory('.cbsh-history')
        self._output_format = Application.OUTPUT_FORMAT_JSON_COLORED
        self._output_verbosity = Application.OUTPUT_VERBOSITY_NORMAL

        self._style = style_from_pygments_dict({
            Token.Toolbar: '#fce94f bg:#333333',

            # User input.
            # Token:          '#ff0066',

            # Prompt.
            # Token.Username: '#884444',
            # Token.At:       '#00aa00',
            # Token.Colon:    '#00aa00',
            # Token.Pound:    '#00aa00',
            # Token.Host:     '#000088 bg:#aaaaff',
            # Token.Path:     '#884444 underline',
        })

        self._output_style = 'fruity'

    @staticmethod
    def load_profile(dotdir=None, profile=None, yes_to_all=False, verbose=False):

        profile = profile or 'default'

        if not dotdir:
            if 'CROSSBAR_FABRIC_SUPERUSER' in os.environ:
                cbf_dir = os.path.abspath(os.path.dirname(os.environ['CROSSBAR_FABRIC_SUPERUSER']))
                if verbose:
                    click.echo('Using dotdir derived from CROSSBAR_FABRIC_SUPERUSER: {}'.format(style_ok(cbf_dir)))
            else:
                cbf_dir = os.path.abspath(os.path.expanduser('~/.crossbar'))
                if verbose:
                    click.echo('Using default dotdir: {}'.format(style_ok(cbf_dir)))
        else:
            cbf_dir = os.path.abspath(os.path.expanduser(dotdir))
            if verbose:
                click.echo('Using explicit dotdir: {}'.format(style_ok(cbf_dir)))

        if not os.path.isdir(cbf_dir):
            os.mkdir(cbf_dir)
            if verbose:
                click.echo('Created new local user directory: {}'.format(style_ok(cbf_dir)))

        config_path = os.path.join(cbf_dir, 'config.ini')
        if not os.path.isfile(config_path):
            with open(config_path, 'w') as f:
                url = _prompt_for_url(yes_to_all)
                f.write(_DEFAULT_CONFIG.format(url=url))
                if verbose:
                    click.echo('Created new local user configuration: {}'.format(style_ok(config_path)))
        else:
            if verbose:
                click.echo('Using existing local user configuration: {}'.format(style_ok(config_path)))

        config_obj = config.UserConfig(config_path)

        profile_obj = config_obj.profiles.get(profile, None)
        if not profile_obj:
            raise click.ClickException('no such profile: "{}"'.format(profile))
        else:
            if verbose:
                click.echo('Active user profile: {}'.format(style_ok(profile)))

        privkey_path = os.path.join(cbf_dir, profile_obj.privkey or '{}.priv'.format(profile))  # noqa: W503
        pubkey_path = os.path.join(cbf_dir, profile_obj.pubkey or '{}.pub'.format(profile))  # noqa: W503
        key_obj = UserKey(privkey_path, pubkey_path, yes_to_all=yes_to_all)

        return key_obj, profile_obj

    def set_output_format(self, output_format):
        """
        Set command output format.

        :param output_format: The verbosity to use.
        :type output_format: str
        """
        if output_format in Application.OUTPUT_FORMAT:
            self._output_format = output_format
        else:
            raise Exception('invalid value {} for output_format (not in {})'.format(
                output_format, Application.OUTPUT_FORMAT))

    def set_output_verbosity(self, output_verbosity):
        """
        Set command output verbosity.

        :param output_verbosity: The verbosity to use.
        :type output_verbosity: str
        """
        if output_verbosity in Application.OUTPUT_VERBOSITY:
            self._output_verbosity = output_verbosity
        else:
            raise Exception('invalid value {} for output_verbosity (not in {})'.format(
                output_verbosity, Application.OUTPUT_VERBOSITY))

    def set_output_style(self, output_style):
        """
        Set pygments syntax highlighting style ("theme") to be used for command result output.

        :param output_style: The style to use.
        :type output_style: str
        """
        if output_style in Application.OUTPUT_STYLE:
            self._output_style = output_style
        else:
            raise Exception('invalid value {} for output_style (not in {})'.format(output_style,
                                                                                   Application.OUTPUT_STYLE))

    def error(self, msg):
        click.echo()

    def format_selected(self):
        return '{} -> {}.\n'.format(self.current_resource_type, self.current_resource)

    def print_selected(self):
        click.echo(self.format_selected())

    def selected(self):
        return self.current_resource_type, self.current_resource

    def __str__(self):
        return 'Application(current_resource_type={}, current_resource={})'.format(self.current_resource_type,
                                                                                   self.current_resource)

    async def run_command(self, cmd):
        try:
            result = await cmd.run(self.session)
        except Exception as e:
            print(e)
        else:
            self._output_result(result)

    def _output_result(self, result):
        cmd_str = ' '.join(["crossbar", "shell"] + sys.argv[1:])
        if self._output_format in [Application.OUTPUT_FORMAT_JSON, Application.OUTPUT_FORMAT_JSON_COLORED]:

            json_str = json.dumps(result.result,
                                  separators=(', ', ': '),
                                  sort_keys=False,
                                  indent=4,
                                  ensure_ascii=False)

            if self._output_format == Application.OUTPUT_FORMAT_JSON_COLORED:
                console_str = highlight(json_str, lexers.JsonLexer(),
                                        formatters.Terminal256Formatter(style=self._output_style))
            else:
                console_str = json_str

        elif self._output_format in [Application.OUTPUT_FORMAT_YAML, Application.OUTPUT_FORMAT_YAML_COLORED]:

            yaml_str = yaml.safe_dump(result.result)

            if self._output_format == Application.OUTPUT_FORMAT_YAML_COLORED:
                console_str = highlight(yaml_str, lexers.YamlLexer(),
                                        formatters.Terminal256Formatter(style=self._output_style))
            else:
                console_str = yaml_str

        elif self._output_format == Application.OUTPUT_FORMAT_PLAIN:

            console_str = '{}'.format(result)

        else:
            # should not arrive here
            raise Exception('internal error: unprocessed value "{}" for output format'.format(self._output_format))

        # output command metadata (such as runtime)
        if self._output_verbosity == Application.OUTPUT_VERBOSITY_SILENT:
            pass
        else:
            # output result of command
            click.echo(console_str)

            if self._output_verbosity == Application.OUTPUT_VERBOSITY_RESULT_ONLY or self._output_format == Application.OUTPUT_FORMAT_PLAIN:
                pass
            elif self._output_verbosity == Application.OUTPUT_VERBOSITY_NORMAL:
                if result.duration:
                    click.echo(style_finished_line('Finished command in {} ms: {}'.format(result.duration, cmd_str)))
                else:
                    click.echo(style_finished_line('Finished command successfully: {}'.format(cmd_str)))
            elif self._output_verbosity == Application.OUTPUT_VERBOSITY_EXTENDED:
                if result.duration:
                    click.echo(
                        style_finished_line('Finished command in {} ms on {}: {}'.format(
                            result.duration, localnow(), cmd_str)))
                else:
                    click.echo(style_finished_line('Finished successfully on {}: {}'.format(localnow(), cmd_str)))
            else:
                # should not arrive here
                raise Exception('internal error')

    def _get_bottom_toolbar_tokens(self, cli):
        toolbar_str = ' Current resource path: {}'.format(self.format_selected())
        return [
            (Token.Toolbar, toolbar_str),
        ]

    def _get_prompt_tokens(self, cli):
        return [
            (Token.Username, 'john'),
            (Token.At, '@'),
            (Token.Host, 'localhost'),
            (Token.Colon, ':'),
            (Token.Path, '/user/john'),
            (Token.Pound, '# '),
        ]

    def run_context(self, ctx, command=None):

        # cfg contains the command lines options and arguments that
        # click collected for us
        cfg = ctx.obj
        cmd = ctx.command.name

        self.log.info('{klass}.run_context: running shell command "{cmd}"', klass=self.__class__.__name__, cmd=cmd)

        yes_to_all = cfg.yes_to_all if hasattr(cfg, 'yes_to_all') else False

        # if cmd not in ['auth', 'shell']:
        #    raise click.ClickException('"{}" command can only be run in shell'.format(cmd))

        if self._output_verbosity == Application.OUTPUT_VERBOSITY_VERBOSE:
            click.echo('Crossbar.io Shell: {}'.format(style_ok('v{}'.format(__version__))))

        # load user profile and key for given profile name
        key, profile = self.load_profile(dotdir=cfg.dotdir,
                                         profile=cfg.profile,
                                         yes_to_all=yes_to_all,
                                         verbose=(ctx.command.name == 'init'))

        if ctx.command.name == 'init':
            return

        # set the Fabric URL to connect to from the profile or default
        url = profile.url or 'wss://fabric.crossbario.com'

        # users always authenticate with the user_id from the key, which
        # filled from the email the user provided
        authid = key.user_id

        # the realm can be set from command line, env var, the profile
        # or can be None, which means the user will be joined to the global
        # Crossbar.io users realm ('com.crossbario.fabric')
        realm = cfg.realm or profile.realm or None

        # the authrole can be set from command line, env var, the profile
        # or can be None, in which case the role is chosen automatically
        # from the list of roles the user us authorized for
        authrole = cfg.role or profile.role or None

        # this will be fired when the ShellClient below actually has joined
        # the respective realm on Crossbar.io (either the global users
        # realm, or a management realm the user has a role on)
        done = txaio.create_future()

        url_is_secure, _, _, _, _, _ = parse_url(url)

        extra = {
            # these are forward on the actual client connection
            'authid': authid,
            'authrole': authrole,

            # these are native Python object and only used client-side
            'key': key.key,
            'done': done,
            'command': command,

            # WAMP-cryptosign authentication: TLS channel binding
            'channel_binding': 'tls-unique' if url_is_secure else None,
        }

        cert_options = None
        if profile.tls_hostname:
            self.log.info('Setting up TLS context (server CA/intermediate certificates, etc) from profile:')
            tls_config = {'hostname': profile.tls_hostname, 'ca_certificates': profile.tls_certificates}
            cert_options = _create_tls_client_context(tls_config, '.crossbar', self.log)

        # for the "auth" command, forward additional command line options
        if ctx.command.name == 'auth':
            # user provides authentication code to verify
            extra['activation_code'] = cfg.code

            # user requests sending of a new authentication code (while an old one is still pending)
            extra['request_new_activation_code'] = cfg.new_code

        # this is the WAMP ApplicationSession that connects the CLI to Crossbar.io
        self.session = client.ShellClient(ComponentConfig(realm, extra))

        runner = ApplicationRunner(url, realm, ssl=cert_options)

        if self._output_verbosity == Application.OUTPUT_VERBOSITY_VERBOSE:
            click.echo('Connecting to {} ..'.format(url))

        connect_done = runner.run(self.session, start_reactor=False)

        def on_connect_success(res):
            self.log.info('{klass}.on_connect_success(res={res})', klass=self.__class__.__name__, res=pformat(res))

        def on_connect_error(err):
            self.log.warn('{klass}.on_connect_error(err={err})', klass=self.__class__.__name__, err=err)

            if isinstance(err, Failure):
                err = err.value

            txaio.reject(done, err)

            # raise SystemExit(1)

        txaio.add_callbacks(connect_done, on_connect_success, on_connect_error)

        def on_success(res):
            self.log.info('{klass}.on_success(res={res})', klass=self.__class__.__name__, res=pformat(res))

            session_details, result = res

            if cmd == 'auth':

                self._print_welcome(url, session_details)

            elif cmd == 'shell':

                # click.clear()
                self._print_welcome(url, session_details)

                # FIXME:

                # prompt_kwargs = {
                #     'history': self._history,
                # }
                #
                # from crossbar.shell import repl
                #
                # shell_task = loop.create_task(
                #     repl.repl(
                #         ctx,
                #         get_bottom_toolbar_tokens=self._get_bottom_toolbar_tokens,
                #         # get_prompt_tokens=self._get_prompt_tokens,
                #         style=self._style,
                #         prompt_kwargs=prompt_kwargs))
                #
                # try:
                #     loop.run_until_complete(shell_task)
                # except Exception as e:
                #     print(e)

            else:
                if result:
                    self._output_result(result)

        def on_error(err):
            self.log.warn('{klass}.on_error(err={err})', klass=self.__class__.__name__, err=err)

            if isinstance(err, Failure):
                err = err.value

            if isinstance(err, ApplicationError):

                self.log.warn('{message} - {error}', message=err.args[0] if err.args else '', error=err.error)

                # some ApplicationErrors are actually signaling progress
                # in the authentication flow, some are real errors

                exit_code = None

                if err.error.startswith('fabric.auth-failed.'):
                    error = err.error.split('.')[2]
                    message = err.args[0]

                    if error == 'new-user-auth-code-sent':

                        click.echo('\nThanks for registering! {}'.format(message))
                        click.echo(
                            style_ok(
                                'Please check your inbox and run "crossbar shell auth --code <THE CODE YOU GOT BY EMAIL>.\n'
                            ))

                    elif error == 'registered-user-auth-code-sent':

                        click.echo('\nWelcome back! {}'.format(message))
                        click.echo(
                            style_ok(
                                'Please check your inbox and run "crossbar shell auth --code <THE CODE YOU GOT BY EMAIL>.\n'
                            ))

                    elif error == 'pending-activation':

                        click.echo()
                        click.echo(style_ok(message))
                        click.echo()
                        click.echo('Tip: to activate, run "crossbar shell auth --code <THE CODE YOU GOT BY EMAIL>"')
                        click.echo('Tip: you can request sending a new code with "crossbar shell auth --new-code"')
                        click.echo()

                    elif error == 'no-pending-activation':

                        exit_code = 1
                        click.echo()
                        click.echo(style_error('{} [{}]'.format(message, err.error)))
                        click.echo()

                    elif error == 'email-failure':

                        exit_code = 1
                        click.echo()
                        click.echo(style_error('{} [{}]'.format(message, err.error)))
                        click.echo()

                    elif error == 'invalid-activation-code':

                        exit_code = 1
                        click.echo()
                        click.echo(style_error('{} [{}]'.format(message, err.error)))
                        click.echo()

                    else:

                        exit_code = 1
                        click.echo(style_error('{}'.format(error)))
                        click.echo(style_error(message))

                elif err.error.startswith('crossbar.error.'):

                    error = err.error.split('.')[2]
                    message = err.args[0]

                    if error == 'invalid_configuration':

                        click.echo()
                        click.echo(style_error('{} [{}]'.format(message, err.error)))
                        click.echo()
                    else:

                        exit_code = 1
                        click.echo(style_error('{} [{}]'.format(message, err.error)))

                else:

                    click.echo(style_error('{}'.format(err)))
                    exit_code = 1

                if exit_code:
                    raise SystemExit(exit_code)

            else:
                click.echo(style_error('{}'.format(err)))
                raise SystemExit(1)

        txaio.add_callbacks(done, on_success, on_error)

        def doit(reactor):
            return done

        react(doit)

    def _print_welcome(self, url, session_details):
        click.echo(self.WELCOME)
        click.echo(
            self.CONNECTED.format(url=url,
                                  realm=style_crossbar(session_details.realm) if session_details else None,
                                  authmethod=session_details.authmethod if session_details else None,
                                  authid=style_crossbar(session_details.authid) if session_details else None,
                                  authrole=style_crossbar(session_details.authrole) if session_details else None,
                                  session=session_details.session if session_details else None))

###############################################################################
#
# Crossbar.io Shell
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

import os
import shlex
import sys
import six
from collections import defaultdict

import click
import click._bashcomplete
import click.parser

from prompt_toolkit import prompt
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import style_from_pygments_dict
from pygments.token import Token

from autobahn.wamp.exception import ApplicationError

from crossbar.shell.util import style_error


def _get_bottom_toolbar_tokens(cli):
    return [(Token.Toolbar, ' This is a toolbar. ')]


_style = style_from_pygments_dict({
    Token.Toolbar: '#ffffff bg:#333333',
})


class InternalCommandException(Exception):
    pass


class ExitReplException(InternalCommandException):
    pass


_internal_commands = dict()


def _register_internal_command(names, target, description=None):
    if not hasattr(target, '__call__'):
        raise ValueError('Internal command must be a callable')

    if isinstance(names, six.string_types):
        names = [names]
    elif not isinstance(names, (list, tuple)):
        raise ValueError('"names" must be a string or a list / tuple')

    for name in names:
        _internal_commands[name] = (target, description)


def _get_registered_target(name, default=None):
    target_info = _internal_commands.get(name)
    if target_info:
        return target_info[0]
    return default


def _exit_internal():
    raise ExitReplException()


def _help_internal():
    formatter = click.HelpFormatter()
    formatter.write_heading('REPL help')
    formatter.indent()
    with formatter.section('External Commands'):
        formatter.write_text('prefix external commands with "!"')
    with formatter.section('Internal Commands'):
        formatter.write_text('prefix internal commands with ":"')
        info_table = defaultdict(list)  # type: ignore
        for mnemonic, target_info in six.iteritems(_internal_commands):
            info_table[target_info[1]].append(mnemonic)
        formatter.write_dl((', '.join((':{0}'.format(mnemonic) for mnemonic in sorted(mnemonics))), description)
                           for description, mnemonics in six.iteritems(info_table))
    return formatter.getvalue()


_register_internal_command(['q', 'quit', 'exit'], _exit_internal, 'exits the repl')
_register_internal_command(['?', 'h', 'help'], _help_internal, 'displays general help information')


class ClickCompleter(Completer):
    def __init__(self, cli):
        self.cli = cli

    def get_completions(self, document, complete_event=None):
        # Code analogous to click._bashcomplete.do_complete

        try:
            args = shlex.split(document.text_before_cursor)
        except ValueError:
            # Invalid command, perhaps caused by missing closing quotation.
            return

        cursor_within_command = \
            document.text_before_cursor.rstrip() == document.text_before_cursor

        if args and cursor_within_command:
            # We've entered some text and no space, give completions for the
            # current word.
            incomplete = args.pop()
        else:
            # We've not entered anything, either at all or for the current
            # command, so give all relevant completions for this context.
            incomplete = ''

        # FIXME
        _bc = click._bashcomplete  # type: ignore
        ctx = _bc.resolve_ctx(self.cli, '', args)
        if ctx is None:
            return

        cmds = []
        c = ctx
        while c:
            cmds.append(c.command.name)
            c = c.parent
        cmds.reverse()

        # print(cmds)
        # if ctx.parent:
        #    print('COMMAND: ', ctx.parent.command.name)
        # pprint(dir(ctx.command))
        # print(document.get_word_before_cursor())
        # print(document.get_word_before_cursor(WORD=True))

        choices = []
        for param in ctx.command.params:
            if not isinstance(param, click.Option):
                continue
            for options in (param.opts, param.secondary_opts):
                for o in options:
                    choices.append(Completion(o, -len(incomplete), display_meta=param.help))

        if isinstance(ctx.command, click.MultiCommand):
            for name in ctx.command.list_commands(ctx):
                command = ctx.command.get_command(ctx, name)  # type: ignore
                choices.append(Completion(name, -len(incomplete), display_meta=getattr(command, 'short_help')))

        for item in choices:
            if item.text.startswith(incomplete):
                yield item


def continuation_tokens(cli, width):
    " The continuation: display dots before all the following lines. "

    # (make sure that the width of the continuation does not exceed the given
    # width. -- It is the prompt that decides the width of the left margin.)
    return [(Token, '.' * (width - 1) + ' ')]


async def repl(old_ctx,
               prompt_kwargs=None,
               allow_system_commands=True,
               allow_internal_commands=True,
               once=False,
               get_bottom_toolbar_tokens=_get_bottom_toolbar_tokens,
               get_prompt_tokens=None,
               style=_style):
    """
    Start an interactive shell. All subcommands are available in it.

    :param old_ctx: The current Click context.
    :param prompt_kwargs: Parameters passed to
        :py:func:`prompt_toolkit.shortcuts.prompt`.

    If stdin is not a TTY, no prompt will be printed, but only commands read
    from stdin.

    """
    # parent should be available, but we're not going to bother if not
    group_ctx = old_ctx.parent or old_ctx
    group = group_ctx.command
    isatty = sys.stdin.isatty()

    # Delete the REPL command from those available, as we don't want to allow
    # nesting REPLs (note: pass `None` to `pop` as we don't want to error if
    # REPL command already not present for some reason).
    repl_command_name = old_ctx.command.name
    available_commands = group_ctx.command.commands
    available_commands.pop(repl_command_name, None)

    if isatty:
        prompt_kwargs = prompt_kwargs or {}
        if not get_prompt_tokens:
            prompt_kwargs.setdefault('message', u'>> ')
        history = prompt_kwargs.pop('history', None) \
            or InMemoryHistory()
        completer = prompt_kwargs.pop('completer', None) \
            or ClickCompleter(group)

        def get_command():
            return prompt(
                completer=completer,
                history=history,
                # patch_stdout=False,
                # https://github.com/jonathanslenders/python-prompt-toolkit/blob/master/examples/get-multiline-input.py
                # multiline=True,
                # get_continuation_tokens=continuation_tokens,
                # get_bottom_toolbar_tokens=get_bottom_toolbar_tokens,
                # get_prompt_tokens=get_prompt_tokens,
                style=style,
                async_=True,
                **prompt_kwargs)
    else:
        get_command = sys.stdin.readline

    stopped = False
    while not stopped:
        try:
            command = await get_command()
        except KeyboardInterrupt:
            continue
        except EOFError:
            break
        finally:
            if once:
                stopped = True

        if not command:
            if isatty:
                continue
            else:
                break

        if allow_system_commands and dispatch_repl_commands(command):
            continue

        if allow_internal_commands:
            try:
                result = handle_internal_commands(command)
                if isinstance(result, six.string_types):
                    click.echo(result)
                    continue
            except ExitReplException:
                break

        args = shlex.split(command)

        try:
            with group.make_context(None, args, parent=group_ctx) as ctx:
                f = group.invoke(ctx)
                if f:
                    await f
                ctx.exit()

        except ApplicationError as e:
            click.echo(style_error(u'[{}] {}'.format(e.error, e.args[0])))

        except click.ClickException as e:
            e.show()

        except SystemExit:
            pass


def register_repl(group, name='repl'):
    """Register :func:`repl()` as sub-command *name* of *group*."""
    group.command(name=name)(click.pass_context(repl))


def dispatch_repl_commands(command):
    """Execute system commands entered in the repl.

    System commands are all commands starting with "!".

    """
    if command.startswith('!'):
        os.system(command[1:])  # nosec
        return True

    return False


def handle_internal_commands(command):
    """Run repl-internal commands.

    Repl-internal commands are all commands starting with ":".

    """
    if command.startswith(':'):
        target = _get_registered_target(command[1:], default=None)
        if target:
            return target()

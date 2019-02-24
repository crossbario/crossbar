#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#
#  Unless a separate license agreement exists between you and Crossbar.io GmbH (e.g.
#  you have purchased a commercial license), the license terms below apply.
#
#  Should you enter into a separate license agreement after having received a copy of
#  this software, then the terms of such license agreement replace the terms below at
#  the time at which such license agreement becomes effective.
#
#  In case a separate license agreement ends, and such agreement ends without being
#  replaced by another separate license agreement, the license terms below apply
#  from the time at which said agreement ends.
#
#  LICENSE TERMS
#
#  This program is free software: you can redistribute it and/or modify it under the
#  terms of the GNU Affero General Public License, version 3, as published by the
#  Free Software Foundation. This program is distributed in the hope that it will be
#  useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  See the GNU Affero General Public License Version 3 for more details.
#
#  You should have received a copy of the GNU Affero General Public license along
#  with this program. If not, see <http://www.gnu.org/licenses/agpl-3.0.en.html>.
#
#####################################################################################

import sys
import os
import shutil
import pkg_resources
import jinja2

from txaio import make_logger

__all__ = ('Templates',)


log = make_logger()


class Templates:

    """
    Crossbar.io application templates.
    """

    SKIP_FILES = ('.pyc', '.pyo', '.exe')
    """
    File extensions of files to skip when instantiating an application template.
    """

    TEMPLATES = {
        'default': {
            'name': 'default',
            'help': 'A WAMP router speaking WebSocket plus a static Web server.',
            'basedir': "node/templates/default",
            'params': {
            },
            'skip_jinja': ['autobahn.js', 'autobahn.min.js', 'autobahn.min.jgz']
        }
    }
    """
    Application template definitions.
    """

    @staticmethod
    def help():
        """
        Print CLI help.
        """
        print("\nAvailable Crossbar.io node templates:\n")
        for name, template in Templates.TEMPLATES.values():
            print("  {} {}".format(name.ljust(16, ' '), template['help']))
        print("")

    @staticmethod
    def init(appdir, template='default', params=None, dryrun=False, skip_existing=True):
        """
        Initialize an application directory from a template by template name.

        :param appdir: The path of the directory to instantiate the application template in.
        :type appdir: str

        :param template: The name of the application template to instantiate.
        :type template: str

        :param dryrun: If `True`, only perform a dry run (don't actually do anything, only prepare).
        :type dryrun: bool
        """
        IS_WIN = sys.platform.startswith("win")

        template = Templates.TEMPLATES.get(template, None)
        if not template:
            raise Exception('no such application directory template: "{}"'.format(template))

        basedir = pkg_resources.resource_filename("crossbar", template['basedir'])
        if IS_WIN:
            basedir = basedir.replace('\\', '/')  # Jinja need forward slashes even on Windows
        log.info("Using template from '{dir}'", dir=basedir)

        appdir = os.path.abspath(appdir)

        if 'jinja' in template:
            kwargs = template['jinja']
        else:
            kwargs = {}

        jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(basedir),
                                       keep_trailing_newline=True,
                                       autoescape=True,
                                       **kwargs)

        _params = template['params'].copy()
        if params:
            _params.update(params)

        created = []
        try:
            for root, dirs, files in os.walk(basedir):
                for d in dirs:
                    reldir = os.path.relpath(os.path.join(root, d), basedir)
                    if 'appname' in _params:
                        reldir = reldir.replace('appname', _params['appname'])
                    create_dir_path = os.path.join(appdir, reldir)

                    if os.path.isdir(create_dir_path):
                        msg = "Directory {} already exists".format(create_dir_path)
                        if not skip_existing:
                            log.info(msg)
                            raise Exception(msg)
                        else:
                            log.warn("{msg} - SKIPPING", msg=msg)
                    else:
                        log.info("Creating directory {dir}", dir=create_dir_path)
                        if not dryrun:
                            os.mkdir(create_dir_path)
                        created.append(('dir', create_dir_path))

                for f in files:

                    if not f.endswith(Templates.SKIP_FILES):

                        src_file = os.path.abspath(os.path.join(root, f))
                        src_file_rel_path = os.path.relpath(src_file, basedir)
                        reldir = os.path.relpath(root, basedir)
                        if 'appname' in _params:
                            reldir = reldir.replace('appname', _params['appname'])
                            f = f.replace('appname', _params['appname'])
                        dst_dir_path = os.path.join(appdir, reldir)
                        dst_file = os.path.abspath(os.path.join(dst_dir_path, f))

                        if os.path.isfile(dst_file):
                            msg = "File {} already exists".format(dst_file)
                            if not skip_existing:
                                log.info(msg)
                                raise Exception(msg)
                            else:
                                log.warn("{msg} - SKIPPING", msg=msg)
                        else:
                            log.info("Creating file {name}", name=dst_file)
                            if not dryrun:
                                if f in template.get('skip_jinja', []):
                                    shutil.copy(src_file, dst_file)
                                else:
                                    with open(dst_file, 'wb') as dst_file_fd:
                                        if IS_WIN:
                                            # Jinja need forward slashes even on Windows
                                            src_file_rel_path = src_file_rel_path.replace('\\', '/')
                                        page = jinja_env.get_template(src_file_rel_path)
                                        contents = page.render(**_params).encode('utf8')
                                        dst_file_fd.write(contents)

                            created.append(('file', dst_file))

            # force exception to test rollback
            # a = 1/0

            return template.get('get_started_hint', None)

        except Exception:
            log.failure("Something went wrong while instantiating app template - rolling back changes ..")
            for ptype, path in reversed(created):
                if ptype == 'file':
                    try:
                        log.info("Removing file {path}", path=path)
                        if not dryrun:
                            os.remove(path)
                    except:
                        log.warn("Warning: could not remove file {path}", path=path)
                elif ptype == 'dir':
                    try:
                        log.info("Removing directory {path}", path=path)
                        if not dryrun:
                            os.rmdir(path)
                    except:
                        log.warn("Warning: could not remove directory {path}", path=path)
                else:
                    raise Exception("logic error")
            raise

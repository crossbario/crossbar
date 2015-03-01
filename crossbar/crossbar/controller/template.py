#####################################################################################
#
#  Copyright (C) Tavendo GmbH
#
#  Unless a separate license agreement exists between you and Tavendo GmbH (e.g. you
#  have purchased a commercial license), the license terms below apply.
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

__all__ = ('Templates',)


class Templates:

    """
    Crossbar.io application templates.
    """

    SKIP_FILES = ('.pyc', '.pyo', '.exe')
    """
   File extensions of files to skip when instantiating an application template.
   """

    TEMPLATES = [
        {
            "name": "default",
            "help": "A WAMP router speaking WebSocket plus a static Web server.",
            "basedir": "templates/default",
            "params": {
            }
        },

        {
            "name": "hello:python",
            "help": "A minimal Python WAMP application hosted in a router and a HTML5 client.",
            "basedir": "templates/hello/python",
            "params": {
                "appname": "hello",
                "realm": "realm1",
            }
        },

        {
            "name": "hello:nodejs",
            "help": "A minimal NodeJS WAMP application hosted in a router and a HTML5 client.",
            "get_started_hint": "Now install dependencies by doing 'npm install', start Crossbar using 'crossbar start' and open http://localhost:8080 in your browser.",
            "basedir": "templates/hello/nodejs",
            "params": {
                "appname": "hello",
                "realm": "realm1",
                "url": "ws://127.0.0.1:8080/ws"
            }
        },

        {
            "name": "hello:browser",
            "help": "A minimal JavaAScript WAMP application with two components running in the browser.",
            "get_started_hint": "Start Crossbar using 'crossbar start' and open http://localhost:8080 in your browser.",
            "basedir": "templates/hello/browser",
            "params": {
                "realm": "realm1",
            }
        },


        {
            "name": "hello:cpp",
            "help": "A minimal C++11/AutobahnCpp WAMP application hosted in a router and a HTML5 client.",
            "get_started_hint": "Now build the example by doing 'scons', start Crossbar using 'crossbar start' and open http://localhost:8080 in your browser.",
            "basedir": "templates/hello/cpp",
            "params": {
            },
        },

        {
            "name": "hello:csharp",
            "help": "A minimal C#/WampSharp WAMP application hosted in a router and a HTML5 client.",
            "get_started_hint": "Now build by opening 'src/Hello/Hello.sln' in Visual Studio, start Crossbar using 'crossbar start' and open http://localhost:8080 in your browser.",
            "basedir": "templates/hello/csharp",
            "params": {
            },
            "skip_jinja": []
        },

        {
            "name": "hello:erlang",
            "help": "A minimal Erlang/Erwa WAMP application hosted in a router and a HTML5 client.",
            "get_started_hint": "Now build the Erlang/Erwa client by entering 'make', start Crossbar using 'crossbar start' and open http://localhost:8080 in your browser.",
            "basedir": "templates/hello/erlang",
            "params": {
            },

            # due to Erlang's common use of "{{" and "}}" in syntax, we reconfigure
            # the escape characters used in Jinja templates
            "jinja": {
                "block_start_string": "@@",
                "block_end_string": "@@",
                "variable_start_string": "@=",
                "variable_end_string": "=@",
                "comment_start_string": "@#",
                "comment_end_string": "#@",
            },

            # we need to skip binary files from being processed by Jinja
            #
            "skip_jinja": ["relx"]
        },

        {
            "name": "hello:php",
            "help": "A minimal PHP/Thruway WAMP application hosted in a router and a HTML5 client.",
            "get_started_hint": "Now install dependencies for the PHP/Thruway client by entering 'make install', start Crossbar using 'crossbar start' and open http://localhost:8080 in your browser.",
            "basedir": "templates/hello/php",
            "params": {
            },
        },

        {
            "name": "hello:java",
            "help": "A minimal Java/jawampa WAMP application hosted in a router and a HTML5 client.",
            "get_started_hint": "Please follow the README.md to build the Java component first, then start Crossbar using 'crossbar start' and open http://localhost:8080 in your browser.",
            "basedir": "templates/hello/java",
            "params": {
            },
        },

        {
            "name": "hello:tessel",
            "help": "A minimal JavaScript/wamp-tessel WAMP application running on a Tessel and with a HTML5 client.",
            "get_started_hint": "Please follow the README.md to install npm dependencies, then start Crossbar using 'crossbar start', open http://localhost:8080 in your browser, and do 'tessel run tessel/hello.js'.",
            "basedir": "templates/hello/tessel",
            "params": {
            },
        },

    ]
    """
   Application template definitions.
   """

    def help(self):
        """
        Print CLI help.
        """
        print("\nAvailable Crossbar.io node templates:\n")
        for t in self.TEMPLATES:
            print("  {} {}".format(t['name'].ljust(16, ' '), t['help']))
        print("")

    def __contains__(self, template):
        """
        Check if template exists.

        :param template: The name of the application template to check.
        :type template: str
        """
        for t in self.TEMPLATES:
            if t['name'] == template:
                return True
        return False

    def __getitem__(self, template):
        """
        Get template by name.

        :param template: The name of the application template to get.
        :type template: str
        """
        for t in self.TEMPLATES:
            if t['name'] == template:
                return t
        raise KeyError

    def init(self, appdir, template, params=None, dryrun=False):
        """
        Ctor.


        :param appdir: The path of the directory to instantiate the application template in.
        :type appdir: str
        :param template: The name of the application template to instantiate.
        :type template: str
        :param dryrun: If `True`, only perform a dry run (don't actually do anything, only prepare).
        :type dryrun: bool
        """
        IS_WIN = sys.platform.startswith("win")

        template = self.__getitem__(template)
        basedir = pkg_resources.resource_filename("crossbar", template['basedir'])
        if IS_WIN:
            basedir = basedir.replace('\\', '/')  # Jinja need forward slashes even on Windows
        print("Using template from '{}'".format(basedir))

        appdir = os.path.abspath(appdir)

        if 'jinja' in template:
            kwargs = template['jinja']
        else:
            kwargs = {}

        jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(basedir),
                                       keep_trailing_newline=True, **kwargs)

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

                    print("Creating directory {}".format(create_dir_path))
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

                        print("Creating file      {}".format(dst_file))
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

        except Exception as e:
            print("Error encountered ({}) - rolling back".format(e))
            for ptype, path in reversed(created):
                if ptype == 'file':
                    try:
                        print("Removing file {}".format(path))
                        if not dryrun:
                            os.remove(path)
                    except:
                        print("Warning: could not remove file {}".format(path))
                elif ptype == 'dir':
                    try:
                        print("Removing directory {}".format(path))
                        if not dryrun:
                            os.rmdir(path)
                    except:
                        print("Warning: could not remove directory {}".format(path))
                else:
                    raise Exception("logic error")
            raise e

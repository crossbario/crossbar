###############################################################################
##
##  Copyright (C) 2014 Tavendo GmbH
##
##  This program is free software: you can redistribute it and/or modify
##  it under the terms of the GNU Affero General Public License, version 3,
##  as published by the Free Software Foundation.
##
##  This program is distributed in the hope that it will be useful,
##  but WITHOUT ANY WARRANTY; without even the implied warranty of
##  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
##  GNU Affero General Public License for more details.
##
##  You should have received a copy of the GNU Affero General Public License
##  along with this program. If not, see <http://www.gnu.org/licenses/>.
##
###############################################################################

__all__ = ['Templates']


import sys
import os
import pkg_resources
import jinja2



class Templates:
   """
   """

   TEMPLATES = {
      "default": {
         "help": "A WAMP router speaking WebSocket plus Web server.",
         "basedir": "templates/default",
         "params": {
         }
      },
      "pusher": {
         "help": "A WAMP router with a HTTP gateway for pushing events.",
         "basedir": "templates/pusher",
         "params": {
         }
      },
      "hello:python": {
         "help": "A minimal Python WAMP application hosted in a router and a HTML5 client.",
         "basedir": "templates/hello/python",
         "params": {
            "appname": "hello",
            "realm": "realm1",
         }
      },
      "hello:nodejs": {
         "help": "A minimal NodeJS WAMP application hosted in a router and a HTML5 client.",
         "basedir": "templates/hello/nodejs",
         "params": {
            "appname": "hello",
            "realm": "realm1",
            "url": "ws://127.0.0.1:8080/ws",
            "nodejs": "/usr/bin/node"
         }
      },
      "hello:erwa": {
         "help": "A minimal Erlang/Erwa WAMP application hosted in a router and a HTML5 client.",
         "basedir": "templates/hello/erwa",
         "params": {
            "appname": "hello",
            "realm": "realm1",
         }
      },
   }


   def help(self):
      """
      """
      print("\nAvailable Crossbar.io node templates:\n")
      for t in self.TEMPLATES:
         print("  {} {}".format(t.ljust(20, ' '), self.TEMPLATES[t]['help']))
      print("")



   def __contains__(self, template):
      """
      """
      return template in self.TEMPLATES



   def init(self, appdir, template, params = None, dryrun = False):
      """
      """
      IS_WIN = sys.platform.startswith("win")

      template = self.TEMPLATES[template]
#      basedir = os.path.abspath(pkg_resources.resource_filename("crossbar", template['basedir']))
      basedir = pkg_resources.resource_filename("crossbar", template['basedir'])
      if IS_WIN:
         basedir = basedir.replace('\\', '/') # Jinja need forward slashes even on Windows
      #print("Using templates from '{}'".format(basedir))

      appdir = os.path.abspath(appdir)

      jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(basedir),
         keep_trailing_newline = True)

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
               ## FIXME
               if not f.endswith(".pyc") and f not in ['relx']:
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
                     with open(dst_file, 'wb') as dst_file_fd:
                        if IS_WIN:
                           # Jinja need forward slashes even on Windows
                           src_file_rel_path = src_file_rel_path.replace('\\', '/')
                        page = jinja_env.get_template(src_file_rel_path)
                        contents = page.render(**_params).encode('utf8')
                        dst_file_fd.write(contents)

                  created.append(('file', dst_file))

         # force exception to test rollback
         #a = 1/0

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

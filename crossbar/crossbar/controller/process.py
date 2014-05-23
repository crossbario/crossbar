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


from __future__ import absolute_import

__all__ = ['create_process_env']

import os



def create_process_env(options):
   """
   Create worker process environment dictionary.
   """
   penv = {}

   ## by default, a worker/guest process inherits
   ## complete environment
   inherit_all = True

   ## check/inherit parent process environment
   if 'env' in options and 'inherit' in options['env']:
      inherit = options['env']['inherit']
      if type(inherit) == bool:
         inherit_all = inherit
      elif type(inherit) == list:
         inherit_all = False
         for v in inherit:
            if v in os.environ:
               penv[v] = os.environ[v]

   if inherit_all:
      ## must do deepcopy like this (os.environ is a "special" thing ..)
      for k, v in os.environ.items():
         penv[k] = v

   ## explicit environment vars from config
   if 'env' in options and 'vars' in options['env']:
      for k, v in options['env']['vars'].items():
         penv[k] = v

   return penv



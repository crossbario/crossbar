PROMPT -- Setting optimize level --

/*
11g
ALTER SESSION SET PLSQL_OPTIMIZE_LEVEL = 3;
ALTER SESSION SET plsql_code_type = 'NATIVE';
*/
ALTER SESSION SET plsql_optimize_level = 2;

/*
This software has been released under the MIT license:

  Copyright (c) 2010 Jonas Krogsboell inspired by code from Lewis R Cunningham

  Permission is hereby granted, free of charge, to any person obtaining a copy
  of this software and associated documentation files (the "Software"), to deal
  in the Software without restriction, including without limitation the rights
  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
  copies of the Software, and to permit persons to whom the Software is
  furnished to do so, subject to the following conditions:

  The above copyright notice and this permission notice shall be included in
  all copies or substantial portions of the Software.

  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
  THE SOFTWARE.
*/
PROMPT -----------------------------------;
PROMPT -- Compiling objects for PL/JSON --;
PROMPT -----------------------------------;
@@uninstall.sql
@@json_value.sql
@@json_list.sql
@@json.sql
@@json_parser.sql
@@json_printer.sql
@@json_value_body.sql
@@json_ext.sql --extra helper functions
@@json_body.sql
@@json_list_body.sql
--@@grantsandsynonyms.sql --grants to core API
@@json_ac.sql --wrapper TO enhance autocompletion

PROMPT ------------------------------------------;
PROMPT -- Adding optional packages for PL/JSON --;
PROMPT ------------------------------------------;
@@addons/json_dyn.sql --dynamic SQL EXECUTE
@@addons/jsonml.sql --jsonml (xml TO json)
@@addons/json_xml.sql --json TO xml copied FROM http://www.json.org/java/org/json/xml.java
@@addons/json_util_pkg.sql --dynamic SQL FROM http://ora-00001.blogspot.com/2010/02/ref-cursor-to-json.html
@@addons/json_helper.sql --SET operations ON json and json_list

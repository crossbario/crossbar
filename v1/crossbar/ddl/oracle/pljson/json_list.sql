CREATE OR REPLACE TYPE json_list
   AS OBJECT
(
   /*
   Copyright (c) 2010 Jonas Krogsboell

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

   list_data json_value_array,
   CONSTRUCTOR FUNCTION json_list
      RETURN SELF AS RESULT,
   CONSTRUCTOR FUNCTION json_list (str VARCHAR2)
      RETURN SELF AS RESULT,
   CONSTRUCTOR FUNCTION json_list (str CLOB)
      RETURN SELF AS RESULT,
   CONSTRUCTOR FUNCTION json_list (CAST json_value)
      RETURN SELF AS RESULT,
   MEMBER PROCEDURE append (
      self       IN OUT NOCOPY json_list,
      elem                     json_value,
      position                 PLS_INTEGER DEFAULT NULL),
   MEMBER PROCEDURE append (
      self       IN OUT NOCOPY json_list,
      elem                     VARCHAR2,
      position                 PLS_INTEGER DEFAULT NULL),
   MEMBER PROCEDURE append (
      self       IN OUT NOCOPY json_list,
      elem                     NUMBER,
      position                 PLS_INTEGER DEFAULT NULL),
   MEMBER PROCEDURE append (
      self       IN OUT NOCOPY json_list,
      elem                     BOOLEAN,
      position                 PLS_INTEGER DEFAULT NULL),
   MEMBER PROCEDURE append (
      self       IN OUT NOCOPY json_list,
      elem                     json_list,
      position                 PLS_INTEGER DEFAULT NULL),
   MEMBER PROCEDURE REPLACE (self       IN OUT NOCOPY json_list,
                             position                 PLS_INTEGER,
                             elem                     json_value),
   MEMBER PROCEDURE REPLACE (self       IN OUT NOCOPY json_list,
                             position                 PLS_INTEGER,
                             elem                     VARCHAR2),
   MEMBER PROCEDURE REPLACE (self       IN OUT NOCOPY json_list,
                             position                 PLS_INTEGER,
                             elem                     NUMBER),
   MEMBER PROCEDURE REPLACE (self       IN OUT NOCOPY json_list,
                             position                 PLS_INTEGER,
                             elem                     BOOLEAN),
   MEMBER PROCEDURE REPLACE (self       IN OUT NOCOPY json_list,
                             position                 PLS_INTEGER,
                             elem                     json_list),
   MEMBER FUNCTION COUNT
      RETURN NUMBER,
   MEMBER PROCEDURE remove (self       IN OUT NOCOPY json_list,
                            position                 PLS_INTEGER),
   MEMBER PROCEDURE remove_first (self IN OUT NOCOPY json_list),
   MEMBER PROCEDURE remove_last (self IN OUT NOCOPY json_list),
   MEMBER FUNCTION get (position PLS_INTEGER)
      RETURN json_value,
   MEMBER FUNCTION head
      RETURN json_value,
   MEMBER FUNCTION LAST
      RETURN json_value,
   MEMBER FUNCTION tail
      RETURN json_list,
   /* Output methods */
   MEMBER FUNCTION TO_CHAR (spaces            BOOLEAN DEFAULT TRUE,
                            chars_per_line    NUMBER DEFAULT 0)
      RETURN VARCHAR2,
   MEMBER PROCEDURE TO_CLOB (
      self             IN            json_list,
      buf              IN OUT NOCOPY CLOB,
      spaces                         BOOLEAN DEFAULT FALSE,
      chars_per_line                 NUMBER DEFAULT 0,
      erase_clob                     BOOLEAN DEFAULT TRUE),
   MEMBER PROCEDURE PRINT (self             IN json_list,
                           spaces              BOOLEAN DEFAULT TRUE,
                           chars_per_line      NUMBER DEFAULT 8192,
                           jsonp               VARCHAR2 DEFAULT NULL), --32512 is maximum
   MEMBER PROCEDURE HTP (self             IN json_list,
                         spaces              BOOLEAN DEFAULT FALSE,
                         chars_per_line      NUMBER DEFAULT 0,
                         jsonp               VARCHAR2 DEFAULT NULL),
   /* json path */
   MEMBER FUNCTION PATH (json_path VARCHAR2, base NUMBER DEFAULT 1)
      RETURN json_value,
   /* json path_put */
   MEMBER PROCEDURE path_put (self        IN OUT NOCOPY json_list,
                              json_path                 VARCHAR2,
                              elem                      json_value,
                              base                      NUMBER DEFAULT 1),
   MEMBER PROCEDURE path_put (self        IN OUT NOCOPY json_list,
                              json_path                 VARCHAR2,
                              elem                      VARCHAR2,
                              base                      NUMBER DEFAULT 1),
   MEMBER PROCEDURE path_put (self        IN OUT NOCOPY json_list,
                              json_path                 VARCHAR2,
                              elem                      NUMBER,
                              base                      NUMBER DEFAULT 1),
   MEMBER PROCEDURE path_put (self        IN OUT NOCOPY json_list,
                              json_path                 VARCHAR2,
                              elem                      BOOLEAN,
                              base                      NUMBER DEFAULT 1),
   MEMBER PROCEDURE path_put (self        IN OUT NOCOPY json_list,
                              json_path                 VARCHAR2,
                              elem                      json_list,
                              base                      NUMBER DEFAULT 1),
   /* json path_remove */
   MEMBER PROCEDURE path_remove (self        IN OUT NOCOPY json_list,
                                 json_path                 VARCHAR2,
                                 base                      NUMBER DEFAULT 1),
   MEMBER FUNCTION to_json_value
      RETURN json_value
  /* --backwards compatibility
  ,
  member procedure add_elem(self in out nocopy json_list, elem json_value, position pls_integer default null),
  member procedure add_elem(self in out nocopy json_list, elem varchar2, position pls_integer default null),
  member procedure add_elem(self in out nocopy json_list, elem number, position pls_integer default null),
  member procedure add_elem(self in out nocopy json_list, elem boolean, position pls_integer default null),
  member procedure add_elem(self in out nocopy json_list, elem json_list, position pls_integer default null),

  member procedure set_elem(self in out nocopy json_list, position pls_integer, elem json_value),
  member procedure set_elem(self in out nocopy json_list, position pls_integer, elem varchar2),
  member procedure set_elem(self in out nocopy json_list, position pls_integer, elem number),
  member procedure set_elem(self in out nocopy json_list, position pls_integer, elem boolean),
  member procedure set_elem(self in out nocopy json_list, position pls_integer, elem json_list),

  member procedure remove_elem(self in out nocopy json_list, position pls_integer),
  member function get_elem(position pls_integer) return json_value,
  member function get_first return json_value,
  member function get_last return json_value
--  */

)
   NOT FINAL;
/

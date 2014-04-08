CREATE OR REPLACE TYPE json_value
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

   typeval NUMBER (1), /* 1 = object, 2 = array, 3 = string, 4 = number, 5 = bool, 6 = null */
   str VARCHAR2 (32767),
   num NUMBER,                               /* store 1 as true, 0 as false */
   object_or_array SYS.ANYDATA,                  /* object or array in here */
   extended_str CLOB,
   /* mapping */
   mapname VARCHAR2 (4000),
   mapindx NUMBER (32),
   CONSTRUCTOR FUNCTION json_value (object_or_array SYS.ANYDATA)
      RETURN SELF AS RESULT,
   CONSTRUCTOR FUNCTION json_value (str VARCHAR2, esc BOOLEAN DEFAULT TRUE)
      RETURN SELF AS RESULT,
   CONSTRUCTOR FUNCTION json_value (str CLOB, esc BOOLEAN DEFAULT TRUE)
      RETURN SELF AS RESULT,
   CONSTRUCTOR FUNCTION json_value (num NUMBER)
      RETURN SELF AS RESULT,
   CONSTRUCTOR FUNCTION json_value (b BOOLEAN)
      RETURN SELF AS RESULT,
   CONSTRUCTOR FUNCTION json_value
      RETURN SELF AS RESULT,
   STATIC FUNCTION makenull
      RETURN json_value,
   MEMBER FUNCTION get_type
      RETURN VARCHAR2,
   MEMBER FUNCTION get_string (max_byte_size    NUMBER DEFAULT NULL,
                               max_char_size    NUMBER DEFAULT NULL)
      RETURN VARCHAR2,
   MEMBER PROCEDURE get_string (self IN json_value, buf IN OUT NOCOPY CLOB),
   MEMBER FUNCTION get_number
      RETURN NUMBER,
   MEMBER FUNCTION get_bool
      RETURN BOOLEAN,
   MEMBER FUNCTION get_null
      RETURN VARCHAR2,
   MEMBER FUNCTION is_object
      RETURN BOOLEAN,
   MEMBER FUNCTION is_array
      RETURN BOOLEAN,
   MEMBER FUNCTION is_string
      RETURN BOOLEAN,
   MEMBER FUNCTION is_number
      RETURN BOOLEAN,
   MEMBER FUNCTION is_bool
      RETURN BOOLEAN,
   MEMBER FUNCTION is_null
      RETURN BOOLEAN,
   /* Output methods */
   MEMBER FUNCTION TO_CHAR (spaces            BOOLEAN DEFAULT TRUE,
                            chars_per_line    NUMBER DEFAULT 0)
      RETURN VARCHAR2,
   MEMBER PROCEDURE TO_CLOB (
      self             IN            json_value,
      buf              IN OUT NOCOPY CLOB,
      spaces                         BOOLEAN DEFAULT FALSE,
      chars_per_line                 NUMBER DEFAULT 0,
      erase_clob                     BOOLEAN DEFAULT TRUE),
   MEMBER PROCEDURE PRINT (self             IN json_value,
                           spaces              BOOLEAN DEFAULT TRUE,
                           chars_per_line      NUMBER DEFAULT 8192,
                           jsonp               VARCHAR2 DEFAULT NULL), --32512 is maximum
   MEMBER PROCEDURE HTP (self             IN json_value,
                         spaces              BOOLEAN DEFAULT FALSE,
                         chars_per_line      NUMBER DEFAULT 0,
                         jsonp               VARCHAR2 DEFAULT NULL),
   MEMBER FUNCTION value_of (self            IN json_value,
                             max_byte_size      NUMBER DEFAULT NULL,
                             max_char_size      NUMBER DEFAULT NULL)
      RETURN VARCHAR2
)
   NOT FINAL;
/

CREATE OR REPLACE TYPE json_value_array AS TABLE OF json_value;
/

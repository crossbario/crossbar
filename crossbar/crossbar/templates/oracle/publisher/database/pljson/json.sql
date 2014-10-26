CREATE OR REPLACE TYPE json
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

   /* Variables */
   json_data json_value_array,
   check_for_duplicate NUMBER,
   /* Constructors */
   CONSTRUCTOR FUNCTION json
      RETURN SELF AS RESULT,
   CONSTRUCTOR FUNCTION json (str VARCHAR2)
      RETURN SELF AS RESULT,
   CONSTRUCTOR FUNCTION json (str IN CLOB)
      RETURN SELF AS RESULT,
   CONSTRUCTOR FUNCTION json (CAST json_value)
      RETURN SELF AS RESULT,
   CONSTRUCTOR FUNCTION json (l IN OUT NOCOPY json_list)
      RETURN SELF AS RESULT,
   /* Member setter methods */
   MEMBER PROCEDURE remove (pair_name VARCHAR2),
   MEMBER PROCEDURE put (self         IN OUT NOCOPY json,
                         pair_name                  VARCHAR2,
                         pair_value                 json_value,
                         position                   PLS_INTEGER DEFAULT NULL),
   MEMBER PROCEDURE put (self         IN OUT NOCOPY json,
                         pair_name                  VARCHAR2,
                         pair_value                 VARCHAR2,
                         position                   PLS_INTEGER DEFAULT NULL),
   MEMBER PROCEDURE put (self         IN OUT NOCOPY json,
                         pair_name                  VARCHAR2,
                         pair_value                 NUMBER,
                         position                   PLS_INTEGER DEFAULT NULL),
   MEMBER PROCEDURE put (self         IN OUT NOCOPY json,
                         pair_name                  VARCHAR2,
                         pair_value                 BOOLEAN,
                         position                   PLS_INTEGER DEFAULT NULL),
   MEMBER PROCEDURE check_duplicate (self IN OUT NOCOPY json, v_set BOOLEAN),
   MEMBER PROCEDURE remove_duplicates (self IN OUT NOCOPY json),
   /* deprecated putter use json_value */
   MEMBER PROCEDURE put (self         IN OUT NOCOPY json,
                         pair_name                  VARCHAR2,
                         pair_value                 json,
                         position                   PLS_INTEGER DEFAULT NULL),
   MEMBER PROCEDURE put (self         IN OUT NOCOPY json,
                         pair_name                  VARCHAR2,
                         pair_value                 json_list,
                         position                   PLS_INTEGER DEFAULT NULL),
   /* Member getter methods */
   MEMBER FUNCTION COUNT
      RETURN NUMBER,
   MEMBER FUNCTION get (pair_name VARCHAR2)
      RETURN json_value,
   MEMBER FUNCTION get (position PLS_INTEGER)
      RETURN json_value,
   MEMBER FUNCTION index_of (pair_name VARCHAR2)
      RETURN NUMBER,
   MEMBER FUNCTION exist (pair_name VARCHAR2)
      RETURN BOOLEAN,
   /* Output methods */
   MEMBER FUNCTION TO_CHAR (spaces            BOOLEAN DEFAULT TRUE,
                            chars_per_line    NUMBER DEFAULT 0)
      RETURN VARCHAR2,
   MEMBER PROCEDURE TO_CLOB (
      self             IN            json,
      buf              IN OUT NOCOPY CLOB,
      spaces                         BOOLEAN DEFAULT FALSE,
      chars_per_line                 NUMBER DEFAULT 0,
      erase_clob                     BOOLEAN DEFAULT TRUE),
   MEMBER PROCEDURE PRINT (self             IN json,
                           spaces              BOOLEAN DEFAULT TRUE,
                           chars_per_line      NUMBER DEFAULT 8192,
                           jsonp               VARCHAR2 DEFAULT NULL), --32512 is maximum
   MEMBER PROCEDURE HTP (self             IN json,
                         spaces              BOOLEAN DEFAULT FALSE,
                         chars_per_line      NUMBER DEFAULT 0,
                         jsonp               VARCHAR2 DEFAULT NULL),
   MEMBER FUNCTION to_json_value
      RETURN json_value,
   /* json path */
   MEMBER FUNCTION PATH (json_path VARCHAR2, base NUMBER DEFAULT 1)
      RETURN json_value,
   /* json path_put */
   MEMBER PROCEDURE path_put (self        IN OUT NOCOPY json,
                              json_path                 VARCHAR2,
                              elem                      json_value,
                              base                      NUMBER DEFAULT 1),
   MEMBER PROCEDURE path_put (self        IN OUT NOCOPY json,
                              json_path                 VARCHAR2,
                              elem                      VARCHAR2,
                              base                      NUMBER DEFAULT 1),
   MEMBER PROCEDURE path_put (self        IN OUT NOCOPY json,
                              json_path                 VARCHAR2,
                              elem                      NUMBER,
                              base                      NUMBER DEFAULT 1),
   MEMBER PROCEDURE path_put (self        IN OUT NOCOPY json,
                              json_path                 VARCHAR2,
                              elem                      BOOLEAN,
                              base                      NUMBER DEFAULT 1),
   MEMBER PROCEDURE path_put (self        IN OUT NOCOPY json,
                              json_path                 VARCHAR2,
                              elem                      json_list,
                              base                      NUMBER DEFAULT 1),
   MEMBER PROCEDURE path_put (self        IN OUT NOCOPY json,
                              json_path                 VARCHAR2,
                              elem                      json,
                              base                      NUMBER DEFAULT 1),
   /* json path_remove */
   MEMBER PROCEDURE path_remove (self        IN OUT NOCOPY json,
                                 json_path                 VARCHAR2,
                                 base                      NUMBER DEFAULT 1),
   /* map functions */
   MEMBER FUNCTION get_values
      RETURN json_list,
   MEMBER FUNCTION get_keys
      RETURN json_list
)
   NOT FINAL;
/

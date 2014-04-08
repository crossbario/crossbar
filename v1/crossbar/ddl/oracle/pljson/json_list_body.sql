CREATE OR REPLACE TYPE BODY json_list
AS
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

   CONSTRUCTOR FUNCTION json_list
      RETURN SELF AS RESULT
   AS
   BEGIN
      self.list_data   := json_value_array ();
      RETURN;
   END;

   CONSTRUCTOR FUNCTION json_list (str VARCHAR2)
      RETURN SELF AS RESULT
   AS
   BEGIN
      self   := json_parser.parse_list (str);
      RETURN;
   END;

   CONSTRUCTOR FUNCTION json_list (str CLOB)
      RETURN SELF AS RESULT
   AS
   BEGIN
      self   := json_parser.parse_list (str);
      RETURN;
   END;

   CONSTRUCTOR FUNCTION json_list (CAST json_value)
      RETURN SELF AS RESULT
   AS
      x   NUMBER;
   BEGIN
      x   := CAST.object_or_array.getobject (self);
      RETURN;
   END;


   MEMBER PROCEDURE append (
      self       IN OUT NOCOPY json_list,
      elem                     json_value,
      position                 PLS_INTEGER DEFAULT NULL)
   AS
      indx           PLS_INTEGER;
      insert_value   json_value := NVL (elem, json_value);
   BEGIN
      IF (position IS NULL OR position > self.COUNT) THEN        --end of list
         indx                    := self.COUNT + 1;
         self.list_data.EXTEND (1);
         self.list_data (indx)   := insert_value;
      ELSIF (position < 1) THEN                                    --new first
         indx                 := self.COUNT;
         self.list_data.EXTEND (1);

         FOR x IN REVERSE 1 .. indx
         LOOP
            self.list_data (x + 1)   := self.list_data (x);
         END LOOP;

         self.list_data (1)   := insert_value;
      ELSE
         indx                        := self.COUNT;
         self.list_data.EXTEND (1);

         FOR x IN REVERSE position .. indx
         LOOP
            self.list_data (x + 1)   := self.list_data (x);
         END LOOP;

         self.list_data (position)   := insert_value;
      END IF;
   END;

   MEMBER PROCEDURE append (
      self       IN OUT NOCOPY json_list,
      elem                     VARCHAR2,
      position                 PLS_INTEGER DEFAULT NULL)
   AS
   BEGIN
      append (json_value (elem), position);
   END;

   MEMBER PROCEDURE append (
      self       IN OUT NOCOPY json_list,
      elem                     NUMBER,
      position                 PLS_INTEGER DEFAULT NULL)
   AS
   BEGIN
      IF (elem IS NULL) THEN
         append (json_value (), position);
      ELSE
         append (json_value (elem), position);
      END IF;
   END;

   MEMBER PROCEDURE append (
      self       IN OUT NOCOPY json_list,
      elem                     BOOLEAN,
      position                 PLS_INTEGER DEFAULT NULL)
   AS
   BEGIN
      IF (elem IS NULL) THEN
         append (json_value (), position);
      ELSE
         append (json_value (elem), position);
      END IF;
   END;

   MEMBER PROCEDURE append (
      self       IN OUT NOCOPY json_list,
      elem                     json_list,
      position                 PLS_INTEGER DEFAULT NULL)
   AS
   BEGIN
      IF (elem IS NULL) THEN
         append (json_value (), position);
      ELSE
         append (elem.to_json_value, position);
      END IF;
   END;

   MEMBER PROCEDURE REPLACE (self       IN OUT NOCOPY json_list,
                             position                 PLS_INTEGER,
                             elem                     json_value)
   AS
      insert_value   json_value := NVL (elem, json_value);
      indx           NUMBER;
   BEGIN
      IF (position > self.COUNT) THEN                            --end of list
         indx                    := self.COUNT + 1;
         self.list_data.EXTEND (1);
         self.list_data (indx)   := insert_value;
      ELSIF (position < 1) THEN                  --maybe an error message here
         NULL;
      ELSE
         self.list_data (position)   := insert_value;
      END IF;
   END;

   MEMBER PROCEDURE REPLACE (self       IN OUT NOCOPY json_list,
                             position                 PLS_INTEGER,
                             elem                     VARCHAR2)
   AS
   BEGIN
      REPLACE (position, json_value (elem));
   END;

   MEMBER PROCEDURE REPLACE (self       IN OUT NOCOPY json_list,
                             position                 PLS_INTEGER,
                             elem                     NUMBER)
   AS
   BEGIN
      IF (elem IS NULL) THEN
         REPLACE (position, json_value ());
      ELSE
         REPLACE (position, json_value (elem));
      END IF;
   END;

   MEMBER PROCEDURE REPLACE (self       IN OUT NOCOPY json_list,
                             position                 PLS_INTEGER,
                             elem                     BOOLEAN)
   AS
   BEGIN
      IF (elem IS NULL) THEN
         REPLACE (position, json_value ());
      ELSE
         REPLACE (position, json_value (elem));
      END IF;
   END;

   MEMBER PROCEDURE REPLACE (self       IN OUT NOCOPY json_list,
                             position                 PLS_INTEGER,
                             elem                     json_list)
   AS
   BEGIN
      IF (elem IS NULL) THEN
         REPLACE (position, json_value ());
      ELSE
         REPLACE (position, elem.to_json_value);
      END IF;
   END;

   MEMBER FUNCTION COUNT
      RETURN NUMBER
   AS
   BEGIN
      RETURN self.list_data.COUNT;
   END;

   MEMBER PROCEDURE remove (self       IN OUT NOCOPY json_list,
                            position                 PLS_INTEGER)
   AS
   BEGIN
      IF (position IS NULL OR position < 1 OR position > self.COUNT) THEN
         RETURN;
      END IF;

      FOR x IN (position + 1) .. self.COUNT
      LOOP
         self.list_data (x - 1)   := self.list_data (x);
      END LOOP;

      self.list_data.TRIM (1);
   END;

   MEMBER PROCEDURE remove_first (self IN OUT NOCOPY json_list)
   AS
   BEGIN
      FOR x IN 2 .. self.COUNT
      LOOP
         self.list_data (x - 1)   := self.list_data (x);
      END LOOP;

      IF (self.COUNT > 0) THEN
         self.list_data.TRIM (1);
      END IF;
   END;

   MEMBER PROCEDURE remove_last (self IN OUT NOCOPY json_list)
   AS
   BEGIN
      IF (self.COUNT > 0) THEN
         self.list_data.TRIM (1);
      END IF;
   END;

   MEMBER FUNCTION get (position PLS_INTEGER)
      RETURN json_value
   AS
   BEGIN
      IF (self.COUNT >= position AND position > 0) THEN
         RETURN self.list_data (position);
      END IF;

      RETURN NULL;                     -- do not throw error, just return null
   END;

   MEMBER FUNCTION head
      RETURN json_value
   AS
   BEGIN
      IF (self.COUNT > 0) THEN
         RETURN self.list_data (self.list_data.FIRST);
      END IF;

      RETURN NULL;                     -- do not throw error, just return null
   END;

   MEMBER FUNCTION LAST
      RETURN json_value
   AS
   BEGIN
      IF (self.COUNT > 0) THEN
         RETURN self.list_data (self.list_data.LAST);
      END IF;

      RETURN NULL;                     -- do not throw error, just return null
   END;

   MEMBER FUNCTION tail
      RETURN json_list
   AS
      t   json_list;
   BEGIN
      IF (self.COUNT > 0) THEN
         t   := json_list (self.list_data);
         t.remove (1);
         RETURN t;
      ELSE
         RETURN json_list ();
      END IF;
   END;

   MEMBER FUNCTION TO_CHAR (spaces            BOOLEAN DEFAULT TRUE,
                            chars_per_line    NUMBER DEFAULT 0)
      RETURN VARCHAR2
   AS
   BEGIN
      IF (spaces IS NULL) THEN
         RETURN json_printer.pretty_print_list (
                   self,
                   line_length   => chars_per_line);
      ELSE
         RETURN json_printer.pretty_print_list (
                   self,
                   spaces,
                   line_length   => chars_per_line);
      END IF;
   END;

   MEMBER PROCEDURE TO_CLOB (
      self             IN            json_list,
      buf              IN OUT NOCOPY CLOB,
      spaces                         BOOLEAN DEFAULT FALSE,
      chars_per_line                 NUMBER DEFAULT 0,
      erase_clob                     BOOLEAN DEFAULT TRUE)
   AS
   BEGIN
      IF (spaces IS NULL) THEN
         json_printer.pretty_print_list (self,
                                         FALSE,
                                         buf,
                                         line_length   => chars_per_line,
                                         erase_clob    => erase_clob);
      ELSE
         json_printer.pretty_print_list (self,
                                         spaces,
                                         buf,
                                         line_length   => chars_per_line,
                                         erase_clob    => erase_clob);
      END IF;
   END;

   MEMBER PROCEDURE PRINT (self             IN json_list,
                           spaces              BOOLEAN DEFAULT TRUE,
                           chars_per_line      NUMBER DEFAULT 8192,
                           jsonp               VARCHAR2 DEFAULT NULL)
   AS                              --32512 is the real maximum in sqldeveloper
      my_clob   CLOB;
   BEGIN
      my_clob   := EMPTY_CLOB ();
      DBMS_LOB.createtemporary (my_clob, TRUE);
      json_printer.pretty_print_list (
         self,
         spaces,
         my_clob,
         CASE
            WHEN (chars_per_line > 32512) THEN 32512
            ELSE chars_per_line
         END);
      json_printer.dbms_output_clob (my_clob,
                                     json_printer.newline_char,
                                     jsonp);
      DBMS_LOB.freetemporary (my_clob);
   END;

   MEMBER PROCEDURE HTP (self             IN json_list,
                         spaces              BOOLEAN DEFAULT FALSE,
                         chars_per_line      NUMBER DEFAULT 0,
                         jsonp               VARCHAR2 DEFAULT NULL)
   AS
      my_clob   CLOB;
   BEGIN
      my_clob   := EMPTY_CLOB ();
      DBMS_LOB.createtemporary (my_clob, TRUE);
      json_printer.pretty_print_list (self,
                                      spaces,
                                      my_clob,
                                      chars_per_line);
      json_printer.htp_output_clob (my_clob, jsonp);
      DBMS_LOB.freetemporary (my_clob);
   END;

   /* json path */
   MEMBER FUNCTION PATH (json_path VARCHAR2, base NUMBER DEFAULT 1)
      RETURN json_value
   AS
      cp   json_list := self;
   BEGIN
      RETURN json_ext.get_json_value (json (cp), json_path, base);
   END PATH;


   /* json path_put */
   MEMBER PROCEDURE path_put (self        IN OUT NOCOPY json_list,
                              json_path                 VARCHAR2,
                              elem                      json_value,
                              base                      NUMBER DEFAULT 1)
   AS
      objlist   json;
      jp        json_list := json_ext.parsepath (json_path, base);
   BEGIN
      WHILE (jp.head ().get_number () > self.COUNT)
      LOOP
         self.append (json_value ());
      END LOOP;

      objlist   := json (self);
      json_ext.put (objlist,
                    json_path,
                    elem,
                    base);
      self      := objlist.get_values;
   END path_put;

   MEMBER PROCEDURE path_put (self        IN OUT NOCOPY json_list,
                              json_path                 VARCHAR2,
                              elem                      VARCHAR2,
                              base                      NUMBER DEFAULT 1)
   AS
      objlist   json;
      jp        json_list := json_ext.parsepath (json_path, base);
   BEGIN
      WHILE (jp.head ().get_number () > self.COUNT)
      LOOP
         self.append (json_value ());
      END LOOP;

      objlist   := json (self);
      json_ext.put (objlist,
                    json_path,
                    elem,
                    base);
      self      := objlist.get_values;
   END path_put;

   MEMBER PROCEDURE path_put (self        IN OUT NOCOPY json_list,
                              json_path                 VARCHAR2,
                              elem                      NUMBER,
                              base                      NUMBER DEFAULT 1)
   AS
      objlist   json;
      jp        json_list := json_ext.parsepath (json_path, base);
   BEGIN
      WHILE (jp.head ().get_number () > self.COUNT)
      LOOP
         self.append (json_value ());
      END LOOP;

      objlist   := json (self);

      IF (elem IS NULL) THEN
         json_ext.put (objlist,
                       json_path,
                       json_value,
                       base);
      ELSE
         json_ext.put (objlist,
                       json_path,
                       elem,
                       base);
      END IF;

      self      := objlist.get_values;
   END path_put;

   MEMBER PROCEDURE path_put (self        IN OUT NOCOPY json_list,
                              json_path                 VARCHAR2,
                              elem                      BOOLEAN,
                              base                      NUMBER DEFAULT 1)
   AS
      objlist   json;
      jp        json_list := json_ext.parsepath (json_path, base);
   BEGIN
      WHILE (jp.head ().get_number () > self.COUNT)
      LOOP
         self.append (json_value ());
      END LOOP;

      objlist   := json (self);

      IF (elem IS NULL) THEN
         json_ext.put (objlist,
                       json_path,
                       json_value,
                       base);
      ELSE
         json_ext.put (objlist,
                       json_path,
                       elem,
                       base);
      END IF;

      self      := objlist.get_values;
   END path_put;

   MEMBER PROCEDURE path_put (self        IN OUT NOCOPY json_list,
                              json_path                 VARCHAR2,
                              elem                      json_list,
                              base                      NUMBER DEFAULT 1)
   AS
      objlist   json;
      jp        json_list := json_ext.parsepath (json_path, base);
   BEGIN
      WHILE (jp.head ().get_number () > self.COUNT)
      LOOP
         self.append (json_value ());
      END LOOP;

      objlist   := json (self);

      IF (elem IS NULL) THEN
         json_ext.put (objlist,
                       json_path,
                       json_value,
                       base);
      ELSE
         json_ext.put (objlist,
                       json_path,
                       elem,
                       base);
      END IF;

      self      := objlist.get_values;
   END path_put;

   /* json path_remove */
   MEMBER PROCEDURE path_remove (self        IN OUT NOCOPY json_list,
                                 json_path                 VARCHAR2,
                                 base                      NUMBER DEFAULT 1)
   AS
      objlist   json := json (self);
   BEGIN
      json_ext.remove (objlist, json_path, base);
      self   := objlist.get_values;
   END path_remove;


   MEMBER FUNCTION to_json_value
      RETURN json_value
   AS
   BEGIN
      RETURN json_value (sys.anydata.convertobject (self));
   END;
  /*--backwards compatibility
  member procedure add_elem(self in out nocopy json_list, elem json_value, position pls_integer default null) as begin append(elem,position); end;
  member procedure add_elem(self in out nocopy json_list, elem varchar2, position pls_integer default null) as begin append(elem,position); end;
  member procedure add_elem(self in out nocopy json_list, elem number, position pls_integer default null) as begin append(elem,position); end;
  member procedure add_elem(self in out nocopy json_list, elem boolean, position pls_integer default null) as begin append(elem,position); end;
  member procedure add_elem(self in out nocopy json_list, elem json_list, position pls_integer default null) as begin append(elem,position); end;

  member procedure set_elem(self in out nocopy json_list, position pls_integer, elem json_value) as begin replace(position,elem); end;
  member procedure set_elem(self in out nocopy json_list, position pls_integer, elem varchar2) as begin replace(position,elem); end;
  member procedure set_elem(self in out nocopy json_list, position pls_integer, elem number) as begin replace(position,elem); end;
  member procedure set_elem(self in out nocopy json_list, position pls_integer, elem boolean) as begin replace(position,elem); end;
  member procedure set_elem(self in out nocopy json_list, position pls_integer, elem json_list) as begin replace(position,elem); end;

  member procedure remove_elem(self in out nocopy json_list, position pls_integer) as begin remove(position); end;
  member function get_elem(position pls_integer) return json_value as begin return get(position); end;
  member function get_first return json_value as begin return head(); end;
  member function get_last return json_value as begin return last(); end;
--  */

END;
/

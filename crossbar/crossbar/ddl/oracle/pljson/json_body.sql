CREATE OR REPLACE TYPE BODY json
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

   /* Constructors */
   CONSTRUCTOR FUNCTION json
      RETURN SELF AS RESULT
   AS
   BEGIN
      self.json_data             := json_value_array ();
      self.check_for_duplicate   := 1;
      RETURN;
   END;

   CONSTRUCTOR FUNCTION json (str VARCHAR2)
      RETURN SELF AS RESULT
   AS
   BEGIN
      self                       := json_parser.parser (str);
      self.check_for_duplicate   := 1;
      RETURN;
   END;

   CONSTRUCTOR FUNCTION json (str IN CLOB)
      RETURN SELF AS RESULT
   AS
   BEGIN
      self                       := json_parser.parser (str);
      self.check_for_duplicate   := 1;
      RETURN;
   END;

   CONSTRUCTOR FUNCTION json (CAST json_value)
      RETURN SELF AS RESULT
   AS
      x   NUMBER;
   BEGIN
      x                          := CAST.object_or_array.getobject (self);
      self.check_for_duplicate   := 1;
      RETURN;
   END;

   CONSTRUCTOR FUNCTION json (l IN OUT NOCOPY json_list)
      RETURN SELF AS RESULT
   AS
   BEGIN
      FOR i IN 1 .. l.list_data.COUNT
      LOOP
         IF (   l.list_data (i).mapname IS NULL
             OR l.list_data (i).mapname LIKE 'row%') THEN
            l.list_data (i).mapname   := 'row' || i;
         END IF;

         l.list_data (i).mapindx   := i;
      END LOOP;

      self.json_data             := l.list_data;
      self.check_for_duplicate   := 1;
      RETURN;
   END;

   /* Member setter methods */
   MEMBER PROCEDURE remove (self IN OUT NOCOPY json, pair_name VARCHAR2)
   AS
      temp   json_value;
      indx   PLS_INTEGER;

      FUNCTION get_member (pair_name VARCHAR2)
         RETURN json_value
      AS
         indx   PLS_INTEGER;
      BEGIN
         indx   := json_data.FIRST;

         LOOP
            EXIT WHEN indx IS NULL;

            IF (pair_name IS NULL AND json_data (indx).mapname IS NULL) THEN
               RETURN json_data (indx);
            END IF;

            IF (json_data (indx).mapname = pair_name) THEN
               RETURN json_data (indx);
            END IF;

            indx   := json_data.NEXT (indx);
         END LOOP;

         RETURN NULL;
      END;

   BEGIN
      temp   := get_member (pair_name);

      IF (temp IS NULL) THEN
         RETURN;
      END IF;

      indx   := json_data.NEXT (temp.mapindx);

      LOOP
         EXIT WHEN indx IS NULL;
         json_data (indx).mapindx   := indx - 1;
         json_data (indx - 1)       := json_data (indx);
         indx                       := json_data.NEXT (indx);
      END LOOP;

      json_data.TRIM (1);
   --num_elements := num_elements - 1;
   END;

   MEMBER PROCEDURE put (self         IN OUT NOCOPY json,
                         pair_name                  VARCHAR2,
                         pair_value                 json_value,
                         position                   PLS_INTEGER DEFAULT NULL)
   AS
      insert_value   json_value := NVL (pair_value, json_value.makenull);
      indx           PLS_INTEGER;
      x              NUMBER;
      temp           json_value;

      FUNCTION get_member (pair_name VARCHAR2)
         RETURN json_value
      AS
         indx   PLS_INTEGER;
      BEGIN
         indx   := json_data.FIRST;

         LOOP
            EXIT WHEN indx IS NULL;

            IF (pair_name IS NULL AND json_data (indx).mapname IS NULL) THEN
               RETURN json_data (indx);
            END IF;

            IF (json_data (indx).mapname = pair_name) THEN
               RETURN json_data (indx);
            END IF;

            indx   := json_data.NEXT (indx);
         END LOOP;

         RETURN NULL;
      END;

   BEGIN
      --dbms_output.put_line('PN '||pair_name);

      --    if(pair_name is null) then
      --      raise_application_error(-20102, 'JSON put-method type error: name cannot be null');
      --    end if;
      insert_value.mapname   := pair_name;

      --    self.remove(pair_name);
      IF (self.check_for_duplicate = 1) THEN
         temp   := get_member (pair_name);
      ELSE
         temp   := NULL;
      END IF;

      IF (temp IS NOT NULL) THEN
         insert_value.mapindx       := temp.mapindx;
         json_data (temp.mapindx)   := insert_value;
         RETURN;
      ELSIF (position IS NULL OR position > self.COUNT) THEN
         --insert at the end of the list
         --dbms_output.put_line('Test');
         --      indx := self.count + 1;
         json_data.EXTEND (1);
         json_data (json_data.COUNT)           := insert_value;
         --      insert_value.mapindx := json_data.count;
         json_data (json_data.COUNT).mapindx   := json_data.COUNT;
      --      dbms_output.put_line('Test2'||insert_value.mapindx);
      --      dbms_output.put_line('Test2'||insert_value.mapname);
      --      insert_value.print(false);
      --      self.print;
      ELSIF (position < 2) THEN
         --insert at the start of the list
         indx                   := json_data.LAST;
         json_data.EXTEND;

         LOOP
            EXIT WHEN indx IS NULL;
            temp                       := json_data (indx);
            temp.mapindx               := indx + 1;
            json_data (temp.mapindx)   := temp;
            indx                       := json_data.PRIOR (indx);
         END LOOP;

         json_data (1)          := insert_value;
         insert_value.mapindx   := 1;
      ELSE
         --insert somewhere in the list
         indx                           := json_data.LAST;
         --      dbms_output.put_line('Test '||indx);
         json_data.EXTEND;

         --      dbms_output.put_line('Test '||indx);
         LOOP
            --        dbms_output.put_line('Test '||indx);
            temp                       := json_data (indx);
            temp.mapindx               := indx + 1;
            json_data (temp.mapindx)   := temp;
            EXIT WHEN indx = position;
            indx                       := json_data.PRIOR (indx);
         END LOOP;

         json_data (position)           := insert_value;
         json_data (position).mapindx   := position;
      END IF;
   --    num_elements := num_elements + 1;
   END;

   MEMBER PROCEDURE put (self         IN OUT NOCOPY json,
                         pair_name                  VARCHAR2,
                         pair_value                 VARCHAR2,
                         position                   PLS_INTEGER DEFAULT NULL)
   AS
   BEGIN
      put (pair_name, json_value (pair_value), position);
   END;

   MEMBER PROCEDURE put (self         IN OUT NOCOPY json,
                         pair_name                  VARCHAR2,
                         pair_value                 NUMBER,
                         position                   PLS_INTEGER DEFAULT NULL)
   AS
   BEGIN
      IF (pair_value IS NULL) THEN
         put (pair_name, json_value (), position);
      ELSE
         put (pair_name, json_value (pair_value), position);
      END IF;
   END;

   MEMBER PROCEDURE put (self         IN OUT NOCOPY json,
                         pair_name                  VARCHAR2,
                         pair_value                 BOOLEAN,
                         position                   PLS_INTEGER DEFAULT NULL)
   AS
   BEGIN
      IF (pair_value IS NULL) THEN
         put (pair_name, json_value (), position);
      ELSE
         put (pair_name, json_value (pair_value), position);
      END IF;
   END;

   MEMBER PROCEDURE check_duplicate (self IN OUT NOCOPY json, v_set BOOLEAN)
   AS
   BEGIN
      IF (v_set) THEN
         check_for_duplicate   := 1;
      ELSE
         check_for_duplicate   := 0;
      END IF;
   END;

   /* deprecated putters */

   MEMBER PROCEDURE put (self         IN OUT NOCOPY json,
                         pair_name                  VARCHAR2,
                         pair_value                 json,
                         position                   PLS_INTEGER DEFAULT NULL)
   AS
   BEGIN
      IF (pair_value IS NULL) THEN
         put (pair_name, json_value (), position);
      ELSE
         put (pair_name, pair_value.to_json_value, position);
      END IF;
   END;

   MEMBER PROCEDURE put (self         IN OUT NOCOPY json,
                         pair_name                  VARCHAR2,
                         pair_value                 json_list,
                         position                   PLS_INTEGER DEFAULT NULL)
   AS
   BEGIN
      IF (pair_value IS NULL) THEN
         put (pair_name, json_value (), position);
      ELSE
         put (pair_name, pair_value.to_json_value, position);
      END IF;
   END;

   /* Member getter methods */
   MEMBER FUNCTION COUNT
      RETURN NUMBER
   AS
   BEGIN
      RETURN self.json_data.COUNT;
   END;

   MEMBER FUNCTION get (pair_name VARCHAR2)
      RETURN json_value
   AS
      indx   PLS_INTEGER;
   BEGIN
      indx   := json_data.FIRST;

      LOOP
         EXIT WHEN indx IS NULL;

         IF (pair_name IS NULL AND json_data (indx).mapname IS NULL) THEN
            RETURN json_data (indx);
         END IF;

         IF (json_data (indx).mapname = pair_name) THEN
            RETURN json_data (indx);
         END IF;

         indx   := json_data.NEXT (indx);
      END LOOP;

      RETURN NULL;
   END;

   MEMBER FUNCTION get (position PLS_INTEGER)
      RETURN json_value
   AS
   BEGIN
      IF (self.COUNT >= position AND position > 0) THEN
         RETURN self.json_data (position);
      END IF;

      RETURN NULL;                     -- do not throw error, just return null
   END;

   MEMBER FUNCTION index_of (pair_name VARCHAR2)
      RETURN NUMBER
   AS
      indx   PLS_INTEGER;
   BEGIN
      indx   := json_data.FIRST;

      LOOP
         EXIT WHEN indx IS NULL;

         IF (pair_name IS NULL AND json_data (indx).mapname IS NULL) THEN
            RETURN indx;
         END IF;

         IF (json_data (indx).mapname = pair_name) THEN
            RETURN indx;
         END IF;

         indx   := json_data.NEXT (indx);
      END LOOP;

      RETURN -1;
   END;

   MEMBER FUNCTION exist (pair_name VARCHAR2)
      RETURN BOOLEAN
   AS
   BEGIN
      RETURN (self.get (pair_name) IS NOT NULL);
   END;

   /* Output methods */
   MEMBER FUNCTION TO_CHAR (spaces            BOOLEAN DEFAULT TRUE,
                            chars_per_line    NUMBER DEFAULT 0)
      RETURN VARCHAR2
   AS
   BEGIN
      IF (spaces IS NULL) THEN
         RETURN json_printer.pretty_print (self,
                                           line_length   => chars_per_line);
      ELSE
         RETURN json_printer.pretty_print (self,
                                           spaces,
                                           line_length   => chars_per_line);
      END IF;
   END;

   MEMBER PROCEDURE TO_CLOB (
      self             IN            json,
      buf              IN OUT NOCOPY CLOB,
      spaces                         BOOLEAN DEFAULT FALSE,
      chars_per_line                 NUMBER DEFAULT 0,
      erase_clob                     BOOLEAN DEFAULT TRUE)
   AS
   BEGIN
      IF (spaces IS NULL) THEN
         json_printer.pretty_print (self,
                                    FALSE,
                                    buf,
                                    line_length   => chars_per_line,
                                    erase_clob    => erase_clob);
      ELSE
         json_printer.pretty_print (self,
                                    spaces,
                                    buf,
                                    line_length   => chars_per_line,
                                    erase_clob    => erase_clob);
      END IF;
   END;

   MEMBER PROCEDURE PRINT (self             IN json,
                           spaces              BOOLEAN DEFAULT TRUE,
                           chars_per_line      NUMBER DEFAULT 8192,
                           jsonp               VARCHAR2 DEFAULT NULL)
   AS                              --32512 is the real maximum in sqldeveloper
      my_clob   CLOB;
   BEGIN
      my_clob   := EMPTY_CLOB ();
      DBMS_LOB.createtemporary (my_clob, TRUE);
      json_printer.pretty_print (
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

   MEMBER PROCEDURE HTP (self             IN json,
                         spaces              BOOLEAN DEFAULT FALSE,
                         chars_per_line      NUMBER DEFAULT 0,
                         jsonp               VARCHAR2 DEFAULT NULL)
   AS
      my_clob   CLOB;
   BEGIN
      my_clob   := EMPTY_CLOB ();
      DBMS_LOB.createtemporary (my_clob, TRUE);
      json_printer.pretty_print (self,
                                 spaces,
                                 my_clob,
                                 chars_per_line);
      json_printer.htp_output_clob (my_clob, jsonp);
      DBMS_LOB.freetemporary (my_clob);
   END;

   MEMBER FUNCTION to_json_value
      RETURN json_value
   AS
   BEGIN
      RETURN json_value (sys.anydata.convertobject (self));
   END;

   /* json path */
   MEMBER FUNCTION PATH (json_path VARCHAR2, base NUMBER DEFAULT 1)
      RETURN json_value
   AS
   BEGIN
      RETURN json_ext.get_json_value (self, json_path, base);
   END PATH;

   /* json path_put */
   MEMBER PROCEDURE path_put (self        IN OUT NOCOPY json,
                              json_path                 VARCHAR2,
                              elem                      json_value,
                              base                      NUMBER DEFAULT 1)
   AS
   BEGIN
      json_ext.put (self,
                    json_path,
                    elem,
                    base);
   END path_put;

   MEMBER PROCEDURE path_put (self        IN OUT NOCOPY json,
                              json_path                 VARCHAR2,
                              elem                      VARCHAR2,
                              base                      NUMBER DEFAULT 1)
   AS
   BEGIN
      json_ext.put (self,
                    json_path,
                    elem,
                    base);
   END path_put;

   MEMBER PROCEDURE path_put (self        IN OUT NOCOPY json,
                              json_path                 VARCHAR2,
                              elem                      NUMBER,
                              base                      NUMBER DEFAULT 1)
   AS
   BEGIN
      IF (elem IS NULL) THEN
         json_ext.put (self,
                       json_path,
                       json_value (),
                       base);
      ELSE
         json_ext.put (self,
                       json_path,
                       elem,
                       base);
      END IF;
   END path_put;

   MEMBER PROCEDURE path_put (self        IN OUT NOCOPY json,
                              json_path                 VARCHAR2,
                              elem                      BOOLEAN,
                              base                      NUMBER DEFAULT 1)
   AS
   BEGIN
      IF (elem IS NULL) THEN
         json_ext.put (self,
                       json_path,
                       json_value (),
                       base);
      ELSE
         json_ext.put (self,
                       json_path,
                       elem,
                       base);
      END IF;
   END path_put;

   MEMBER PROCEDURE path_put (self        IN OUT NOCOPY json,
                              json_path                 VARCHAR2,
                              elem                      json_list,
                              base                      NUMBER DEFAULT 1)
   AS
   BEGIN
      IF (elem IS NULL) THEN
         json_ext.put (self,
                       json_path,
                       json_value (),
                       base);
      ELSE
         json_ext.put (self,
                       json_path,
                       elem,
                       base);
      END IF;
   END path_put;

   MEMBER PROCEDURE path_put (self        IN OUT NOCOPY json,
                              json_path                 VARCHAR2,
                              elem                      json,
                              base                      NUMBER DEFAULT 1)
   AS
   BEGIN
      IF (elem IS NULL) THEN
         json_ext.put (self,
                       json_path,
                       json_value (),
                       base);
      ELSE
         json_ext.put (self,
                       json_path,
                       elem,
                       base);
      END IF;
   END path_put;

   MEMBER PROCEDURE path_remove (self        IN OUT NOCOPY json,
                                 json_path                 VARCHAR2,
                                 base                      NUMBER DEFAULT 1)
   AS
   BEGIN
      json_ext.remove (self, json_path, base);
   END path_remove;

   /* Thanks to Matt Nolan */
   MEMBER FUNCTION get_keys
      RETURN json_list
   AS
      keys   json_list;
      indx   PLS_INTEGER;
   BEGIN
      keys   := json_list ();
      indx   := json_data.FIRST;

      LOOP
         EXIT WHEN indx IS NULL;
         keys.append (json_data (indx).mapname);
         indx   := json_data.NEXT (indx);
      END LOOP;

      RETURN keys;
   END;

   MEMBER FUNCTION get_values
      RETURN json_list
   AS
      vals   json_list := json_list ();
   BEGIN
      vals.list_data   := self.json_data;
      RETURN vals;
   END;

   MEMBER PROCEDURE remove_duplicates (self IN OUT NOCOPY json)
   AS
   BEGIN
      json_parser.remove_duplicates (self);
   END remove_duplicates;
END;
/

SHO ERR

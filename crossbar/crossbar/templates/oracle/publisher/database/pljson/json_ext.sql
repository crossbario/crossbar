CREATE OR REPLACE PACKAGE json_ext
AS
   /*
   Copyright (c) 2009 Jonas Krogsboell

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

   /* This package contains extra methods to lookup types and
      an easy way of adding date values in json - without changing the structure */
   FUNCTION parsepath (json_path VARCHAR2, base NUMBER DEFAULT 1)
      RETURN json_list;

   --JSON Path getters
   FUNCTION get_json_value (obj json, v_path VARCHAR2, base NUMBER DEFAULT 1)
      RETURN json_value;

   FUNCTION get_string (obj json, PATH VARCHAR2, base NUMBER DEFAULT 1)
      RETURN VARCHAR2;

   FUNCTION get_number (obj json, PATH VARCHAR2, base NUMBER DEFAULT 1)
      RETURN NUMBER;

   FUNCTION get_json (obj json, PATH VARCHAR2, base NUMBER DEFAULT 1)
      RETURN json;

   FUNCTION get_json_list (obj json, PATH VARCHAR2, base NUMBER DEFAULT 1)
      RETURN json_list;

   FUNCTION get_bool (obj json, PATH VARCHAR2, base NUMBER DEFAULT 1)
      RETURN BOOLEAN;

   --JSON Path putters
   PROCEDURE put (obj    IN OUT NOCOPY json,
                  PATH                 VARCHAR2,
                  elem                 VARCHAR2,
                  base                 NUMBER DEFAULT 1);

   PROCEDURE put (obj    IN OUT NOCOPY json,
                  PATH                 VARCHAR2,
                  elem                 NUMBER,
                  base                 NUMBER DEFAULT 1);

   PROCEDURE put (obj    IN OUT NOCOPY json,
                  PATH                 VARCHAR2,
                  elem                 json,
                  base                 NUMBER DEFAULT 1);

   PROCEDURE put (obj    IN OUT NOCOPY json,
                  PATH                 VARCHAR2,
                  elem                 json_list,
                  base                 NUMBER DEFAULT 1);

   PROCEDURE put (obj    IN OUT NOCOPY json,
                  PATH                 VARCHAR2,
                  elem                 BOOLEAN,
                  base                 NUMBER DEFAULT 1);

   PROCEDURE put (obj    IN OUT NOCOPY json,
                  PATH                 VARCHAR2,
                  elem                 json_value,
                  base                 NUMBER DEFAULT 1);

   PROCEDURE remove (obj    IN OUT NOCOPY json,
                     PATH                 VARCHAR2,
                     base                 NUMBER DEFAULT 1);

   --Pretty print with JSON Path - obsolete in 0.9.4 - obj.path(v_path).(to_char,print,htp)
   FUNCTION pp (obj json, v_path VARCHAR2)
      RETURN VARCHAR2;

   PROCEDURE pp (obj json, v_path VARCHAR2);      --using dbms_output.put_line

   PROCEDURE pp_htp (obj json, v_path VARCHAR2);             --using htp.print

   --extra function checks if number has no fraction
   FUNCTION is_integer (v json_value)
      RETURN BOOLEAN;

   format_string   VARCHAR2 (30 CHAR) := 'yyyy-mm-dd hh24:mi:ss';

   --extension enables json to store dates without comprimising the implementation
   FUNCTION to_json_value (d DATE)
      RETURN json_value;

   --notice that a date type in json is also a varchar2
   FUNCTION is_date (v json_value)
      RETURN BOOLEAN;

   --convertion is needed to extract dates
   --(json_ext.to_date will not work along with the normal to_date function - any fix will be appreciated)
   FUNCTION to_date2 (v json_value)
      RETURN DATE;

   --JSON Path with date
   FUNCTION get_date (obj json, PATH VARCHAR2, base NUMBER DEFAULT 1)
      RETURN DATE;

   PROCEDURE put (obj    IN OUT NOCOPY json,
                  PATH                 VARCHAR2,
                  elem                 DATE,
                  base                 NUMBER DEFAULT 1);

   --experimental support of binary data with base64
   FUNCTION base64 (binarydata BLOB)
      RETURN json_list;

   FUNCTION base64 (l json_list)
      RETURN BLOB;

   FUNCTION encode (binarydata BLOB)
      RETURN json_value;

   FUNCTION DECODE (v json_value)
      RETURN BLOB;
END json_ext;
/

CREATE OR REPLACE PACKAGE BODY json_ext
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

   scanner_exception   EXCEPTION;
   PRAGMA EXCEPTION_INIT (scanner_exception, -20100);
   parser_exception    EXCEPTION;
   PRAGMA EXCEPTION_INIT (parser_exception, -20101);
   jext_exception      EXCEPTION;
   PRAGMA EXCEPTION_INIT (jext_exception, -20110);

   --extra function checks if number has no fraction
   FUNCTION is_integer (v json_value)
      RETURN BOOLEAN
   AS
      myint   NUMBER (38);              --the oracle way to specify an integer
   BEGIN
      IF (v.is_number) THEN
         myint   := v.get_number;
         RETURN (myint = v.get_number);                  --no rounding errors?
      ELSE
         RETURN FALSE;
      END IF;
   END;

   --extension enables json to store dates without comprimising the implementation
   FUNCTION to_json_value (d DATE)
      RETURN json_value
   AS
   BEGIN
      RETURN json_value (TO_CHAR (d, format_string));
   END;

   --notice that a date type in json is also a varchar2
   FUNCTION is_date (v json_value)
      RETURN BOOLEAN
   AS
      temp   DATE;
   BEGIN
      temp   := json_ext.to_date2 (v);
      RETURN TRUE;
   EXCEPTION
      WHEN OTHERS THEN
         RETURN FALSE;
   END;

   --convertion is needed to extract dates
   FUNCTION to_date2 (v json_value)
      RETURN DATE
   AS
   BEGIN
      IF (v.is_string) THEN
         RETURN TO_DATE (v.get_string, format_string);
      ELSE
         raise_application_error (-20110,
                                  'Anydata did not contain a date-value');
      END IF;
   EXCEPTION
      WHEN OTHERS THEN
         raise_application_error (
            -20110,
            'Anydata did not contain a date on the format: ' || format_string);
   END;

   --Json Path parser
   FUNCTION parsepath (json_path VARCHAR2, base NUMBER DEFAULT 1)
      RETURN json_list
   AS
      build_path   VARCHAR2 (32767) := '[';
      buf          VARCHAR2 (4);
      endstring    VARCHAR2 (1);
      indx         NUMBER := 1;
      ret          json_list;

      PROCEDURE next_char
      AS
      BEGIN
         IF (indx <= LENGTH (json_path)) THEN
            buf    := SUBSTR (json_path, indx, 1);
            indx   := indx + 1;
         ELSE
            buf   := NULL;
         END IF;
      END;

      --skip ws
      PROCEDURE skipws
      AS
      BEGIN
         WHILE (buf IN (CHR (9), CHR (10), CHR (13), ' '))
         LOOP
            next_char;
         END LOOP;
      END;

   BEGIN
      next_char ();

      WHILE (buf IS NOT NULL)
      LOOP
         IF (buf = '.') THEN
            next_char ();

            IF (buf IS NULL) THEN
               raise_application_error (
                  -20110,
                  'JSON Path parse error: . is not a valid json_path end');
            END IF;

            IF (NOT REGEXP_LIKE (buf, '^[[:alnum:]\_ ]+', 'c')) THEN
               raise_application_error (
                  -20110,
                     'JSON Path parse error: alpha-numeric character or space expected at position '
                  || indx);
            END IF;

            IF (build_path != '[') THEN
               build_path   := build_path || ',';
            END IF;

            build_path   := build_path || '"';

            WHILE (REGEXP_LIKE (buf, '^[[:alnum:]\_ ]+', 'c'))
            LOOP
               build_path   := build_path || buf;
               next_char ();
            END LOOP;

            build_path   := build_path || '"';
         ELSIF (buf = '[') THEN
            next_char ();
            skipws ();

            IF (buf IS NULL) THEN
               raise_application_error (
                  -20110,
                  'JSON Path parse error: [ is not a valid json_path end');
            END IF;

            IF (   buf IN ('1', '2', '3', '4', '5', '6', '7', '8', '9')
                OR (buf = '0' AND base = 0)) THEN
               IF (build_path != '[') THEN
                  build_path   := build_path || ',';
               END IF;

               WHILE (buf IN
                         ('0', '1', '2', '3', '4', '5', '6', '7', '8', '9'))
               LOOP
                  build_path   := build_path || buf;
                  next_char ();
               END LOOP;
            ELSIF (REGEXP_LIKE (buf, '^(\"|\'')', 'c')) THEN
               endstring    := buf;

               IF (build_path != '[') THEN
                  build_path   := build_path || ',';
               END IF;

               build_path   := build_path || '"';
               next_char ();

               IF (buf IS NULL) THEN
                  raise_application_error (
                     -20110,
                     'JSON Path parse error: premature json_path end');
               END IF;

               WHILE (buf != endstring)
               LOOP
                  build_path   := build_path || buf;
                  next_char ();

                  IF (buf IS NULL) THEN
                     raise_application_error (
                        -20110,
                        'JSON Path parse error: premature json_path end');
                  END IF;

                  IF (buf = '\') THEN
                     next_char ();
                     build_path   := build_path || '\' || buf;
                     next_char ();
                  END IF;
               END LOOP;

               build_path   := build_path || '"';
               next_char ();
            ELSE
               raise_application_error (
                  -20110,
                     'JSON Path parse error: expected a string or an positive integer at '
                  || indx);
            END IF;

            skipws ();

            IF (buf IS NULL) THEN
               raise_application_error (
                  -20110,
                  'JSON Path parse error: premature json_path end');
            END IF;

            IF (buf != ']') THEN
               raise_application_error (
                  -20110,
                     'JSON Path parse error: no array ending found. found: '
                  || buf);
            END IF;

            next_char ();
            skipws ();
         ELSIF (build_path = '[') THEN
            IF (NOT REGEXP_LIKE (buf, '^[[:alnum:]\_ ]+', 'c')) THEN
               raise_application_error (
                  -20110,
                     'JSON Path parse error: alpha-numeric character or space expected at position '
                  || indx);
            END IF;

            build_path   := build_path || '"';

            WHILE (REGEXP_LIKE (buf, '^[[:alnum:]\_ ]+', 'c'))
            LOOP
               build_path   := build_path || buf;
               next_char ();
            END LOOP;

            build_path   := build_path || '"';
         ELSE
            raise_application_error (
               -20110,
                  'JSON Path parse error: expected . or [ found '
               || buf
               || ' at position '
               || indx);
         END IF;
      END LOOP;

      build_path   := build_path || ']';
      build_path      :=
         REPLACE (
            REPLACE (
               REPLACE (
                  REPLACE (REPLACE (build_path, CHR (9), '\t'),
                           CHR (10),
                           '\n'),
                  CHR (13),
                  '\f'),
               CHR (8),
               '\b'),
            CHR (14),
            '\r');

      ret          := json_list (build_path);

      IF (base != 1) THEN
         --fix base 0 to base 1
         DECLARE
            elem   json_value;
         BEGIN
            FOR i IN 1 .. ret.COUNT
            LOOP
               elem   := ret.get (i);

               IF (elem.is_number) THEN
                  ret.REPLACE (i, elem.get_number () + 1);
               END IF;
            END LOOP;
         END;
      END IF;

      RETURN ret;
   END parsepath;

   --JSON Path getters
   FUNCTION get_json_value (obj json, v_path VARCHAR2, base NUMBER DEFAULT 1)
      RETURN json_value
   AS
      PATH   json_list;
      ret    json_value;
      o      json;
      l      json_list;
   BEGIN
      PATH   := parsepath (v_path, base);
      ret    := obj.to_json_value;

      IF (PATH.COUNT = 0) THEN
         RETURN ret;
      END IF;

      FOR i IN 1 .. PATH.COUNT
      LOOP
         IF (PATH.get (i).is_string ()) THEN
            --string fetch only on json
            o     := json (ret);
            ret   := o.get (PATH.get (i).get_string ());
         ELSE
            --number fetch on json and json_list
            IF (ret.is_array ()) THEN
               l     := json_list (ret);
               ret   := l.get (PATH.get (i).get_number ());
            ELSE
               o     := json (ret);
               l     := o.get_values ();
               ret   := l.get (PATH.get (i).get_number ());
            END IF;
         END IF;
      END LOOP;

      RETURN ret;
   EXCEPTION
      WHEN scanner_exception THEN
         RAISE;
      WHEN parser_exception THEN
         RAISE;
      WHEN jext_exception THEN
         RAISE;
      WHEN OTHERS THEN
         RETURN NULL;
   END get_json_value;

   --JSON Path getters
   FUNCTION get_string (obj json, PATH VARCHAR2, base NUMBER DEFAULT 1)
      RETURN VARCHAR2
   AS
      temp   json_value;
   BEGIN
      temp   := get_json_value (obj, PATH, base);

      IF (temp IS NULL OR NOT temp.is_string) THEN
         RETURN NULL;
      ELSE
         RETURN temp.get_string;
      END IF;
   END;

   FUNCTION get_number (obj json, PATH VARCHAR2, base NUMBER DEFAULT 1)
      RETURN NUMBER
   AS
      temp   json_value;
   BEGIN
      temp   := get_json_value (obj, PATH, base);

      IF (temp IS NULL OR NOT temp.is_number) THEN
         RETURN NULL;
      ELSE
         RETURN temp.get_number;
      END IF;
   END;

   FUNCTION get_json (obj json, PATH VARCHAR2, base NUMBER DEFAULT 1)
      RETURN json
   AS
      temp   json_value;
   BEGIN
      temp   := get_json_value (obj, PATH, base);

      IF (temp IS NULL OR NOT temp.is_object) THEN
         RETURN NULL;
      ELSE
         RETURN json (temp);
      END IF;
   END;

   FUNCTION get_json_list (obj json, PATH VARCHAR2, base NUMBER DEFAULT 1)
      RETURN json_list
   AS
      temp   json_value;
   BEGIN
      temp   := get_json_value (obj, PATH, base);

      IF (temp IS NULL OR NOT temp.is_array) THEN
         RETURN NULL;
      ELSE
         RETURN json_list (temp);
      END IF;
   END;

   FUNCTION get_bool (obj json, PATH VARCHAR2, base NUMBER DEFAULT 1)
      RETURN BOOLEAN
   AS
      temp   json_value;
   BEGIN
      temp   := get_json_value (obj, PATH, base);

      IF (temp IS NULL OR NOT temp.is_bool) THEN
         RETURN NULL;
      ELSE
         RETURN temp.get_bool;
      END IF;
   END;

   FUNCTION get_date (obj json, PATH VARCHAR2, base NUMBER DEFAULT 1)
      RETURN DATE
   AS
      temp   json_value;
   BEGIN
      temp   := get_json_value (obj, PATH, base);

      IF (temp IS NULL OR NOT is_date (temp)) THEN
         RETURN NULL;
      ELSE
         RETURN json_ext.to_date2 (temp);
      END IF;
   END;

   /* JSON Path putter internal function */
   PROCEDURE put_internal (obj      IN OUT NOCOPY json,
                           v_path                 VARCHAR2,
                           elem                   json_value,
                           base                   NUMBER)
   AS
      val             json_value := elem;
      PATH            json_list;
      backreference   json_list := json_list ();

      keyval          json_value;
      keynum          NUMBER;
      keystring       VARCHAR2 (4000);
      temp            json_value := obj.to_json_value;
      obj_temp        json;
      list_temp       json_list;
      inserter        json_value;
   BEGIN
      PATH       := json_ext.parsepath (v_path, base);

      IF (PATH.COUNT = 0) THEN
         raise_application_error (
            -20110,
            'JSON_EXT put error: cannot put with empty string.');
      END IF;

      --build backreference
      FOR i IN 1 .. PATH.COUNT
      LOOP
         --backreference.print(false);
         keyval   := PATH.get (i);

         IF (keyval.is_number ()) THEN
            --nummer index
            keynum   := keyval.get_number ();

            IF ( (NOT temp.is_object ()) AND (NOT temp.is_array ())) THEN
               IF (val IS NULL) THEN
                  RETURN;
               END IF;

               backreference.remove_last;
               temp   := json_list ().to_json_value ();
               backreference.append (temp);
            END IF;

            IF (temp.is_object ()) THEN
               obj_temp   := json (temp);

               IF (obj_temp.COUNT < keynum) THEN
                  IF (val IS NULL) THEN
                     RETURN;
                  END IF;

                  raise_application_error (
                     -20110,
                     'JSON_EXT put error: access object with to few members.');
               END IF;

               temp       := obj_temp.get (keynum);
            ELSE
               list_temp   := json_list (temp);

               IF (list_temp.COUNT < keynum) THEN
                  IF (val IS NULL) THEN
                     RETURN;
                  END IF;

                  --raise error or quit if val is null
                  FOR i IN list_temp.COUNT + 1 .. keynum
                  LOOP
                     list_temp.append (json_value.makenull);
                  END LOOP;

                  backreference.remove_last;
                  backreference.append (list_temp);
               END IF;

               temp        := list_temp.get (keynum);
            END IF;
         ELSE
            --streng index
            keystring   := keyval.get_string ();

            IF (NOT temp.is_object ()) THEN
               --backreference.print;
               IF (val IS NULL) THEN
                  RETURN;
               END IF;

               backreference.remove_last;
               temp   := json ().to_json_value ();
               backreference.append (temp);
            --raise_application_error(-20110, 'JSON_ext put error: trying to access a non object with a string.');
            END IF;

            obj_temp    := json (temp);
            temp        := obj_temp.get (keystring);
         END IF;

         IF (temp IS NULL) THEN
            IF (val IS NULL) THEN
               RETURN;
            END IF;

            --what to expect?
            keyval   := PATH.get (i + 1);

            IF (keyval IS NOT NULL AND keyval.is_number ()) THEN
               temp   := json_list ().to_json_value;
            ELSE
               temp   := json ().to_json_value;
            END IF;
         END IF;

         backreference.append (temp);
      END LOOP;

      --  backreference.print(false);
      --  path.print(false);

      --use backreference and path together
      inserter   := val;

      FOR i IN REVERSE 1 .. backreference.COUNT
      LOOP
         --    inserter.print(false);
         IF (i = 1) THEN
            keyval   := PATH.get (1);

            IF (keyval.is_string ()) THEN
               keystring   := keyval.get_string ();
            ELSE
               keynum   := keyval.get_number ();

               DECLARE
                  t1   json_value := obj.get (keynum);
               BEGIN
                  keystring   := t1.mapname;
               END;
            END IF;

            IF (inserter IS NULL) THEN
               obj.remove (keystring);
            ELSE
               obj.put (keystring, inserter);
            END IF;
         ELSE
            temp   := backreference.get (i - 1);

            IF (temp.is_object ()) THEN
               keyval     := PATH.get (i);
               obj_temp   := json (temp);

               IF (keyval.is_string ()) THEN
                  keystring   := keyval.get_string ();
               ELSE
                  keynum   := keyval.get_number ();

                  DECLARE
                     t1   json_value := obj_temp.get (keynum);
                  BEGIN
                     keystring   := t1.mapname;
                  END;
               END IF;

               IF (inserter IS NULL) THEN
                  obj_temp.remove (keystring);

                  IF (obj_temp.COUNT > 0) THEN
                     inserter   := obj_temp.to_json_value;
                  END IF;
               ELSE
                  obj_temp.put (keystring, inserter);
                  inserter   := obj_temp.to_json_value;
               END IF;
            ELSE
               --array only number
               keynum      := PATH.get (i).get_number ();
               list_temp   := json_list (temp);
               list_temp.remove (keynum);

               IF (NOT inserter IS NULL) THEN
                  list_temp.append (inserter, keynum);
                  inserter   := list_temp.to_json_value;
               ELSE
                  IF (list_temp.COUNT > 0) THEN
                     inserter   := list_temp.to_json_value;
                  END IF;
               END IF;
            END IF;
         END IF;
      END LOOP;
   END put_internal;

   /* JSON Path putters */
   PROCEDURE put (obj    IN OUT NOCOPY json,
                  PATH                 VARCHAR2,
                  elem                 VARCHAR2,
                  base                 NUMBER DEFAULT 1)
   AS
   BEGIN
      put_internal (obj,
                    PATH,
                    json_value (elem),
                    base);
   END;

   PROCEDURE put (obj    IN OUT NOCOPY json,
                  PATH                 VARCHAR2,
                  elem                 NUMBER,
                  base                 NUMBER DEFAULT 1)
   AS
   BEGIN
      IF (elem IS NULL) THEN
         raise_application_error (-20110, 'Cannot put null-value');
      END IF;

      put_internal (obj,
                    PATH,
                    json_value (elem),
                    base);
   END;

   PROCEDURE put (obj    IN OUT NOCOPY json,
                  PATH                 VARCHAR2,
                  elem                 json,
                  base                 NUMBER DEFAULT 1)
   AS
   BEGIN
      IF (elem IS NULL) THEN
         raise_application_error (-20110, 'Cannot put null-value');
      END IF;

      put_internal (obj,
                    PATH,
                    elem.to_json_value,
                    base);
   END;

   PROCEDURE put (obj    IN OUT NOCOPY json,
                  PATH                 VARCHAR2,
                  elem                 json_list,
                  base                 NUMBER DEFAULT 1)
   AS
   BEGIN
      IF (elem IS NULL) THEN
         raise_application_error (-20110, 'Cannot put null-value');
      END IF;

      put_internal (obj,
                    PATH,
                    elem.to_json_value,
                    base);
   END;

   PROCEDURE put (obj    IN OUT NOCOPY json,
                  PATH                 VARCHAR2,
                  elem                 BOOLEAN,
                  base                 NUMBER DEFAULT 1)
   AS
   BEGIN
      IF (elem IS NULL) THEN
         raise_application_error (-20110, 'Cannot put null-value');
      END IF;

      put_internal (obj,
                    PATH,
                    json_value (elem),
                    base);
   END;

   PROCEDURE put (obj    IN OUT NOCOPY json,
                  PATH                 VARCHAR2,
                  elem                 json_value,
                  base                 NUMBER DEFAULT 1)
   AS
   BEGIN
      IF (elem IS NULL) THEN
         raise_application_error (-20110, 'Cannot put null-value');
      END IF;

      put_internal (obj,
                    PATH,
                    elem,
                    base);
   END;

   PROCEDURE put (obj    IN OUT NOCOPY json,
                  PATH                 VARCHAR2,
                  elem                 DATE,
                  base                 NUMBER DEFAULT 1)
   AS
   BEGIN
      IF (elem IS NULL) THEN
         raise_application_error (-20110, 'Cannot put null-value');
      END IF;

      put_internal (obj,
                    PATH,
                    json_ext.to_json_value (elem),
                    base);
   END;

   PROCEDURE remove (obj    IN OUT NOCOPY json,
                     PATH                 VARCHAR2,
                     base                 NUMBER DEFAULT 1)
   AS
   BEGIN
      json_ext.put_internal (obj,
                             PATH,
                             NULL,
                             base);
   --    if(json_ext.get_json_value(obj,path) is not null) then
   --    end if;
   END remove;

   --Pretty print with JSON Path
   FUNCTION pp (obj json, v_path VARCHAR2)
      RETURN VARCHAR2
   AS
      json_part   json_value;
   BEGIN
      json_part   := json_ext.get_json_value (obj, v_path);

      IF (json_part IS NULL) THEN
         RETURN '';
      ELSE
         RETURN json_printer.pretty_print_any (json_part); --escapes a possible internal string
      END IF;
   END pp;

   PROCEDURE pp (obj json, v_path VARCHAR2)
   AS                                             --using dbms_output.put_line
   BEGIN
      DBMS_OUTPUT.put_line (pp (obj, v_path));
   END pp;

   -- spaces = false!
   PROCEDURE pp_htp (obj json, v_path VARCHAR2)
   AS                                                        --using htp.print
      json_part   json_value;
   BEGIN
      json_part   := json_ext.get_json_value (obj, v_path);

      IF (json_part IS NULL) THEN
         HTP.PRINT;
      ELSE
         HTP.PRINT (json_printer.pretty_print_any (json_part, FALSE));
      END IF;
   END pp_htp;

   FUNCTION base64 (binarydata BLOB)
      RETURN json_list
   AS
      obj              json_list := json_list ();
      c                CLOB := EMPTY_CLOB ();
      benc             BLOB;

      v_blob_offset    NUMBER := 1;
      v_clob_offset    NUMBER := 1;
      v_lang_context   NUMBER := DBMS_LOB.default_lang_ctx;
      v_warning        NUMBER;
      v_amount         PLS_INTEGER;

      --    temp varchar2(32767);

      FUNCTION encodeblob2base64 (pblobin IN BLOB)
         RETURN BLOB
      IS
         vamount       NUMBER := 45;
         vblobenc      BLOB := EMPTY_BLOB ();
         vblobenclen   NUMBER := 0;
         vblobinlen    NUMBER := 0;
         vbuffer       RAW (45);
         voffset       NUMBER := 1;
      BEGIN
         --      dbms_output.put_line('Start base64 encoding.');
         vblobinlen    := DBMS_LOB.getlength (pblobin);
         --      dbms_output.put_line('<BlobInLength>' || vBlobInLen);
         DBMS_LOB.createtemporary (vblobenc, TRUE);

         LOOP
            IF voffset >= vblobinlen THEN
               EXIT;
            END IF;

            DBMS_LOB.read (pblobin,
                           vamount,
                           voffset,
                           vbuffer);

            BEGIN
               DBMS_LOB.append (vblobenc, UTL_ENCODE.base64_encode (vbuffer));
            EXCEPTION
               WHEN OTHERS THEN
                  DBMS_OUTPUT.put_line (
                        '<vAmount>'
                     || vamount
                     || '<vOffset>'
                     || voffset
                     || '<vBuffer>'
                     || vbuffer);
                  DBMS_OUTPUT.put_line ('ERROR IN append: ' || SQLERRM);
                  RAISE;
            END;

            voffset   := voffset + vamount;
         END LOOP;

         vblobenclen   := DBMS_LOB.getlength (vblobenc);
         --      dbms_output.put_line('<BlobEncLength>' || vBlobEncLen);
         --      dbms_output.put_line('Finshed base64 encoding.');
         RETURN vblobenc;
      END encodeblob2base64;

   BEGIN
      benc            := encodeblob2base64 (binarydata);
      DBMS_LOB.createtemporary (c, TRUE);
      v_amount        := DBMS_LOB.getlength (benc);
      DBMS_LOB.converttoclob (c,
                              benc,
                              v_amount,
                              v_clob_offset,
                              v_blob_offset,
                              1,
                              v_lang_context,
                              v_warning);

      v_amount        := DBMS_LOB.getlength (c);
      v_clob_offset   := 1;

      --dbms_output.put_line('V amount: '||v_amount);
      WHILE (v_clob_offset < v_amount)
      LOOP
         --dbms_output.put_line(v_offset);
         --temp := ;
         --dbms_output.put_line('size: '||length(temp));
         obj.append (DBMS_LOB.SUBSTR (c, 4000, v_clob_offset));
         v_clob_offset   := v_clob_offset + 4000;
      END LOOP;

      DBMS_LOB.freetemporary (benc);
      DBMS_LOB.freetemporary (c);
      --dbms_output.put_line(obj.count);
      --dbms_output.put_line(obj.get_last().to_char);
      RETURN obj;
   END base64;


   FUNCTION base64 (l json_list)
      RETURN BLOB
   AS
      c                CLOB := EMPTY_CLOB ();
      b                BLOB := EMPTY_BLOB ();
      bret             BLOB;

      v_blob_offset    NUMBER := 1;
      v_clob_offset    NUMBER := 1;
      v_lang_context   NUMBER := 0;               --DBMS_LOB.DEFAULT_LANG_CTX;
      v_warning        NUMBER;
      v_amount         PLS_INTEGER;

      FUNCTION decodebase642blob (pblobin IN BLOB)
         RETURN BLOB
      IS
         vamount       NUMBER := 256;                                    --32;
         vblobdec      BLOB := EMPTY_BLOB ();
         vblobdeclen   NUMBER := 0;
         vblobinlen    NUMBER := 0;
         vbuffer       RAW (256);                                       --32);
         voffset       NUMBER := 1;
      BEGIN
         --      dbms_output.put_line('Start base64 decoding.');
         vblobinlen    := DBMS_LOB.getlength (pblobin);
         --      dbms_output.put_line('<BlobInLength>' || vBlobInLen);
         DBMS_LOB.createtemporary (vblobdec, TRUE);

         LOOP
            IF voffset >= vblobinlen THEN
               EXIT;
            END IF;

            DBMS_LOB.read (pblobin,
                           vamount,
                           voffset,
                           vbuffer);

            BEGIN
               DBMS_LOB.append (vblobdec, UTL_ENCODE.base64_decode (vbuffer));
            EXCEPTION
               WHEN OTHERS THEN
                  DBMS_OUTPUT.put_line (
                        '<vAmount>'
                     || vamount
                     || '<vOffset>'
                     || voffset
                     || '<vBuffer>'
                     || vbuffer);
                  DBMS_OUTPUT.put_line ('ERROR IN append: ' || SQLERRM);
                  RAISE;
            END;

            voffset   := voffset + vamount;
         END LOOP;

         vblobdeclen   := DBMS_LOB.getlength (vblobdec);
         --      dbms_output.put_line('<BlobDecLength>' || vBlobDecLen);
         --      dbms_output.put_line('Finshed base64 decoding.');
         RETURN vblobdec;
      END decodebase642blob;

   BEGIN
      DBMS_LOB.createtemporary (c, TRUE);

      FOR i IN 1 .. l.COUNT
      LOOP
         DBMS_LOB.append (c, l.get (i).get_string ());
      END LOOP;

      v_amount   := DBMS_LOB.getlength (c);
      --    dbms_output.put_line('L C'||v_amount);

      DBMS_LOB.createtemporary (b, TRUE);
      DBMS_LOB.converttoblob (b,
                              c,
                              DBMS_LOB.lobmaxsize,
                              v_clob_offset,
                              v_blob_offset,
                              1,
                              v_lang_context,
                              v_warning);
      DBMS_LOB.freetemporary (c);
      v_amount   := DBMS_LOB.getlength (b);
      --    dbms_output.put_line('L B'||v_amount);

      bret       := decodebase642blob (b);
      DBMS_LOB.freetemporary (b);
      RETURN bret;
   END base64;

   FUNCTION encode (binarydata BLOB)
      RETURN json_value
   AS
      obj              json_value;
      c                CLOB := EMPTY_CLOB ();
      benc             BLOB;

      v_blob_offset    NUMBER := 1;
      v_clob_offset    NUMBER := 1;
      v_lang_context   NUMBER := DBMS_LOB.default_lang_ctx;
      v_warning        NUMBER;
      v_amount         PLS_INTEGER;

      --    temp varchar2(32767);

      FUNCTION encodeblob2base64 (pblobin IN BLOB)
         RETURN BLOB
      IS
         vamount       NUMBER := 45;
         vblobenc      BLOB := EMPTY_BLOB ();
         vblobenclen   NUMBER := 0;
         vblobinlen    NUMBER := 0;
         vbuffer       RAW (45);
         voffset       NUMBER := 1;
      BEGIN
         --      dbms_output.put_line('Start base64 encoding.');
         vblobinlen    := DBMS_LOB.getlength (pblobin);
         --      dbms_output.put_line('<BlobInLength>' || vBlobInLen);
         DBMS_LOB.createtemporary (vblobenc, TRUE);

         LOOP
            IF voffset >= vblobinlen THEN
               EXIT;
            END IF;

            DBMS_LOB.read (pblobin,
                           vamount,
                           voffset,
                           vbuffer);

            BEGIN
               DBMS_LOB.append (vblobenc, UTL_ENCODE.base64_encode (vbuffer));
            EXCEPTION
               WHEN OTHERS THEN
                  DBMS_OUTPUT.put_line (
                        '<vAmount>'
                     || vamount
                     || '<vOffset>'
                     || voffset
                     || '<vBuffer>'
                     || vbuffer);
                  DBMS_OUTPUT.put_line ('ERROR IN append: ' || SQLERRM);
                  RAISE;
            END;

            voffset   := voffset + vamount;
         END LOOP;

         vblobenclen   := DBMS_LOB.getlength (vblobenc);
         --      dbms_output.put_line('<BlobEncLength>' || vBlobEncLen);
         --      dbms_output.put_line('Finshed base64 encoding.');
         RETURN vblobenc;
      END encodeblob2base64;

   BEGIN
      benc       := encodeblob2base64 (binarydata);
      DBMS_LOB.createtemporary (c, TRUE);
      v_amount   := DBMS_LOB.getlength (benc);
      DBMS_LOB.converttoclob (c,
                              benc,
                              v_amount,
                              v_clob_offset,
                              v_blob_offset,
                              1,
                              v_lang_context,
                              v_warning);

      obj        := json_value (c);

      DBMS_LOB.freetemporary (benc);
      DBMS_LOB.freetemporary (c);
      --dbms_output.put_line(obj.count);
      --dbms_output.put_line(obj.get_last().to_char);
      RETURN obj;
   END encode;

   FUNCTION DECODE (v json_value)
      RETURN BLOB
   AS
      c                CLOB := EMPTY_CLOB ();
      b                BLOB := EMPTY_BLOB ();
      bret             BLOB;

      v_blob_offset    NUMBER := 1;
      v_clob_offset    NUMBER := 1;
      v_lang_context   NUMBER := 0;               --DBMS_LOB.DEFAULT_LANG_CTX;
      v_warning        NUMBER;
      v_amount         PLS_INTEGER;

      FUNCTION decodebase642blob (pblobin IN BLOB)
         RETURN BLOB
      IS
         vamount       NUMBER := 256;                                    --32;
         vblobdec      BLOB := EMPTY_BLOB ();
         vblobdeclen   NUMBER := 0;
         vblobinlen    NUMBER := 0;
         vbuffer       RAW (256);                                       --32);
         voffset       NUMBER := 1;
      BEGIN
         --      dbms_output.put_line('Start base64 decoding.');
         vblobinlen    := DBMS_LOB.getlength (pblobin);
         --      dbms_output.put_line('<BlobInLength>' || vBlobInLen);
         DBMS_LOB.createtemporary (vblobdec, TRUE);

         LOOP
            IF voffset >= vblobinlen THEN
               EXIT;
            END IF;

            DBMS_LOB.read (pblobin,
                           vamount,
                           voffset,
                           vbuffer);

            BEGIN
               DBMS_LOB.append (vblobdec, UTL_ENCODE.base64_decode (vbuffer));
            EXCEPTION
               WHEN OTHERS THEN
                  DBMS_OUTPUT.put_line (
                        '<vAmount>'
                     || vamount
                     || '<vOffset>'
                     || voffset
                     || '<vBuffer>'
                     || vbuffer);
                  DBMS_OUTPUT.put_line ('ERROR IN append: ' || SQLERRM);
                  RAISE;
            END;

            voffset   := voffset + vamount;
         END LOOP;

         vblobdeclen   := DBMS_LOB.getlength (vblobdec);
         --      dbms_output.put_line('<BlobDecLength>' || vBlobDecLen);
         --      dbms_output.put_line('Finshed base64 decoding.');
         RETURN vblobdec;
      END decodebase642blob;

   BEGIN
      DBMS_LOB.createtemporary (c, TRUE);
      v.get_string (c);
      v_amount   := DBMS_LOB.getlength (c);
      --    dbms_output.put_line('L C'||v_amount);

      DBMS_LOB.createtemporary (b, TRUE);
      DBMS_LOB.converttoblob (b,
                              c,
                              DBMS_LOB.lobmaxsize,
                              v_clob_offset,
                              v_blob_offset,
                              1,
                              v_lang_context,
                              v_warning);
      DBMS_LOB.freetemporary (c);
      v_amount   := DBMS_LOB.getlength (b);
      --    dbms_output.put_line('L B'||v_amount);

      bret       := decodebase642blob (b);
      DBMS_LOB.freetemporary (b);
      RETURN bret;
   END DECODE;
END json_ext;
/

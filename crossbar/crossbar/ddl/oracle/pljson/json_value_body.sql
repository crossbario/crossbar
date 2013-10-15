CREATE OR REPLACE TYPE BODY json_value
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

   CONSTRUCTOR FUNCTION json_value (object_or_array SYS.ANYDATA)
      RETURN SELF AS RESULT
   AS
   BEGIN
      CASE object_or_array.gettypename
         WHEN SYS_CONTEXT ('userenv', 'current_schema') || '.JSON_LIST' THEN
            self.typeval   := 2;
         WHEN SYS_CONTEXT ('userenv', 'current_schema') || '.JSON' THEN
            self.typeval   := 1;
         ELSE
            raise_application_error (
               -20102,
               'JSON_Value init error (JSON or JSON\_List allowed)');
      END CASE;

      self.object_or_array   := object_or_array;

      IF (self.object_or_array IS NULL) THEN
         self.typeval   := 6;
      END IF;

      RETURN;
   END json_value;

   CONSTRUCTOR FUNCTION json_value (str VARCHAR2, esc BOOLEAN DEFAULT TRUE)
      RETURN SELF AS RESULT
   AS
   BEGIN
      self.typeval   := 3;

      IF (esc) THEN
         self.num   := 1;
      ELSE
         self.num   := 0;
      END IF;                                      --message to pretty printer

      self.str       := str;
      RETURN;
   END json_value;

   CONSTRUCTOR FUNCTION json_value (str CLOB, esc BOOLEAN DEFAULT TRUE)
      RETURN SELF AS RESULT
   AS
      amount   NUMBER := 32767;
   BEGIN
      self.typeval   := 3;

      IF (esc) THEN
         self.num   := 1;
      ELSE
         self.num   := 0;
      END IF;                                      --message to pretty printer

      IF (DBMS_LOB.getlength (str) > 32767) THEN
         extended_str   := str;
      END IF;

      DBMS_LOB.read (str,
                     amount,
                     1,
                     self.str);
      RETURN;
   END json_value;

   CONSTRUCTOR FUNCTION json_value (num NUMBER)
      RETURN SELF AS RESULT
   AS
   BEGIN
      self.typeval   := 4;
      self.num       := num;

      IF (self.num IS NULL) THEN
         self.typeval   := 6;
      END IF;

      RETURN;
   END json_value;

   CONSTRUCTOR FUNCTION json_value (b BOOLEAN)
      RETURN SELF AS RESULT
   AS
   BEGIN
      self.typeval   := 5;
      self.num       := 0;

      IF (b) THEN
         self.num   := 1;
      END IF;

      IF (b IS NULL) THEN
         self.typeval   := 6;
      END IF;

      RETURN;
   END json_value;

   CONSTRUCTOR FUNCTION json_value
      RETURN SELF AS RESULT
   AS
   BEGIN
      self.typeval   := 6;                                 /* for JSON null */
      RETURN;
   END json_value;

   STATIC FUNCTION makenull
      RETURN json_value
   AS
   BEGIN
      RETURN json_value;
   END makenull;

   MEMBER FUNCTION get_type
      RETURN VARCHAR2
   AS
   BEGIN
      CASE self.typeval
         WHEN 1 THEN
            RETURN 'object';
         WHEN 2 THEN
            RETURN 'array';
         WHEN 3 THEN
            RETURN 'string';
         WHEN 4 THEN
            RETURN 'number';
         WHEN 5 THEN
            RETURN 'bool';
         WHEN 6 THEN
            RETURN 'null';
      END CASE;

      RETURN 'unknown type';
   END get_type;

   MEMBER FUNCTION get_string (max_byte_size    NUMBER DEFAULT NULL,
                               max_char_size    NUMBER DEFAULT NULL)
      RETURN VARCHAR2
   AS
   BEGIN
      IF (self.typeval = 3) THEN
         IF (max_byte_size IS NOT NULL) THEN
            RETURN SUBSTRB (self.str, 1, max_byte_size);
         ELSIF (max_char_size IS NOT NULL) THEN
            RETURN SUBSTR (self.str, 1, max_char_size);
         ELSE
            RETURN self.str;
         END IF;
      END IF;

      RETURN NULL;
   END get_string;

   MEMBER PROCEDURE get_string (self IN json_value, buf IN OUT NOCOPY CLOB)
   AS
   BEGIN
      IF (self.typeval = 3) THEN
         IF (extended_str IS NOT NULL) THEN
            DBMS_LOB.COPY (buf,
                           extended_str,
                           DBMS_LOB.getlength (extended_str));
         ELSE
            DBMS_LOB.writeappend (buf, LENGTH (self.str), self.str);
         END IF;
      END IF;
   END get_string;


   MEMBER FUNCTION get_number
      RETURN NUMBER
   AS
   BEGIN
      IF (self.typeval = 4) THEN
         RETURN self.num;
      END IF;

      RETURN NULL;
   END get_number;

   MEMBER FUNCTION get_bool
      RETURN BOOLEAN
   AS
   BEGIN
      IF (self.typeval = 5) THEN
         RETURN self.num = 1;
      END IF;

      RETURN NULL;
   END get_bool;

   MEMBER FUNCTION get_null
      RETURN VARCHAR2
   AS
   BEGIN
      IF (self.typeval = 6) THEN
         RETURN 'null';
      END IF;

      RETURN NULL;
   END get_null;

   MEMBER FUNCTION is_object
      RETURN BOOLEAN
   AS
   BEGIN
      RETURN self.typeval = 1;
   END;

   MEMBER FUNCTION is_array
      RETURN BOOLEAN
   AS
   BEGIN
      RETURN self.typeval = 2;
   END;

   MEMBER FUNCTION is_string
      RETURN BOOLEAN
   AS
   BEGIN
      RETURN self.typeval = 3;
   END;

   MEMBER FUNCTION is_number
      RETURN BOOLEAN
   AS
   BEGIN
      RETURN self.typeval = 4;
   END;

   MEMBER FUNCTION is_bool
      RETURN BOOLEAN
   AS
   BEGIN
      RETURN self.typeval = 5;
   END;

   MEMBER FUNCTION is_null
      RETURN BOOLEAN
   AS
   BEGIN
      RETURN self.typeval = 6;
   END;

   /* Output methods */
   MEMBER FUNCTION TO_CHAR (spaces            BOOLEAN DEFAULT TRUE,
                            chars_per_line    NUMBER DEFAULT 0)
      RETURN VARCHAR2
   AS
   BEGIN
      IF (spaces IS NULL) THEN
         RETURN json_printer.pretty_print_any (
                   self,
                   line_length   => chars_per_line);
      ELSE
         RETURN json_printer.pretty_print_any (
                   self,
                   spaces,
                   line_length   => chars_per_line);
      END IF;
   END;

   MEMBER PROCEDURE TO_CLOB (
      self             IN            json_value,
      buf              IN OUT NOCOPY CLOB,
      spaces                         BOOLEAN DEFAULT FALSE,
      chars_per_line                 NUMBER DEFAULT 0,
      erase_clob                     BOOLEAN DEFAULT TRUE)
   AS
   BEGIN
      IF (spaces IS NULL) THEN
         json_printer.pretty_print_any (self,
                                        FALSE,
                                        buf,
                                        line_length   => chars_per_line,
                                        erase_clob    => erase_clob);
      ELSE
         json_printer.pretty_print_any (self,
                                        spaces,
                                        buf,
                                        line_length   => chars_per_line,
                                        erase_clob    => erase_clob);
      END IF;
   END;

   MEMBER PROCEDURE PRINT (self             IN json_value,
                           spaces              BOOLEAN DEFAULT TRUE,
                           chars_per_line      NUMBER DEFAULT 8192,
                           jsonp               VARCHAR2 DEFAULT NULL)
   AS                              --32512 is the real maximum in sqldeveloper
      my_clob   CLOB;
   BEGIN
      my_clob   := EMPTY_CLOB ();
      DBMS_LOB.createtemporary (my_clob, TRUE);
      json_printer.pretty_print_any (
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

   MEMBER PROCEDURE HTP (self             IN json_value,
                         spaces              BOOLEAN DEFAULT FALSE,
                         chars_per_line      NUMBER DEFAULT 0,
                         jsonp               VARCHAR2 DEFAULT NULL)
   AS
      my_clob   CLOB;
   BEGIN
      my_clob   := EMPTY_CLOB ();
      DBMS_LOB.createtemporary (my_clob, TRUE);
      json_printer.pretty_print_any (self,
                                     spaces,
                                     my_clob,
                                     chars_per_line);
      json_printer.htp_output_clob (my_clob, jsonp);
      DBMS_LOB.freetemporary (my_clob);
   END;

   MEMBER FUNCTION value_of (self            IN json_value,
                             max_byte_size      NUMBER DEFAULT NULL,
                             max_char_size      NUMBER DEFAULT NULL)
      RETURN VARCHAR2
   AS
   BEGIN
      CASE self.typeval
         WHEN 1 THEN
            RETURN 'json object';
         WHEN 2 THEN
            RETURN 'json array';
         WHEN 3 THEN
            RETURN self.get_string (max_byte_size, max_char_size);
         WHEN 4 THEN
            RETURN self.get_number ();
         WHEN 5 THEN
            IF (self.get_bool ()) THEN
               RETURN 'true';
            ELSE
               RETURN 'false';
            END IF;
         ELSE
            RETURN NULL;
      END CASE;
   END;
END;
/

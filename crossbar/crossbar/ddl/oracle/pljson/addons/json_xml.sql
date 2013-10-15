CREATE OR REPLACE PACKAGE json_xml
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

   /*
   declare
     obj json := json('{a:1,b:[2,3,4],c:true}');
     x xmltype;
   begin
     obj.print;
     x := json_xml.json_to_xml(obj);
     dbms_output.put_line(x.getclobval());
   end;
   */

   FUNCTION json_to_xml (obj json, tagname VARCHAR2 DEFAULT 'root')
      RETURN XMLTYPE;
END json_xml;
/

CREATE OR REPLACE PACKAGE BODY json_xml
AS
   FUNCTION escapestr (str VARCHAR2)
      RETURN VARCHAR2
   AS
      buf   VARCHAR2 (32767) := '';
      ch    VARCHAR2 (4);
   BEGIN
      FOR i IN 1 .. LENGTH (str)
      LOOP
         ch   := SUBSTR (str, i, 1);

         CASE ch
            WHEN '&' THEN
               buf   := buf || '&amp;';
            WHEN '<' THEN
               buf   := buf || '&lt;';
            WHEN '>' THEN
               buf   := buf || '&gt;';
            WHEN '"' THEN
               buf   := buf || '&quot;';
            ELSE
               buf   := buf || ch;
         END CASE;
      END LOOP;

      RETURN buf;
   END escapestr;

   /* Clob methods from printer */
   PROCEDURE add_to_clob (buf_lob   IN OUT NOCOPY CLOB,
                          buf_str   IN OUT NOCOPY VARCHAR2,
                          str                     VARCHAR2)
   AS
   BEGIN
      IF (LENGTH (str) > 32767 - LENGTH (buf_str)) THEN
         DBMS_LOB.append (buf_lob, buf_str);
         buf_str   := str;
      ELSE
         buf_str   := buf_str || str;
      END IF;
   END add_to_clob;

   PROCEDURE flush_clob (buf_lob   IN OUT NOCOPY CLOB,
                         buf_str   IN OUT NOCOPY VARCHAR2)
   AS
   BEGIN
      DBMS_LOB.append (buf_lob, buf_str);
   END flush_clob;

   PROCEDURE tostring (obj                     json_value,
                       tagname   IN            VARCHAR2,
                       xmlstr    IN OUT NOCOPY CLOB,
                       xmlbuf    IN OUT NOCOPY VARCHAR2)
   AS
      v_obj     json;
      v_list    json_list;

      v_keys    json_list;
      v_value   json_value;
      key_str   VARCHAR2 (4000);
   BEGIN
      IF (obj.is_object ()) THEN
         add_to_clob (xmlstr, xmlbuf, '<' || tagname || '>');
         v_obj    := json (obj);

         v_keys   := v_obj.get_keys ();

         FOR i IN 1 .. v_keys.COUNT
         LOOP
            v_value   := v_obj.get (i);
            key_str   := v_keys.get (i).str;

            IF (key_str = 'content') THEN
               IF (v_value.is_array ()) THEN
                  DECLARE
                     v_l   json_list := json_list (v_value);
                  BEGIN
                     FOR j IN 1 .. v_l.COUNT
                     LOOP
                        IF (j > 1) THEN
                           add_to_clob (xmlstr, xmlbuf, CHR (13) || CHR (10));
                        END IF;

                        add_to_clob (xmlstr,
                                     xmlbuf,
                                     escapestr (v_l.get (j).TO_CHAR ()));
                     END LOOP;
                  END;
               ELSE
                  add_to_clob (xmlstr,
                               xmlbuf,
                               escapestr (v_value.TO_CHAR ()));
               END IF;
            ELSIF (v_value.is_array ()) THEN
               DECLARE
                  v_l   json_list := json_list (v_value);
               BEGIN
                  FOR j IN 1 .. v_l.COUNT
                  LOOP
                     v_value   := v_l.get (j);

                     IF (v_value.is_array ()) THEN
                        add_to_clob (xmlstr, xmlbuf, '<' || key_str || '>');
                        add_to_clob (xmlstr,
                                     xmlbuf,
                                     escapestr (v_value.TO_CHAR ()));
                        add_to_clob (xmlstr, xmlbuf, '</' || key_str || '>');
                     ELSE
                        tostring (v_value,
                                  key_str,
                                  xmlstr,
                                  xmlbuf);
                     END IF;
                  END LOOP;
               END;
            ELSIF (   v_value.is_null ()
                   OR (v_value.is_string AND v_value.get_string = '')) THEN
               add_to_clob (xmlstr, xmlbuf, '<' || key_str || '/>');
            ELSE
               tostring (v_value,
                         key_str,
                         xmlstr,
                         xmlbuf);
            END IF;
         END LOOP;

         add_to_clob (xmlstr, xmlbuf, '</' || tagname || '>');
      ELSIF (obj.is_array ()) THEN
         v_list   := json_list (obj);

         FOR i IN 1 .. v_list.COUNT
         LOOP
            v_value   := v_list.get (i);
            tostring (v_value,
                      NVL (tagname, 'array'),
                      xmlstr,
                      xmlbuf);
         END LOOP;
      ELSE
         add_to_clob (
            xmlstr,
            xmlbuf,
               '<'
            || tagname
            || '>'
            || escapestr (obj.TO_CHAR ())
            || '</'
            || tagname
            || '>');
      END IF;
   END tostring;

   FUNCTION json_to_xml (obj json, tagname VARCHAR2 DEFAULT 'root')
      RETURN XMLTYPE
   AS
      xmlstr        CLOB := EMPTY_CLOB ();
      xmlbuf        VARCHAR2 (32767) := '';
      returnvalue   XMLTYPE;
   BEGIN
      DBMS_LOB.createtemporary (xmlstr, TRUE);

      tostring (obj.to_json_value (),
                tagname,
                xmlstr,
                xmlbuf);

      flush_clob (xmlstr, xmlbuf);
      returnvalue   := xmltype ('<?xml version="1.0"?>' || xmlstr);
      DBMS_LOB.freetemporary (xmlstr);
      RETURN returnvalue;
   END;
END json_xml;
/

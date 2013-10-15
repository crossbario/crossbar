CREATE OR REPLACE PACKAGE json_helper
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

   /* Example:
   set serveroutput on;
   declare
     v_a json;
     v_b json;
   begin
     v_a := json('{a:1, b:{a:null}, e:false}');
     v_b := json('{c:3, e:{}, b:{b:2}}');
     json_helper.merge(v_a, v_b).print(false);
   end;
   --
   {"a":1,"b":{"a":null,"b":2},"e":{},"c":3}
   */
   -- Recursive merge
   -- Courtesy of Matt Nolan - edited by Jonas Krogsboell
   FUNCTION merge (p_a_json json, p_b_json json)
      RETURN json;

   -- Join two lists
   -- json_helper.join(json_list('[1,2,3]'),json_list('[4,5,6]')) -> [1,2,3,4,5,6]
   FUNCTION join (p_a_list json_list, p_b_list json_list)
      RETURN json_list;

   -- keep only specific keys in json object
   -- json_helper.keep(json('{a:1,b:2,c:3,d:4,e:5,f:6}'),json_list('["a","f","c"]')) -> {"a":1,"f":6,"c":3}
   FUNCTION keep (p_json json, p_keys json_list)
      RETURN json;

   -- remove specific keys in json object
   -- json_helper.remove(json('{a:1,b:2,c:3,d:4,e:5,f:6}'),json_list('["a","f","c"]')) -> {"b":2,"d":4,"e":5}
   FUNCTION remove (p_json json, p_keys json_list)
      RETURN json;

   --equals
   FUNCTION equals (p_v1     json_value,
                    p_v2     json_value,
                    exact    BOOLEAN DEFAULT TRUE)
      RETURN BOOLEAN;

   FUNCTION equals (p_v1 json_value, p_v2 json, exact BOOLEAN DEFAULT TRUE)
      RETURN BOOLEAN;

   FUNCTION equals (p_v1     json_value,
                    p_v2     json_list,
                    exact    BOOLEAN DEFAULT TRUE)
      RETURN BOOLEAN;

   FUNCTION equals (p_v1 json_value, p_v2 NUMBER)
      RETURN BOOLEAN;

   FUNCTION equals (p_v1 json_value, p_v2 VARCHAR2)
      RETURN BOOLEAN;

   FUNCTION equals (p_v1 json_value, p_v2 BOOLEAN)
      RETURN BOOLEAN;

   FUNCTION equals (p_v1 json_value, p_v2 CLOB)
      RETURN BOOLEAN;

   FUNCTION equals (p_v1 json, p_v2 json, exact BOOLEAN DEFAULT TRUE)
      RETURN BOOLEAN;

   FUNCTION equals (p_v1     json_list,
                    p_v2     json_list,
                    exact    BOOLEAN DEFAULT TRUE)
      RETURN BOOLEAN;

   --contains json, json_value
   --contains json_list, json_value
   FUNCTION contains (p_v1     json,
                      p_v2     json_value,
                      exact    BOOLEAN DEFAULT FALSE)
      RETURN BOOLEAN;

   FUNCTION contains (p_v1 json, p_v2 json, exact BOOLEAN DEFAULT FALSE)
      RETURN BOOLEAN;

   FUNCTION contains (p_v1 json, p_v2 json_list, exact BOOLEAN DEFAULT FALSE)
      RETURN BOOLEAN;

   FUNCTION contains (p_v1 json, p_v2 NUMBER, exact BOOLEAN DEFAULT FALSE)
      RETURN BOOLEAN;

   FUNCTION contains (p_v1 json, p_v2 VARCHAR2, exact BOOLEAN DEFAULT FALSE)
      RETURN BOOLEAN;

   FUNCTION contains (p_v1 json, p_v2 BOOLEAN, exact BOOLEAN DEFAULT FALSE)
      RETURN BOOLEAN;

   FUNCTION contains (p_v1 json, p_v2 CLOB, exact BOOLEAN DEFAULT FALSE)
      RETURN BOOLEAN;

   FUNCTION contains (p_v1     json_list,
                      p_v2     json_value,
                      exact    BOOLEAN DEFAULT FALSE)
      RETURN BOOLEAN;

   FUNCTION contains (p_v1 json_list, p_v2 json, exact BOOLEAN DEFAULT FALSE)
      RETURN BOOLEAN;

   FUNCTION contains (p_v1     json_list,
                      p_v2     json_list,
                      exact    BOOLEAN DEFAULT FALSE)
      RETURN BOOLEAN;

   FUNCTION contains (p_v1     json_list,
                      p_v2     NUMBER,
                      exact    BOOLEAN DEFAULT FALSE)
      RETURN BOOLEAN;

   FUNCTION contains (p_v1     json_list,
                      p_v2     VARCHAR2,
                      exact    BOOLEAN DEFAULT FALSE)
      RETURN BOOLEAN;

   FUNCTION contains (p_v1     json_list,
                      p_v2     BOOLEAN,
                      exact    BOOLEAN DEFAULT FALSE)
      RETURN BOOLEAN;

   FUNCTION contains (p_v1 json_list, p_v2 CLOB, exact BOOLEAN DEFAULT FALSE)
      RETURN BOOLEAN;
END json_helper;
/

CREATE OR REPLACE PACKAGE BODY json_helper
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

   --recursive merge
   FUNCTION merge (p_a_json json, p_b_json json)
      RETURN json
   AS
      l_json        json;
      l_jv          json_value;
      l_indx        NUMBER;
      l_recursive   json_value;
   BEGIN
      --
      -- Initialize our return object
      --
      l_json   := p_a_json;

      -- loop through p_b_json
      l_indx   := p_b_json.json_data.FIRST;

      LOOP
         EXIT WHEN l_indx IS NULL;
         l_jv     := p_b_json.json_data (l_indx);

         IF (l_jv.is_object) THEN
            --recursive
            l_recursive   := l_json.get (l_jv.mapname);

            IF (l_recursive IS NOT NULL AND l_recursive.is_object) THEN
               l_json.put (l_jv.mapname,
                           merge (json (l_recursive), json (l_jv)));
            ELSE
               l_json.put (l_jv.mapname, l_jv);
            END IF;
         ELSE
            l_json.put (l_jv.mapname, l_jv);
         END IF;

         --increment
         l_indx   := p_b_json.json_data.NEXT (l_indx);
      END LOOP;

      RETURN l_json;
   END merge;

   -- join two lists
   FUNCTION join (p_a_list json_list, p_b_list json_list)
      RETURN json_list
   AS
      l_json_list   json_list := p_a_list;
   BEGIN
      FOR indx IN 1 .. p_b_list.COUNT
      LOOP
         l_json_list.append (p_b_list.get (indx));
      END LOOP;

      RETURN l_json_list;
   END join;

   -- keep keys.
   FUNCTION keep (p_json json, p_keys json_list)
      RETURN json
   AS
      l_json    json := json ();
      mapname   VARCHAR2 (4000);
   BEGIN
      FOR i IN 1 .. p_keys.COUNT
      LOOP
         mapname   := p_keys.get (i).get_string;

         IF (p_json.exist (mapname)) THEN
            l_json.put (mapname, p_json.get (mapname));
         END IF;
      END LOOP;

      RETURN l_json;
   END keep;

   -- drop keys.
   FUNCTION remove (p_json json, p_keys json_list)
      RETURN json
   AS
      l_json   json := p_json;
   BEGIN
      FOR i IN 1 .. p_keys.COUNT
      LOOP
         l_json.remove (p_keys.get (i).get_string);
      END LOOP;

      RETURN l_json;
   END remove;

   --equals functions

   FUNCTION equals (p_v1 json_value, p_v2 NUMBER)
      RETURN BOOLEAN
   AS
   BEGIN
      IF (p_v2 IS NULL) THEN
         RETURN p_v1.is_null;
      END IF;

      IF (NOT p_v1.is_number) THEN
         RETURN FALSE;
      END IF;

      RETURN p_v2 = p_v1.get_number;
   END;

   FUNCTION equals (p_v1 json_value, p_v2 BOOLEAN)
      RETURN BOOLEAN
   AS
   BEGIN
      IF (p_v2 IS NULL) THEN
         RETURN p_v1.is_null;
      END IF;

      IF (NOT p_v1.is_bool) THEN
         RETURN FALSE;
      END IF;

      RETURN p_v2 = p_v1.get_bool;
   END;

   FUNCTION equals (p_v1 json_value, p_v2 VARCHAR2)
      RETURN BOOLEAN
   AS
   BEGIN
      IF (p_v2 IS NULL) THEN
         RETURN p_v1.is_null;
      END IF;

      IF (NOT p_v1.is_string) THEN
         RETURN FALSE;
      END IF;

      RETURN p_v2 = p_v1.get_string;
   END;

   FUNCTION equals (p_v1 json_value, p_v2 CLOB)
      RETURN BOOLEAN
   AS
      my_clob   CLOB;
      res       BOOLEAN;
   BEGIN
      IF (p_v2 IS NULL) THEN
         RETURN p_v1.is_null;
      END IF;

      IF (NOT p_v1.is_string) THEN
         RETURN FALSE;
      END IF;

      my_clob   := EMPTY_CLOB ();
      DBMS_LOB.createtemporary (my_clob, TRUE);
      p_v1.get_string (my_clob);

      res       := DBMS_LOB.compare (p_v2, my_clob) = 0;
      DBMS_LOB.freetemporary (my_clob);
   END;

   FUNCTION equals (p_v1 json_value, p_v2 json_value, exact BOOLEAN)
      RETURN BOOLEAN
   AS
   BEGIN
      IF (p_v2 IS NULL) THEN
         RETURN p_v1.is_null;
      END IF;

      IF (p_v2.is_number) THEN
         RETURN equals (p_v1, p_v2.get_number);
      END IF;

      IF (p_v2.is_bool) THEN
         RETURN equals (p_v1, p_v2.get_bool);
      END IF;

      IF (p_v2.is_object) THEN
         RETURN equals (p_v1, json (p_v2), exact);
      END IF;

      IF (p_v2.is_array) THEN
         RETURN equals (p_v1, json_list (p_v2), exact);
      END IF;

      IF (p_v2.is_string) THEN
         IF (p_v2.extended_str IS NULL) THEN
            RETURN equals (p_v1, p_v2.get_string);
         ELSE
            DECLARE
               my_clob   CLOB;
               res       BOOLEAN;
            BEGIN
               my_clob   := EMPTY_CLOB ();
               DBMS_LOB.createtemporary (my_clob, TRUE);
               p_v2.get_string (my_clob);
               res       := equals (p_v1, my_clob);
               DBMS_LOB.freetemporary (my_clob);
               RETURN res;
            END;
         END IF;
      END IF;

      RETURN FALSE;                                      --should never happen
   END;

   FUNCTION equals (p_v1 json_value, p_v2 json_list, exact BOOLEAN)
      RETURN BOOLEAN
   AS
      cmp   json_list;
      res   BOOLEAN := TRUE;
   BEGIN
      --  p_v1.print(false);
      --  p_v2.print(false);
      --  dbms_output.put_line('labc1'||case when exact then 'X' else 'U' end);

      IF (p_v2 IS NULL) THEN
         RETURN p_v1.is_null;
      END IF;

      IF (NOT p_v1.is_array) THEN
         RETURN FALSE;
      END IF;

      --  dbms_output.put_line('labc2'||case when exact then 'X' else 'U' end);

      cmp   := json_list (p_v1);

      IF (cmp.COUNT != p_v2.COUNT AND exact) THEN
         RETURN FALSE;
      END IF;

      --  dbms_output.put_line('labc3'||case when exact then 'X' else 'U' end);

      IF (exact) THEN
         FOR i IN 1 .. cmp.COUNT
         LOOP
            res   := equals (cmp.get (i), p_v2.get (i), exact);

            IF (NOT res) THEN
               RETURN res;
            END IF;
         END LOOP;
      ELSE
         --  dbms_output.put_line('labc4'||case when exact then 'X' else 'U' end);
         IF (p_v2.COUNT > cmp.COUNT) THEN
            RETURN FALSE;
         END IF;

         --  dbms_output.put_line('labc5'||case when exact then 'X' else 'U' end);

         --match sublist here!
         FOR x IN 0 .. (cmp.COUNT - p_v2.COUNT)
         LOOP
            --  dbms_output.put_line('labc7'||x);

            FOR i IN 1 .. p_v2.COUNT
            LOOP
               res   := equals (cmp.get (x + i), p_v2.get (i), exact);

               IF (NOT res) THEN
                  GOTO next_index;
               END IF;
            END LOOP;

            RETURN TRUE;

           <<next_index>>
            NULL;
         END LOOP;

         --  dbms_output.put_line('labc7'||case when exact then 'X' else 'U' end);

         RETURN FALSE;                                              --no match
      END IF;

      RETURN res;
   END;

   FUNCTION equals (p_v1 json_value, p_v2 json, exact BOOLEAN)
      RETURN BOOLEAN
   AS
      cmp   json;
      res   BOOLEAN := TRUE;
   BEGIN
      --  p_v1.print(false);
      --  p_v2.print(false);
      --  dbms_output.put_line('abc1');

      IF (p_v2 IS NULL) THEN
         RETURN p_v1.is_null;
      END IF;

      IF (NOT p_v1.is_object) THEN
         RETURN FALSE;
      END IF;

      cmp   := json (p_v1);

      --  dbms_output.put_line('abc2');

      IF (cmp.COUNT != p_v2.COUNT AND exact) THEN
         RETURN FALSE;
      END IF;

      --  dbms_output.put_line('abc3');
      DECLARE
         k1          json_list := p_v2.get_keys;
         key_index   NUMBER;
      BEGIN
         FOR i IN 1 .. k1.COUNT
         LOOP
            key_index   := cmp.index_of (k1.get (i).get_string);

            IF (key_index = -1) THEN
               RETURN FALSE;
            END IF;

            IF (exact) THEN
               IF (NOT equals (p_v2.get (i), cmp.get (key_index), TRUE)) THEN
                  RETURN FALSE;
               END IF;
            ELSE
               --non exact
               DECLARE
                  v1   json_value := cmp.get (key_index);
                  v2   json_value := p_v2.get (i);
               BEGIN
                  --  dbms_output.put_line('abc3 1/2');
                  --            v1.print(false);
                  --            v2.print(false);

                  IF (v1.is_object AND v2.is_object) THEN
                     IF (NOT equals (v1, v2, FALSE)) THEN
                        RETURN FALSE;
                     END IF;
                  ELSIF (v1.is_array AND v2.is_array) THEN
                     IF (NOT equals (v1, v2, FALSE)) THEN
                        RETURN FALSE;
                     END IF;
                  ELSE
                     IF (NOT equals (v1, v2, TRUE)) THEN
                        RETURN FALSE;
                     END IF;
                  END IF;
               END;
            END IF;
         END LOOP;
      END;

      --  dbms_output.put_line('abc4');

      RETURN TRUE;
   END;

   FUNCTION equals (p_v1 json, p_v2 json, exact BOOLEAN)
      RETURN BOOLEAN
   AS
   BEGIN
      RETURN equals (p_v1.to_json_value, p_v2, exact);
   END;

   FUNCTION equals (p_v1 json_list, p_v2 json_list, exact BOOLEAN)
      RETURN BOOLEAN
   AS
   BEGIN
      RETURN equals (p_v1.to_json_value, p_v2, exact);
   END;

   --contain
   FUNCTION contains (p_v1 json, p_v2 json_value, exact BOOLEAN)
      RETURN BOOLEAN
   AS
      v_values   json_list;
   BEGIN
      IF (equals (p_v1.to_json_value, p_v2, exact)) THEN
         RETURN TRUE;
      END IF;

      v_values   := p_v1.get_values;

      FOR i IN 1 .. v_values.COUNT
      LOOP
         DECLARE
            v_val   json_value := v_values.get (i);
         BEGIN
            IF (v_val.is_object) THEN
               IF (contains (json (v_val), p_v2, exact)) THEN
                  RETURN TRUE;
               END IF;
            END IF;

            IF (v_val.is_array) THEN
               IF (contains (json_list (v_val), p_v2, exact)) THEN
                  RETURN TRUE;
               END IF;
            END IF;

            IF (equals (v_val, p_v2, exact)) THEN
               RETURN TRUE;
            END IF;
         END;
      END LOOP;

      RETURN FALSE;
   END;

   FUNCTION contains (p_v1 json_list, p_v2 json_value, exact BOOLEAN)
      RETURN BOOLEAN
   AS
   BEGIN
      IF (equals (p_v1.to_json_value, p_v2, exact)) THEN
         RETURN TRUE;
      END IF;

      FOR i IN 1 .. p_v1.COUNT
      LOOP
         DECLARE
            v_val   json_value := p_v1.get (i);
         BEGIN
            IF (v_val.is_object) THEN
               IF (contains (json (v_val), p_v2, exact)) THEN
                  RETURN TRUE;
               END IF;
            END IF;

            IF (v_val.is_array) THEN
               IF (contains (json_list (v_val), p_v2, exact)) THEN
                  RETURN TRUE;
               END IF;
            END IF;

            IF (equals (v_val, p_v2, exact)) THEN
               RETURN TRUE;
            END IF;
         END;
      END LOOP;

      RETURN FALSE;
   END;

   FUNCTION contains (p_v1 json, p_v2 json, exact BOOLEAN)
      RETURN BOOLEAN
   AS
   BEGIN
      RETURN contains (p_v1, p_v2.to_json_value, exact);
   END;

   FUNCTION contains (p_v1 json, p_v2 json_list, exact BOOLEAN)
      RETURN BOOLEAN
   AS
   BEGIN
      RETURN contains (p_v1, p_v2.to_json_value, exact);
   END;

   FUNCTION contains (p_v1 json, p_v2 NUMBER, exact BOOLEAN)
      RETURN BOOLEAN
   AS
   BEGIN
      RETURN contains (p_v1, json_value (p_v2), exact);
   END;

   FUNCTION contains (p_v1 json, p_v2 VARCHAR2, exact BOOLEAN)
      RETURN BOOLEAN
   AS
   BEGIN
      RETURN contains (p_v1, json_value (p_v2), exact);
   END;

   FUNCTION contains (p_v1 json, p_v2 BOOLEAN, exact BOOLEAN)
      RETURN BOOLEAN
   AS
   BEGIN
      RETURN contains (p_v1, json_value (p_v2), exact);
   END;

   FUNCTION contains (p_v1 json, p_v2 CLOB, exact BOOLEAN)
      RETURN BOOLEAN
   AS
   BEGIN
      RETURN contains (p_v1, json_value (p_v2), exact);
   END;

   FUNCTION contains (p_v1 json_list, p_v2 json, exact BOOLEAN)
      RETURN BOOLEAN
   AS
   BEGIN
      RETURN contains (p_v1, p_v2.to_json_value, exact);
   END;

   FUNCTION contains (p_v1 json_list, p_v2 json_list, exact BOOLEAN)
      RETURN BOOLEAN
   AS
   BEGIN
      RETURN contains (p_v1, p_v2.to_json_value, exact);
   END;

   FUNCTION contains (p_v1 json_list, p_v2 NUMBER, exact BOOLEAN)
      RETURN BOOLEAN
   AS
   BEGIN
      RETURN contains (p_v1, json_value (p_v2), exact);
   END;

   FUNCTION contains (p_v1 json_list, p_v2 VARCHAR2, exact BOOLEAN)
      RETURN BOOLEAN
   AS
   BEGIN
      RETURN contains (p_v1, json_value (p_v2), exact);
   END;

   FUNCTION contains (p_v1 json_list, p_v2 BOOLEAN, exact BOOLEAN)
      RETURN BOOLEAN
   AS
   BEGIN
      RETURN contains (p_v1, json_value (p_v2), exact);
   END;

   FUNCTION contains (p_v1 json_list, p_v2 CLOB, exact BOOLEAN)
      RETURN BOOLEAN
   AS
   BEGIN
      RETURN contains (p_v1, json_value (p_v2), exact);
   END;
END json_helper;
/


/**

set serveroutput on;
declare
  v1 json := json('{a:34, b:true, a2:{a1:2,a3:{}}, c:{a:[1,2,3,4,5,true]}, g:3}');

  v2 json := json('{a:34, b:true, a2:{a1:2}}');


begin
  if(json_helper.contains(v1, v2)) then
    dbms_output.put_line('************123');
  end if;


end;

**/

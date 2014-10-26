CREATE OR REPLACE PACKAGE json_dyn
   AUTHID CURRENT_USER
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

   null_as_empty_string   BOOLEAN NOT NULL := TRUE;                 --varchar2
   include_dates          BOOLEAN NOT NULL := TRUE;                     --date
   include_clobs          BOOLEAN NOT NULL := TRUE;
   include_blobs          BOOLEAN NOT NULL := FALSE;

  /* usage example:
   * declare
   *   res json_list;
   * begin
   *   res := json_dyn.executeList(
   *            'select :bindme as one, :lala as two from dual where dummy in :arraybind',
   *            json('{bindme:"4", lala:123, arraybind:[1,2,3,"X"]}')
   *          );
   *   res.print;
   * end;
   */

   /* list with objects */
   FUNCTION executelist (stmt       VARCHAR2,
                         bindvar    json DEFAULT NULL,
                         cur_num    NUMBER DEFAULT NULL)
      RETURN json_list;

   /* object with lists */
   FUNCTION executeobject (stmt       VARCHAR2,
                           bindvar    json DEFAULT NULL,
                           cur_num    NUMBER DEFAULT NULL)
      RETURN json;

   FUNCTION executelist (stmt IN OUT SYS_REFCURSOR)
      RETURN json_list;

   FUNCTION executeobject (stmt IN OUT SYS_REFCURSOR)
      RETURN json;
END json_dyn;
/

CREATE OR REPLACE PACKAGE BODY json_dyn
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

   -- 11gR2
   FUNCTION executelist (stmt IN OUT SYS_REFCURSOR)
      RETURN json_list
   AS
      l_cur   NUMBER;
   BEGIN
      l_cur   := DBMS_SQL.to_cursor_number (stmt);
      RETURN json_dyn.executelist (NULL, NULL, l_cur);
   END;

   -- 11gR2
   FUNCTION executeobject (stmt IN OUT SYS_REFCURSOR)
      RETURN json
   AS
      l_cur   NUMBER;
   BEGIN
      l_cur   := DBMS_SQL.to_cursor_number (stmt);
      RETURN json_dyn.executeobject (NULL, NULL, l_cur);
   END;

   PROCEDURE bind_json (l_cur NUMBER, bindvar json)
   AS
      keylist   json_list := bindvar.get_keys ();
   BEGIN
      FOR i IN 1 .. keylist.COUNT
      LOOP
         IF (bindvar.get (i).get_type = 'number') THEN
            DBMS_SQL.bind_variable (l_cur,
                                    ':' || keylist.get (i).get_string,
                                    bindvar.get (i).get_number);
         ELSIF (bindvar.get (i).get_type = 'array') THEN
            DECLARE
               v_bind   DBMS_SQL.varchar2_table;
               v_arr    json_list := json_list (bindvar.get (i));
            BEGIN
               FOR j IN 1 .. v_arr.COUNT
               LOOP
                  v_bind (j)   := v_arr.get (j).value_of;
               END LOOP;

               DBMS_SQL.bind_array (l_cur,
                                    ':' || keylist.get (i).get_string,
                                    v_bind);
            END;
         ELSE
            DBMS_SQL.bind_variable (l_cur,
                                    ':' || keylist.get (i).get_string,
                                    bindvar.get (i).value_of ());
         END IF;
      END LOOP;
   END bind_json;

   /* list with objects */
   FUNCTION executelist (stmt VARCHAR2, bindvar json, cur_num NUMBER)
      RETURN json_list
   AS
      l_cur        NUMBER;
      l_dtbl       DBMS_SQL.desc_tab;
      l_cnt        NUMBER;
      l_status     NUMBER;
      l_val        VARCHAR2 (4000);
      outer_list   json_list := json_list ();
      inner_obj    json;
      conv         NUMBER;
      read_date    DATE;
      read_clob    CLOB;
      read_blob    BLOB;
      col_type     NUMBER;
   BEGIN
      IF (cur_num IS NOT NULL) THEN
         l_cur   := cur_num;
      ELSE
         l_cur   := DBMS_SQL.open_cursor;
         DBMS_SQL.parse (l_cur, stmt, DBMS_SQL.native);

         IF (bindvar IS NOT NULL) THEN
            bind_json (l_cur, bindvar);
         END IF;
      END IF;

      DBMS_SQL.describe_columns (l_cur, l_cnt, l_dtbl);

      FOR i IN 1 .. l_cnt
      LOOP
         col_type   := l_dtbl (i).col_type;

         --dbms_output.put_line(col_type);
         IF (col_type = 12) THEN
            DBMS_SQL.define_column (l_cur, i, read_date);
         ELSIF (col_type = 112) THEN
            DBMS_SQL.define_column (l_cur, i, read_clob);
         ELSIF (col_type = 113) THEN
            DBMS_SQL.define_column (l_cur, i, read_blob);
         ELSIF (col_type IN (1, 2, 96)) THEN
            DBMS_SQL.define_column (l_cur,
                                    i,
                                    l_val,
                                    4000);
         END IF;
      END LOOP;

      IF (cur_num IS NULL) THEN
         l_status   := DBMS_SQL.execute (l_cur);
      END IF;

      --loop through rows
      WHILE (DBMS_SQL.fetch_rows (l_cur) > 0)
      LOOP
         inner_obj   := json ();                           --init for each row

         --loop through columns
         FOR i IN 1 .. l_cnt
         LOOP
            CASE TRUE
               --handling string types
               WHEN l_dtbl (i).col_type IN (1, 96) THEN            -- varchar2
                  DBMS_SQL.COLUMN_VALUE (l_cur, i, l_val);

                  IF (l_val IS NULL) THEN
                     IF (null_as_empty_string) THEN
                        inner_obj.put (l_dtbl (i).col_name, ''); --treatet as emptystring?
                     ELSE
                        inner_obj.put (l_dtbl (i).col_name,
                                       json_value.makenull);            --null
                     END IF;
                  ELSE
                     inner_obj.put (l_dtbl (i).col_name, json_value (l_val)); --null
                  END IF;
               --dbms_output.put_line(l_dtbl(i).col_name||' --> '||l_val||'varchar2' ||l_dtbl(i).col_type);
               --handling number types
               WHEN l_dtbl (i).col_type = 2 THEN                     -- number
                  DBMS_SQL.COLUMN_VALUE (l_cur, i, l_val);
                  conv   := l_val;
                  inner_obj.put (l_dtbl (i).col_name, conv);
               -- dbms_output.put_line(l_dtbl(i).col_name||' --> '||l_val||'number ' ||l_dtbl(i).col_type);
               WHEN l_dtbl (i).col_type = 12 THEN                      -- date
                  IF (include_dates) THEN
                     DBMS_SQL.COLUMN_VALUE (l_cur, i, read_date);
                     inner_obj.put (l_dtbl (i).col_name,
                                    json_ext.to_json_value (read_date));
                  END IF;
               --dbms_output.put_line(l_dtbl(i).col_name||' --> '||l_val||'date ' ||l_dtbl(i).col_type);
               WHEN l_dtbl (i).col_type = 112 THEN                      --clob
                  IF (include_clobs) THEN
                     DBMS_SQL.COLUMN_VALUE (l_cur, i, read_clob);
                     inner_obj.put (l_dtbl (i).col_name,
                                    json_value (read_clob));
                  END IF;
               WHEN l_dtbl (i).col_type = 113 THEN                      --blob
                  IF (include_blobs) THEN
                     DBMS_SQL.COLUMN_VALUE (l_cur, i, read_blob);

                     IF (DBMS_LOB.getlength (read_blob) > 0) THEN
                        inner_obj.put (l_dtbl (i).col_name,
                                       json_ext.encode (read_blob));
                     ELSE
                        inner_obj.put (l_dtbl (i).col_name,
                                       json_value.makenull);
                     END IF;
                  END IF;
               ELSE
                  NULL;                                  --discard other types
            END CASE;
         END LOOP;

         outer_list.append (inner_obj.to_json_value);
      END LOOP;

      DBMS_SQL.close_cursor (l_cur);
      RETURN outer_list;
   END executelist;

   /* object with lists */
   FUNCTION executeobject (stmt VARCHAR2, bindvar json, cur_num NUMBER)
      RETURN json
   AS
      l_cur              NUMBER;
      l_dtbl             DBMS_SQL.desc_tab;
      l_cnt              NUMBER;
      l_status           NUMBER;
      l_val              VARCHAR2 (4000);
      inner_list_names   json_list := json_list ();
      inner_list_data    json_list := json_list ();
      data_list          json_list;
      outer_obj          json := json ();
      conv               NUMBER;
      read_date          DATE;
      read_clob          CLOB;
      read_blob          BLOB;
      col_type           NUMBER;
   BEGIN
      IF (cur_num IS NOT NULL) THEN
         l_cur   := cur_num;
      ELSE
         l_cur   := DBMS_SQL.open_cursor;
         DBMS_SQL.parse (l_cur, stmt, DBMS_SQL.native);

         IF (bindvar IS NOT NULL) THEN
            bind_json (l_cur, bindvar);
         END IF;
      END IF;

      DBMS_SQL.describe_columns (l_cur, l_cnt, l_dtbl);

      FOR i IN 1 .. l_cnt
      LOOP
         col_type   := l_dtbl (i).col_type;

         IF (col_type = 12) THEN
            DBMS_SQL.define_column (l_cur, i, read_date);
         ELSIF (col_type = 112) THEN
            DBMS_SQL.define_column (l_cur, i, read_clob);
         ELSIF (col_type = 113) THEN
            DBMS_SQL.define_column (l_cur, i, read_blob);
         ELSIF (col_type IN (1, 2, 96)) THEN
            DBMS_SQL.define_column (l_cur,
                                    i,
                                    l_val,
                                    4000);
         END IF;
      END LOOP;

      IF (cur_num IS NULL) THEN
         l_status   := DBMS_SQL.execute (l_cur);
      END IF;

      --build up name_list
      FOR i IN 1 .. l_cnt
      LOOP
         CASE l_dtbl (i).col_type
            WHEN 1 THEN
               inner_list_names.append (l_dtbl (i).col_name);
            WHEN 96 THEN
               inner_list_names.append (l_dtbl (i).col_name);
            WHEN 2 THEN
               inner_list_names.append (l_dtbl (i).col_name);
            WHEN 12 THEN
               IF (include_dates) THEN
                  inner_list_names.append (l_dtbl (i).col_name);
               END IF;
            WHEN 112 THEN
               IF (include_clobs) THEN
                  inner_list_names.append (l_dtbl (i).col_name);
               END IF;
            WHEN 113 THEN
               IF (include_blobs) THEN
                  inner_list_names.append (l_dtbl (i).col_name);
               END IF;
            ELSE
               NULL;
         END CASE;
      END LOOP;

      --loop through rows
      WHILE (DBMS_SQL.fetch_rows (l_cur) > 0)
      LOOP
         data_list   := json_list ();

         --loop through columns
         FOR i IN 1 .. l_cnt
         LOOP
            CASE TRUE
               --handling string types
               WHEN l_dtbl (i).col_type IN (1, 96) THEN            -- varchar2
                  DBMS_SQL.COLUMN_VALUE (l_cur, i, l_val);

                  IF (l_val IS NULL) THEN
                     IF (null_as_empty_string) THEN
                        data_list.append ('');       --treatet as emptystring?
                     ELSE
                        data_list.append (json_value.makenull);         --null
                     END IF;
                  ELSE
                     data_list.append (json_value (l_val));             --null
                  END IF;
               --dbms_output.put_line(l_dtbl(i).col_name||' --> '||l_val||'varchar2' ||l_dtbl(i).col_type);
               --handling number types
               WHEN l_dtbl (i).col_type = 2 THEN                     -- number
                  DBMS_SQL.COLUMN_VALUE (l_cur, i, l_val);
                  conv   := l_val;
                  data_list.append (conv);
               -- dbms_output.put_line(l_dtbl(i).col_name||' --> '||l_val||'number ' ||l_dtbl(i).col_type);
               WHEN l_dtbl (i).col_type = 12 THEN                      -- date
                  IF (include_dates) THEN
                     DBMS_SQL.COLUMN_VALUE (l_cur, i, read_date);
                     data_list.append (json_ext.to_json_value (read_date));
                  END IF;
               --dbms_output.put_line(l_dtbl(i).col_name||' --> '||l_val||'date ' ||l_dtbl(i).col_type);
               WHEN l_dtbl (i).col_type = 112 THEN                      --clob
                  IF (include_clobs) THEN
                     DBMS_SQL.COLUMN_VALUE (l_cur, i, read_clob);
                     data_list.append (json_value (read_clob));
                  END IF;
               WHEN l_dtbl (i).col_type = 113 THEN                      --blob
                  IF (include_blobs) THEN
                     DBMS_SQL.COLUMN_VALUE (l_cur, i, read_blob);

                     IF (DBMS_LOB.getlength (read_blob) > 0) THEN
                        data_list.append (json_ext.encode (read_blob));
                     ELSE
                        data_list.append (json_value.makenull);
                     END IF;
                  END IF;
               ELSE
                  NULL;                                  --discard other types
            END CASE;
         END LOOP;

         inner_list_data.append (data_list);
      END LOOP;

      outer_obj.put ('names', inner_list_names.to_json_value);
      outer_obj.put ('data', inner_list_data.to_json_value);
      DBMS_SQL.close_cursor (l_cur);
      RETURN outer_obj;
   END executeobject;
END json_dyn;
/

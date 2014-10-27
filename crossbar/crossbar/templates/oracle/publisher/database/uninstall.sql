--
-- Uninstall Crossbar.io Oracle database integration.
--
-- To run, connect as CBDB and run the script using SQL*Plus:
--
-- sqlplus cbdb/crossbar@localhost:1521/orcl @uninstall.sql
--


-- Gracefully remove all objects previously installed.
-- See also: http://stackoverflow.com/a/1801453/884770
--

--
-- Pipes
--
DECLARE
   l_id INTEGER;
BEGIN
   l_id := SYS.DBMS_PIPE.remove_pipe(pipename => 'crossbar_on_publish');
   l_id := SYS.DBMS_PIPE.remove_pipe(pipename => 'crossbar_on_export');
END;
/

--
-- Public Synonyms
--
DECLARE
   TYPE table_of_varchar IS TABLE OF VARCHAR2(30);
   l_objects   table_of_varchar;
   l_sql       VARCHAR2(32767);
BEGIN
   l_objects := table_of_varchar(
      'crossbar',
      'crossbar_event',
      'crossbar_endpoint',
      'crossbar_session',
      'crossbar_sessionids',
      'crossbar_authkeys');
   FOR i IN 1 .. l_objects.count
   LOOP
      BEGIN
         l_sql := 'DROP PUBLIC SYNONYM ' || l_objects(i);
         DBMS_OUTPUT.put_line(l_sql);
         EXECUTE IMMEDIATE l_sql;
      EXCEPTION
         WHEN OTHERS THEN
            IF SQLCODE != -1432 THEN
               RAISE;
            END IF;
      END;
   END LOOP;
END;
/

--
-- Packages
--
DECLARE
   TYPE table_of_varchar IS TABLE OF VARCHAR2(30);
   l_objects   table_of_varchar;
   l_sql       VARCHAR2(32767);
BEGIN
   l_objects := table_of_varchar(
      'crossbar',
      --
      'json_parser',
      'json_printer',
      'json_ext',
      'json_dyn',
      'json_ml',
      'json_xml',
      'json_util_pkg',
      'json_helper',
      'json_ac'
   );
   FOR i IN 1 .. l_objects.count
   LOOP
      BEGIN
         l_sql := 'DROP PACKAGE ' || l_objects(i);
         DBMS_OUTPUT.put_line(l_sql);
         EXECUTE IMMEDIATE l_sql;
      EXCEPTION
         WHEN OTHERS THEN
            IF SQLCODE != -4043 THEN
               RAISE;
            END IF;
      END;
   END LOOP;
END;
/

--
-- Views
--
DECLARE
   TYPE table_of_varchar IS TABLE OF VARCHAR2(30);
   l_objects   table_of_varchar;
   l_sql       VARCHAR2(32767);
BEGIN
   l_objects := table_of_varchar(
      'crossbar_event',
      'crossbar_endpoint'
   );
   FOR i IN 1 .. l_objects.count
   LOOP
      BEGIN
         l_sql := 'DROP VIEW ' || l_objects(i);
         DBMS_OUTPUT.put_line(l_sql);
         EXECUTE IMMEDIATE l_sql;
      EXCEPTION
         WHEN OTHERS THEN
            IF SQLCODE != -942 THEN
               RAISE;
            END IF;
      END;
   END LOOP;
END;
/

--
-- Tables
--
DECLARE
   TYPE table_of_varchar IS TABLE OF VARCHAR2(30);
   l_objects   table_of_varchar;
   l_sql       VARCHAR2(32767);
BEGIN
   l_objects := table_of_varchar(
      'config',
      'event',
      'endpoint'
   );
   FOR i IN 1 .. l_objects.count
   LOOP
      BEGIN
         l_sql := 'DROP TABLE ' || l_objects(i);
         DBMS_OUTPUT.put_line(l_sql);
         EXECUTE IMMEDIATE l_sql;
      EXCEPTION
         WHEN OTHERS THEN
            IF SQLCODE != -942 THEN
               RAISE;
            END IF;
      END;
   END LOOP;
END;
/

--
-- Sequences
--
DECLARE
   TYPE table_of_varchar IS TABLE OF VARCHAR2(30);
   l_objects   table_of_varchar;
   l_sql       VARCHAR2(32767);
BEGIN
   l_objects := table_of_varchar(
      'event_id',
      'endpoint_id'
   );
   FOR i IN 1 .. l_objects.count
   LOOP
      BEGIN
         l_sql := 'DROP SEQUENCE ' || l_objects(i);
         DBMS_OUTPUT.put_line(l_sql);
         EXECUTE IMMEDIATE l_sql;
      EXCEPTION
         WHEN OTHERS THEN
            IF SQLCODE != -2289 THEN
               RAISE;
            END IF;
      END;
   END LOOP;
END;
/

--
-- Types
--
DECLARE
   TYPE table_of_varchar IS TABLE OF VARCHAR2(30);
   l_objects   table_of_varchar;
   l_sql       VARCHAR2(32767);
BEGIN
   l_objects := table_of_varchar(
      'crossbar_session',
      'crossbar_sessionids',
      'crossbar_authkeys',
      't_arg_types',
      't_arg_inouts',
      --
      'json',
      'json_member_array',
      'json_member',
      'json_list',
      'json_element_array',
      'json_element',
      'json_bool',
      'json_null',
      'json_value_array',
      'json_value'
   );
   FOR i IN 1 .. l_objects.count
   LOOP
      BEGIN
         l_sql := 'DROP TYPE ' || l_objects(i) || ' FORCE';
         DBMS_OUTPUT.put_line(l_sql);
         EXECUTE IMMEDIATE l_sql;
      EXCEPTION
         WHEN OTHERS THEN
            IF SQLCODE != -4043 THEN
               RAISE;
            END IF;
      END;
   END LOOP;
END;
/

show errors;
exit;
/

--
-- Remove all Crossbar.io users from the database. WARNING: This is destructive.
--
-- To run, connect as SYS and run the script using SQL*Plus:
--
-- sqlplus sys/oracle@localhost:1521/orcl as sysdba @remove_users.sql
--

BEGIN
   -- kick all sessions for Crossbar.io users
   --
   FOR r IN (SELECT s.sid, s.serial#
               FROM v$session s
              WHERE s.username IN (UPPER('{{ cbadapter }}'), UPPER('{{ cbdb }}') ))
   LOOP
      EXECUTE IMMEDIATE
         'ALTER SYSTEM KILL SESSION ''' || r.sid || ',' || r.serial# || '''';
   END LOOP;
END;
/

BEGIN
   EXECUTE IMMEDIATE 'DROP USER {{ cbadapter }} CASCADE';
EXCEPTION
   WHEN OTHERS THEN
      IF SQLCODE != -1918 THEN
         RAISE;
      END IF;
END;
/

BEGIN
   EXECUTE IMMEDIATE 'DROP USER {{ cbdb }} CASCADE';
EXCEPTION
   WHEN OTHERS THEN
      IF SQLCODE != -1918 THEN
         RAISE;
      END IF;
END;
/

show errors;
exit;
/

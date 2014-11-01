--
-- Create Crossbar.io users.
--
-- To run, connect as SYS and run the script using SQL*Plus:
--
-- Password provided in command (not recommended):
--
-- sqlplus sys/oracle@localhost:1521/orcl as sysdba @create_users.sql
--
-- Or password prompted for (see: http://blog.oracle48.nl/sqlplus-and-easy-connect-without-password-on-the-command-line/)
--
-- sqlplus sys@\"localhost:1521/orcl\" as sysdba @create_users.sql
--

--
-- Create Crossbar.io Adapter User
--
CREATE USER {{ cbadapter }} IDENTIFIED BY {{ cbadapter_password }}
/

GRANT CREATE SESSION TO {{ cbadapter }}
/


--
-- Create Crossbar.io Database User
--
CREATE USER {{ cbdb }} IDENTIFIED BY {{ cbdb_password }}
/

ALTER USER {{ cbdb }} DEFAULT TABLESPACE {{ cbdb_tablespace }} QUOTA UNLIMITED ON {{ cbdb_tablespace }}
/

GRANT CREATE SESSION TO {{ cbdb }}
/

GRANT CREATE TABLE TO {{ cbdb }}
/

GRANT CREATE VIEW TO {{ cbdb }}
/

GRANT CREATE SEQUENCE TO {{ cbdb }}
/

GRANT CREATE TYPE TO {{ cbdb }}
/

GRANT CREATE PROCEDURE TO {{ cbdb }}
/

GRANT CREATE TRIGGER TO {{ cbdb }}
/

GRANT EXECUTE ON SYS.DBMS_PIPE TO {{ cbdb }}
/

GRANT EXECUTE ON SYS.DBMS_LOCK TO {{ cbdb }}
/

GRANT EXECUTE ON SYS.DBMS_SESSION TO {{ cbdb }}
/

GRANT EXECUTE ON SYS.DBMS_LOB TO {{ cbdb }}
/

GRANT EXECUTE ON SYS.DBMS_TYPES TO {{ cbdb }}
/

GRANT EXECUTE ON SYS.DBMS_STATS TO {{ cbdb }}
/

GRANT EXECUTE ON SYS.DBMS_SQL TO {{ cbdb }}
/

GRANT EXECUTE ON SYS.DBMS_UTILITY TO {{ cbdb }}
/

GRANT EXECUTE ON SYS.DBMS_XMLGEN TO {{ cbdb }}
/

GRANT EXECUTE ON SYS.DBMS_RANDOM TO {{ cbdb }}
/

GRANT EXECUTE ON SYS.DBMS_CRYPTO TO {{ cbdb }}
/

GRANT EXECUTE ON SYS.DBMS_OUTPUT TO {{ cbdb }}
/

GRANT EXECUTE ON SYS.DBMS_DB_VERSION TO {{ cbdb }}
/

GRANT EXECUTE ON SYS.DBMS_APPLICATION_INFO TO {{ cbdb }}
/

GRANT EXECUTE ON SYS.DBMS_AQADM TO {{ cbdb }}
/

GRANT EXECUTE ON SYS.DBMS_AQ TO {{ cbdb }}
/

GRANT CREATE PUBLIC SYNONYM TO {{ cbdb }}
/

GRANT DROP PUBLIC SYNONYM TO {{ cbdb }}
/

show errors;
exit;
/

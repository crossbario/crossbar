ALTER SESSION SET PLSQL_OPTIMIZE_LEVEL = 3;
ALTER SESSION SET plsql_code_type = 'NATIVE';
/

BEGIN
   EXECUTE IMMEDIATE 'DROP PUBLIC SYNONYM crossbar';
EXCEPTION
   WHEN OTHERS THEN
      IF SQLCODE != -1432 THEN
         RAISE;
      END IF;
END;
/

@@crossbar/crossbar_spec.sql
@@crossbar/crossbar_body.sql

CREATE PUBLIC SYNONYM crossbar FOR crossbar
/

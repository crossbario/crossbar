@@create_schema.sql

ALTER SESSION SET PLSQL_OPTIMIZE_LEVEL = 3;
ALTER SESSION SET plsql_code_type = 'NATIVE';
/

@@crossbar_spec.sql
@@crossbar_body.sql


CREATE PUBLIC SYNONYM crossbar FOR crossbar;
/

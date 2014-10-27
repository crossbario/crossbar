--
-- Install Crossbar.io Oracle database integration.
--
-- To run, connect as CBDB and run the script using SQL*Plus:
--
-- sqlplus cbdb/crossbar@localhost:1521/orcl @install.sql
--

PROMPT ****** Installing Crossbar.io Oracle Integration  *******

@@pljson/install.sql

@@create_schema.sql

@@create_packages.sql

PROMPT ****** Installation complete  *******

show errors;
exit;
/

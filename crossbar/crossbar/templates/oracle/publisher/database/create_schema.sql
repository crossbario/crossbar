CREATE TYPE crossbar_sessionids IS TABLE OF VARCHAR2(16) NOT NULL
/

CREATE TYPE crossbar_authkeys IS TABLE OF VARCHAR2(30)
/

CREATE TYPE t_arg_types IS TABLE OF VARCHAR2(96)
/

CREATE TYPE t_arg_inouts IS TABLE OF VARCHAR2(9)
/

CREATE OR REPLACE TYPE crossbar_session AS OBJECT
(
   sessionid   VARCHAR2(16),
   authkey     VARCHAR2(30),
   data        JSON
)
/

CREATE SEQUENCE event_id
/

CREATE SEQUENCE endpoint_id
/

CREATE TABLE config
(
   key                 VARCHAR2(30)                     PRIMARY KEY,
   value               VARCHAR2(4000)                   NOT NULL
)
/

CREATE TABLE endpoint
(
   id                  NUMBER(38)                       PRIMARY KEY,
   created_at          TIMESTAMP                        NOT NULL,
   created_by          VARCHAR2(30)                     NOT NULL,
   modified_at         TIMESTAMP,
   schema              VARCHAR2(30)                     NOT NULL,
   package             VARCHAR2(30)                     NOT NULL,
   procedure           VARCHAR2(30)                     NOT NULL,
   object_id           NUMBER                           NOT NULL,
   subprogram_id       NUMBER                           NOT NULL,
   return_type         VARCHAR2(30),
   args_cnt            NUMBER                           NOT NULL,
   arg_types           t_arg_types,
   arg_inouts          t_arg_inouts,
   uri                 NVARCHAR2({{ nchar_maxlen }})      NOT NULL,
   authkeys            crossbar_authkeys
)
NESTED TABLE authkeys   STORE AS endpoint_authkeys
NESTED TABLE arg_types  STORE AS endpoint_arg_types
NESTED TABLE arg_inouts STORE AS endpoint_arg_inouts
/

CREATE UNIQUE INDEX idx_endpoint1 ON endpoint (uri)
/

CREATE TABLE event
(
   id                  NUMBER(38)                       PRIMARY KEY,
   published_at        TIMESTAMP                        NOT NULL,
   published_by        VARCHAR2(30)                     NOT NULL,
   processed_at        TIMESTAMP,
   processed_status    INT,
   processed_len       NUMBER(38),
   processed_errmsg    VARCHAR2(4000),
   dispatch_status     INT,
   dispatch_success    NUMBER(38),
   dispatch_failed     NUMBER(38),
   topic               NVARCHAR2({{ nchar_maxlen }})      NOT NULL,
   qos                 INT                              NOT NULL,
   payload_type        INT                              NOT NULL,
   payload_str         NVARCHAR2({{ nchar_maxlen }}),
   payload_lob         NCLOB,
   exclude_sids        crossbar_sessionids,
   eligible_sids       crossbar_sessionids
)
NESTED TABLE exclude_sids  STORE AS event_exclude_sids
NESTED TABLE eligible_sids STORE AS event_eligible_sids
/

ALTER TABLE event ADD CONSTRAINT cstr_event_payload_type CHECK (payload_type IN (1, 2)) ENABLE
/

ALTER TABLE event ADD CONSTRAINT cstr_event_qos CHECK (qos IN (1)) ENABLE
/

ALTER TABLE event ADD CONSTRAINT cstr_event_processed_status CHECK (processed_status IN (0, 1, 2, 3, 4, 5)) ENABLE
/

ALTER TABLE event ADD CONSTRAINT cstr_event_dispatch_status CHECK (dispatch_status IN (0, 1)) ENABLE
/

CREATE INDEX idx_event1 ON event (published_by, published_at)
/

CREATE VIEW crossbar_event
AS
   SELECT * FROM event
   WHERE published_by = sys_context('USERENV', 'SESSION_USER')
/

CREATE VIEW crossbar_endpoint
AS
   SELECT * FROM endpoint
   WHERE created_by = sys_context('USERENV', 'SESSION_USER')
/

DECLARE
   l_id INTEGER;
BEGIN
   l_id := SYS.DBMS_PIPE.create_pipe('{{ pipe_onpublish }}', 256 * 1024);
   l_id := SYS.DBMS_PIPE.create_pipe('{{ pipe_onexport }}', 8 * 1024);
END;
/

CREATE PUBLIC SYNONYM crossbar_event FOR crossbar_event
/

CREATE PUBLIC SYNONYM crossbar_endpoint FOR crossbar_endpoint
/

CREATE PUBLIC SYNONYM crossbar_session FOR crossbar_session
/

CREATE PUBLIC SYNONYM crossbar_sessionids FOR crossbar_sessionids
/

CREATE PUBLIC SYNONYM crossbar_authkeys FOR crossbar_authkeys
/

GRANT SELECT ON crossbar_event TO {{ cbadapter }}
/

GRANT SELECT ON crossbar_endpoint TO {{ cbadapter }}
/

BEGIN
   INSERT INTO config (key, value) VALUES ('io.crossbar.schema.category', 'core');
   INSERT INTO config (key, value) VALUES ('io.crossbar.schema.version', '1');
   INSERT INTO config (key, value) VALUES ('io.crossbar.schema.created', TO_CHAR(sysdate(), 'YYYY-MM-DD HH24:MI:SS'));
   COMMIT;
END;
/

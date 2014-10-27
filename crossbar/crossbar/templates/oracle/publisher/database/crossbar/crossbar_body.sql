CREATE OR REPLACE PACKAGE BODY crossbar
AS
   FUNCTION dopublish(p_topic         NVARCHAR2,
                      p_payload_type  INTEGER,
                      p_payload_str   NVARCHAR2,
                      p_payload_lob   NCLOB,
                      p_exclude       crossbar_sessionids,
                      p_eligible      crossbar_sessionids,
                      p_qos           INTEGER) RETURN NUMBER
   AS
      l_now    TIMESTAMP;
      l_user   VARCHAR2(30);
      l_id     NUMBER(38);
      l_status NUMBER;
   BEGIN
      --
      -- check args
      --
      IF p_qos NOT IN (QOS_BEST_EFFORT) THEN
         RAISE_APPLICATION_ERROR(-20001, 'illegal QoS mode ' || p_qos);
      END IF;

      --
      -- event metadata
      --
      SELECT systimestamp at time zone 'utc',
             sys_context('USERENV', 'SESSION_USER'),
             event_id.nextval
         INTO
             l_now,
             l_user,
             l_id
         FROM dual;

      -- persist event
      --
      INSERT INTO event (id, published_at, published_by, topic, qos, payload_type, payload_str, payload_lob, exclude_sids, eligible_sids)
         VALUES
            (l_id, l_now, l_user, p_topic, p_qos, p_payload_type, p_payload_str, p_payload_lob, p_exclude, p_eligible);

      -- notify pipe
      --
      DBMS_PIPE.pack_message(l_id);
      l_status := DBMS_PIPE.send_message('{{ pipe_onpublish }}');

      -- commit and return event ID on success
      --
      IF l_status != 0 THEN
         ROLLBACK;
         RAISE_APPLICATION_ERROR(-20001, 'could not pipe event');
      ELSE
         COMMIT;
         RETURN l_id;
      END IF;
   END dopublish;


   FUNCTION publish(p_topic      NVARCHAR2,
                    p_exclude    crossbar_sessionids,
                    p_eligible   crossbar_sessionids,
                    p_qos        INTEGER) RETURN NUMBER
   AS
      PRAGMA AUTONOMOUS_TRANSACTION;
   BEGIN
      RETURN dopublish(p_topic, PAYLOAD_TYPE_STRING, NULL, NULL, p_exclude, p_eligible, p_qos);
   END publish;


   PROCEDURE publish(p_topic      NVARCHAR2,
                     p_exclude    crossbar_sessionids,
                     p_eligible   crossbar_sessionids,
                     p_qos        INTEGER)
   AS
      l_id     NUMBER;
   BEGIN
      l_id := publish(p_topic, p_exclude, p_eligible, p_qos);
   END publish;


   FUNCTION publish(p_topic      NVARCHAR2,
                    p_payload    NVARCHAR2,
                    p_exclude    crossbar_sessionids,
                    p_eligible   crossbar_sessionids,
                    p_qos        INTEGER) RETURN NUMBER
   AS
      PRAGMA AUTONOMOUS_TRANSACTION;
   BEGIN
      RETURN dopublish(p_topic, PAYLOAD_TYPE_STRING, p_payload, NULL, p_exclude, p_eligible, p_qos);
   END publish;


   PROCEDURE publish(p_topic      NVARCHAR2,
                     p_payload    NVARCHAR2,
                     p_exclude    crossbar_sessionids,
                     p_eligible   crossbar_sessionids,
                     p_qos        INTEGER)
   AS
      l_id     NUMBER;
   BEGIN
      l_id := publish(p_topic, p_payload, p_exclude, p_eligible, p_qos);
   END publish;


   FUNCTION publish(p_topic      NVARCHAR2,
                    p_payload    NCLOB,
                    p_exclude    crossbar_sessionids,
                    p_eligible   crossbar_sessionids,
                    p_qos        INTEGER) RETURN NUMBER
   AS
      PRAGMA AUTONOMOUS_TRANSACTION;
   BEGIN
      RETURN dopublish(p_topic, PAYLOAD_TYPE_STRING, NULL, p_payload, p_exclude, p_eligible, p_qos);
   END publish;


   PROCEDURE publish(p_topic      NVARCHAR2,
                     p_payload    NCLOB,
                     p_exclude    crossbar_sessionids,
                     p_eligible   crossbar_sessionids,
                     p_qos        INTEGER)
   AS
      l_id     NUMBER;
   BEGIN
      l_id := publish(p_topic, p_payload, p_exclude, p_eligible, p_qos);
   END publish;


   FUNCTION publish(p_topic      NVARCHAR2,
                    p_payload    JSON_VALUE,
                    p_exclude    crossbar_sessionids,
                    p_eligible   crossbar_sessionids,
                    p_qos        INTEGER) RETURN NUMBER
   AS
      PRAGMA AUTONOMOUS_TRANSACTION;

      l_id     NUMBER;
      l_lob    CLOB;
      l_str    VARCHAR2(4000);
   BEGIN
      BEGIN
         -- try serializing into VARCHAR2 with target column length limit
         --
         l_str := p_payload.to_char();
         l_id := dopublish(p_topic, PAYLOAD_TYPE_JSON, l_str, NULL, p_exclude, p_eligible, p_qos);
      EXCEPTION WHEN OTHERS THEN
         --
         -- if serialization is too long for VARCHAR2, try again using LOB
         --
         DBMS_LOB.createtemporary(lob_loc => l_lob,
                                  cache => true,
                                  dur => DBMS_LOB.call);
         p_payload.to_clob(l_lob);
         l_id := dopublish(p_topic, PAYLOAD_TYPE_JSON, NULL, l_lob, p_exclude, p_eligible, p_qos);
         DBMS_LOB.freetemporary(l_lob);
      END;
      RETURN l_id;
   END publish;


   PROCEDURE publish(p_topic      NVARCHAR2,
                     p_payload    JSON_VALUE,
                     p_exclude    crossbar_sessionids,
                     p_eligible   crossbar_sessionids,
                     p_qos        INTEGER)
   AS
      l_id     NUMBER;
   BEGIN
      l_id := publish(p_topic, p_payload, p_exclude, p_eligible, p_qos);
   END publish;


   FUNCTION publish(p_topic      NVARCHAR2,
                    p_payload    JSON,
                    p_exclude    crossbar_sessionids,
                    p_eligible   crossbar_sessionids,
                    p_qos        INTEGER) RETURN NUMBER
   AS
      PRAGMA AUTONOMOUS_TRANSACTION;

      l_id     NUMBER;
      l_lob    CLOB;
      l_str    VARCHAR2(4000);
   BEGIN
      BEGIN
         -- try serializing into VARCHAR2 with target column length limit
         --
         l_str := p_payload.to_char();
         l_id := dopublish(p_topic, PAYLOAD_TYPE_JSON, l_str, NULL, p_exclude, p_eligible, p_qos);
      EXCEPTION WHEN OTHERS THEN
         --
         -- if serialization is too long for VARCHAR2, try again using LOB
         --
         DBMS_LOB.createtemporary(lob_loc => l_lob,
                                  cache => true,
                                  dur => DBMS_LOB.call);
         p_payload.to_clob(l_lob);
         l_id := dopublish(p_topic, PAYLOAD_TYPE_JSON, NULL, l_lob, p_exclude, p_eligible, p_qos);
         DBMS_LOB.freetemporary(l_lob);
      END;
      RETURN l_id;
   END publish;


   PROCEDURE publish(p_topic      NVARCHAR2,
                     p_payload    JSON,
                     p_exclude    crossbar_sessionids,
                     p_eligible   crossbar_sessionids,
                     p_qos        INTEGER)
   AS
      l_id     NUMBER;
   BEGIN
      l_id := publish(p_topic, p_payload, p_exclude, p_eligible, p_qos);
   END publish;


   FUNCTION publish(p_topic      NVARCHAR2,
                    p_payload    JSON_LIST,
                    p_exclude    crossbar_sessionids,
                    p_eligible   crossbar_sessionids,
                    p_qos        INTEGER) RETURN NUMBER
   AS
      PRAGMA AUTONOMOUS_TRANSACTION;

      l_id     NUMBER;
      l_lob    CLOB;
      l_str    VARCHAR2(4000);
   BEGIN
      BEGIN
         -- try serializing into VARCHAR2 with target column length limit
         --
         l_str := p_payload.to_char();
         l_id := dopublish(p_topic, PAYLOAD_TYPE_JSON, l_str, NULL, p_exclude, p_eligible, p_qos);
      EXCEPTION WHEN OTHERS THEN
         --
         -- if serialization is too long for VARCHAR2, try again using LOB
         --
         DBMS_LOB.createtemporary(lob_loc => l_lob,
                                  cache => true,
                                  dur => DBMS_LOB.call);
         p_payload.to_clob(l_lob);
         l_id := dopublish(p_topic, PAYLOAD_TYPE_JSON, NULL, l_lob, p_exclude, p_eligible, p_qos);
         DBMS_LOB.freetemporary(l_lob);
      END;
      RETURN l_id;
   END publish;


   PROCEDURE publish(p_topic      NVARCHAR2,
                     p_payload    JSON_LIST,
                     p_exclude    crossbar_sessionids,
                     p_eligible   crossbar_sessionids,
                     p_qos        INTEGER)
   AS
      l_id     NUMBER;
   BEGIN
      l_id := publish(p_topic, p_payload, p_exclude, p_eligible, p_qos);
   END publish;


   PROCEDURE remove_export(p_endpoint_id   IN NUMBER)
   AS
      PRAGMA AUTONOMOUS_TRANSACTION;

      l_now              TIMESTAMP;
      l_created_by       VARCHAR2(30);
      l_user             VARCHAR2(30);
      l_id               NUMBER(38);
      l_status           NUMBER;
   BEGIN
      --
      -- get current time / user
      --
      SELECT systimestamp at time zone 'utc',
             sys_context('USERENV', 'SESSION_USER')
         INTO
             l_now,
             l_user
         FROM dual;

      BEGIN
         SELECT created_by INTO l_created_by FROM endpoint WHERE id = p_endpoint_id;
      EXCEPTION WHEN NO_DATA_FOUND THEN
         RAISE_APPLICATION_ERROR(-20001, 'no endpoint with ID ' || p_endpoint_id);
      END;

      IF l_created_by != l_user THEN
         RAISE_APPLICATION_ERROR(-20001, 'not allowed to delete export with ID ' || p_endpoint_id || ' (not owner)');
      END IF;

      DELETE FROM endpoint WHERE id = p_endpoint_id;
      COMMIT;

      -- notify pipe
      --
      DBMS_PIPE.pack_message(p_endpoint_id);
      l_status := DBMS_PIPE.send_message('{{ pipe_onexport }}');

   END remove_export;


   FUNCTION remove_exports(p_schema    IN VARCHAR2,
                           p_package   IN VARCHAR2,
                           p_proc      IN VARCHAR2) RETURN NUMBER
   AS
      PRAGMA AUTONOMOUS_TRANSACTION;

      l_cnt              NUMBER;
      l_now              TIMESTAMP;
      l_created_by       VARCHAR2(30);
      l_user             VARCHAR2(30);
      l_id               NUMBER(38);
      l_status           NUMBER;

      l_schema           VARCHAR2(30);
      l_package          VARCHAR2(30);
      l_proc             VARCHAR2(30);
   BEGIN
      --
      -- determine schema of remoted package procedure
      --
      IF p_schema IS NOT NULL THEN
         l_schema := UPPER(SUBSTR(p_schema, 1, 30));
      ELSE
         l_schema := sys_context('USERENV', 'SESSION_USER');
      END IF;

      IF p_package IS NOT NULL THEN
         l_package := UPPER(SUBSTR(p_package, 1, 30));
      ELSE
         l_package := NULL;
      END IF;

      IF p_proc IS NOT NULL THEN
         l_proc := UPPER(SUBSTR(p_proc, 1, 30));
      ELSE
         l_proc := NULL;
      END IF;

      --
      -- get current time / user
      --
      SELECT systimestamp at time zone 'utc',
             sys_context('USERENV', 'SESSION_USER')
         INTO
             l_now,
             l_user
         FROM dual;

      SELECT COUNT(*) INTO l_cnt FROM endpoint e
         WHERE
            schema = l_schema AND
            package = NVL(l_package, e.package) AND
            procedure = NVL(l_proc, e.procedure) AND
            created_by != l_user;

      IF l_cnt > 0 THEN
         RAISE_APPLICATION_ERROR(-20001, 'cannot delete exports - ' || l_cnt || ' exported endpoint(s) not owned by current user');
      END IF;

      l_cnt := 0;
      FOR r IN (SELECT id FROM endpoint e
                   WHERE
                      schema = l_schema AND
                      package = NVL(l_package, e.package) AND
                      procedure = NVL(l_proc, e.procedure) AND
                      created_by = l_user)
      LOOP
         DELETE FROM endpoint WHERE id = r.id;
         COMMIT;
         DBMS_PIPE.pack_message(r.id);
         l_status := DBMS_PIPE.send_message('{{ pipe_onexport }}');
         l_cnt := l_cnt + 1;
      END LOOP;

      RETURN l_cnt;

   END remove_exports;


   PROCEDURE remove_exports(p_schema    IN VARCHAR2,
                            p_package   IN VARCHAR2,
                            p_proc      IN VARCHAR2)
   IS
      l_cnt       NUMBER;
   BEGIN
      l_cnt := remove_exports(p_schema, p_package, p_proc);
   END remove_exports;


   PROCEDURE remove_exports(p_package   IN VARCHAR2,
                            p_proc      IN VARCHAR2)
   IS
      l_cnt       NUMBER;
   BEGIN
      l_cnt := remove_exports(NULL, p_package, p_proc);
   END remove_exports;


   FUNCTION remove_exports_by_uri(p_uri_pattern   IN NVARCHAR2) RETURN NUMBER
   AS
      PRAGMA AUTONOMOUS_TRANSACTION;

      l_cnt              NUMBER;
      l_now              TIMESTAMP;
      l_created_by       VARCHAR2(30);
      l_user             VARCHAR2(30);
      l_id               NUMBER(38);
      l_status           NUMBER;
   BEGIN
      --
      -- get current time / user
      --
      SELECT systimestamp at time zone 'utc',
             sys_context('USERENV', 'SESSION_USER')
         INTO
             l_now,
             l_user
         FROM dual;

      SELECT COUNT(*) INTO l_cnt FROM endpoint WHERE uri LIKE p_uri_pattern AND created_by != l_user;
      IF l_cnt > 0 THEN
         RAISE_APPLICATION_ERROR(-20001, 'cannot delete exports - ' || l_cnt || ' exported endpoint(s) not owned by current user');
      END IF;

      l_cnt := 0;
      FOR r IN (SELECT id FROM endpoint WHERE uri LIKE p_uri_pattern AND created_by = l_user)
      LOOP
         DELETE FROM endpoint WHERE id = r.id;
         COMMIT;
         DBMS_PIPE.pack_message(r.id);
         l_status := DBMS_PIPE.send_message('{{ pipe_onexport }}');
         l_cnt := l_cnt + 1;
      END LOOP;

      RETURN l_cnt;

   END remove_exports_by_uri;


   PROCEDURE remove_exports_by_uri(p_uri_pattern   IN NVARCHAR2)
   IS
      l_cnt       NUMBER;
   BEGIN
      l_cnt := remove_exports_by_uri(p_uri_pattern);
   END remove_exports_by_uri;


   FUNCTION export (p_schema      VARCHAR2,
                    p_package     VARCHAR2,
                    p_proc        VARCHAR2,
                    p_endpoint    NVARCHAR2,
                    p_authkeys    crossbar_authkeys) RETURN NUMBER
   AS
      PRAGMA AUTONOMOUS_TRANSACTION;

      l_isnew            BOOLEAN := TRUE;
      l_now              TIMESTAMP;
      l_created_by       VARCHAR2(30);
      l_authkeys         crossbar_authkeys;
      l_user             VARCHAR2(30);
      l_id               NUMBER(38);
      l_object_id        NUMBER;
      l_subprogram_id    NUMBER;
      l_overload_cnt     NUMBER;
      l_sessobj_cnt      NUMBER;
      l_status           NUMBER;
      l_schema           VARCHAR2(30);
      l_package          VARCHAR2(30) := UPPER(p_package);
      l_proc             VARCHAR2(30) := UPPER(p_proc);

      -- existing metadata (for updating)
      l_cur_return_type  VARCHAR2(30);
      l_cur_args_cnt     NUMBER;
      l_cur_arg_types    t_arg_types;
      l_cur_arg_inouts   t_arg_inouts;

      -- new metadata
      l_return_type      VARCHAR2(30) := NULL;
      l_args_cnt         NUMBER := 0;
      l_arg_types        t_arg_types := t_arg_types();
      l_arg_inouts       t_arg_inouts := t_arg_inouts();
      l_data_type        VARCHAR2(30);
   BEGIN
      --
      -- determine schema of remoted package procedure
      --
      IF p_schema IS NULL THEN
         l_schema := sys_context('USERENV', 'SESSION_USER');
      ELSE
         l_schema := UPPER(p_schema);
      END IF;

      --
      -- get current time / user
      --
      SELECT systimestamp at time zone 'utc',
             sys_context('USERENV', 'SESSION_USER')
         INTO
             l_now,
             l_user
         FROM dual;

      --
      -- check if package exists and if we have execute grants on it
      --
      BEGIN
         SELECT object_id INTO l_object_id FROM all_procedures
            WHERE owner = l_schema AND object_name = l_package AND object_type = 'PACKAGE' AND subprogram_id = 0;
      EXCEPTION WHEN NO_DATA_FOUND THEN
         RAISE_APPLICATION_ERROR(-20001, 'no package ' || l_schema || '.' || l_package || ' or no execute grant on package');
      END;

      --
      -- check if package procedure/function exists
      --
      BEGIN
         SELECT MAX(subprogram_id), COUNT(*) INTO l_subprogram_id, l_overload_cnt FROM all_procedures
            WHERE owner = l_schema AND object_name = l_package AND procedure_name = l_proc AND object_type = 'PACKAGE' AND subprogram_id > 0
            GROUP BY owner, object_name, procedure_name;
      EXCEPTION WHEN NO_DATA_FOUND THEN
         RAISE_APPLICATION_ERROR(-20001, 'no procedure or function ' || l_schema || '.' || l_package || '.' || l_proc);
      END;

      --
      -- check for overloaded SP
      --
      IF l_overload_cnt > 1 THEN
         RAISE_APPLICATION_ERROR(-20001, 'procedure or function ' || l_schema || '.' || l_package || '.' || l_proc || ' is overloaded [' || l_overload_cnt || ' overloads]');
      END IF;

      --
      -- check for SP with multiple session object parameters
      --
      SELECT COUNT(*) INTO l_sessobj_cnt
        FROM all_arguments
       WHERE     object_id = l_object_id
             AND subprogram_id = l_subprogram_id
             AND data_type = 'OBJECT'
             AND type_owner = 'PUBLIC'
             AND type_name = 'CROSSBAR_SESSION';
      IF l_sessobj_cnt > 1 THEN
         RAISE_APPLICATION_ERROR(-20001, 'procedure or function ' || l_schema || '.' || l_package || '.' || l_proc || ' uses more than 1 session object parameter [' || l_sessobj_cnt || ' session object parameters]');
      END IF;

      --
      -- check SP arguments
      --
      FOR r IN (SELECT position,
                       argument_name,
                       data_type,
                       type_owner,
                       type_name,
                       defaulted,
                       in_out FROM all_arguments
                 WHERE object_id = l_object_id AND
                       subprogram_id = l_subprogram_id
              ORDER BY position ASC)
      LOOP
         --
         -- check for stuff we (currently) don't supports
         --
         IF r.position = 0 AND r.in_out != 'OUT' THEN
            -- should not happen anyway (it seems that functions are the only items having arg (= return value) in position 0)
            RAISE_APPLICATION_ERROR(-20001, 'procedure or function ' || l_schema || '.' || l_package || '.' || l_proc || ' uses IN/INOUT parameter in position 0');
         END IF;
         IF r.position > 0 AND r.in_out != 'IN' THEN
            IF r.data_type = 'OBJECT' AND r.type_owner = 'PUBLIC' AND r.type_name = 'CROSSBAR_SESSION' THEN
               -- session info is the only parameter type allowed to be IN or IN/OUT (but not OUT)
               IF r.in_out NOT IN ('IN', 'IN/OUT') THEN
                  RAISE_APPLICATION_ERROR(-20001, 'procedure or function ' || l_schema || '.' || l_package || '.' || l_proc || ' uses session object parameter of OUT (only IN or IN/OUT allowed)');
               END IF;
            ELSE
               RAISE_APPLICATION_ERROR(-20001, 'procedure or function ' || l_schema || '.' || l_package || '.' || l_proc || ' uses OUT/INOUT parameters');
            END IF;
         END IF;
         IF r.defaulted != 'N' THEN
            RAISE_APPLICATION_ERROR(-20001, 'procedure or function ' || l_schema || '.' || l_package || '.' || l_proc || ' uses parameters defaults');
         END IF;
         IF r.position = 0 AND
            r.data_type != 'NUMBER' AND
            r.data_type != 'VARCHAR2' AND
            r.data_type != 'NVARCHAR2' AND
            r.data_type != 'CHAR' AND
            r.data_type != 'NCHAR' AND
            r.data_type != 'BINARY_FLOAT' AND
            r.data_type != 'BINARY_DOUBLE' AND
            r.data_type != 'DATE' AND
            r.data_type != 'TIMESTAMP' AND
            r.data_type != 'TIMESTAMP WITH TIME ZONE' AND
            r.data_type != 'TIMESTAMP WITH LOCAL TIME ZONE' AND
            r.data_type != 'INTERVAL DAY TO SECOND' AND
            --r.data_type != 'INTERVAL YEAR TO MONTH' AND
            NOT (r.data_type = 'OBJECT' AND r.type_owner = 'PUBLIC' AND r.type_name IN ('JSON', 'JSON_VALUE', 'JSON_LIST')) AND
            r.data_type != 'REF CURSOR'
            THEN
            RAISE_APPLICATION_ERROR(-20001, 'procedure or function ' || l_schema || '.' || l_package || '.' || l_proc || ' uses unsupported return type');
         END IF;
         IF r.position > 0 AND
            r.data_type != 'NUMBER' AND
            r.data_type != 'VARCHAR2' AND
            r.data_type != 'NVARCHAR2' AND
            r.data_type != 'CHAR' AND
            r.data_type != 'NCHAR' AND
            r.data_type != 'BINARY_FLOAT' AND
            r.data_type != 'BINARY_DOUBLE' AND
            r.data_type != 'DATE' AND
            r.data_type != 'TIMESTAMP' AND
            r.data_type != 'TIMESTAMP WITH TIME ZONE' AND
            r.data_type != 'TIMESTAMP WITH LOCAL TIME ZONE' AND
            r.data_type != 'INTERVAL DAY TO SECOND' AND
            --r.data_type != 'INTERVAL YEAR TO MONTH' AND
            NOT (r.data_type = 'OBJECT' AND r.type_owner = 'PUBLIC' AND r.type_name IN ('CROSSBAR_SESSION', 'JSON', 'JSON_VALUE', 'JSON_LIST'))
            THEN
            RAISE_APPLICATION_ERROR(-20001, 'procedure or function ' || l_schema || '.' || l_package || '.' || l_proc || ' uses unsupported parameter type');
         END IF;

         --
         -- remember return type (if a function) and number of (IN) args
         --
         IF r.data_type = 'OBJECT' AND r.type_owner = 'PUBLIC' AND r.type_name IN ('CROSSBAR_SESSION', 'JSON', 'JSON_VALUE', 'JSON_LIST') THEN
            l_data_type := r.type_name;
         ELSE
            l_data_type := r.data_type;
         END IF;

         --
         -- remember arg types
         --
         IF r.position = 0 THEN
            l_return_type := l_data_type;
         ELSE
            -- don't count injected args
            --
            IF NOT (r.data_type = 'OBJECT' AND r.type_owner = 'PUBLIC' AND r.type_name IN ('CROSSBAR_SESSION')) THEN
               l_args_cnt := l_args_cnt + 1;
            END IF;

            IF l_data_type IS NOT NULL THEN
               l_arg_types.extend(1);
               l_arg_types(l_arg_types.last) := l_data_type;
               l_arg_inouts.extend(1);
               l_arg_inouts(l_arg_inouts.last) := r.in_out;
            END IF;
         END IF;
      END LOOP;

      BEGIN
         SELECT id, created_by, authkeys, return_type, args_cnt, arg_types, arg_inouts INTO l_id, l_created_by, l_authkeys, l_cur_return_type, l_cur_args_cnt, l_cur_arg_types, l_cur_arg_inouts FROM endpoint
            WHERE schema = l_schema AND package = l_package AND procedure = l_proc AND uri = p_endpoint;

         IF l_created_by != l_user THEN
            RAISE_APPLICATION_ERROR(-20001, 'endpoint already exists, but was created by different user: not allowed to modify endpoint');
         END IF;

         l_isnew := FALSE;

         IF l_authkeys != p_authkeys OR
            (l_authkeys IS NULL     AND p_authkeys IS NOT NULL) OR
            (l_authkeys IS NOT NULL AND p_authkeys IS NULL) OR
            l_cur_return_type != l_return_type OR
            (l_cur_return_type IS NULL     AND l_return_type IS NOT NULL) OR
            (l_cur_return_type IS NOT NULL AND l_return_type IS NULL) OR
            l_cur_args_cnt != l_args_cnt OR
            l_arg_types != l_cur_arg_types OR
            (l_arg_types IS NULL     AND l_cur_arg_types IS NOT NULL) OR
            (l_arg_types IS NOT NULL AND l_cur_arg_types IS NULL) OR
            l_arg_inouts != l_cur_arg_inouts OR
            (l_arg_inouts IS NULL     AND l_cur_arg_inouts IS NOT NULL) OR
            (l_arg_inouts IS NOT NULL AND l_cur_arg_inouts IS NULL)
            THEN

            UPDATE endpoint
               SET
                  modified_at = l_now,
                  authkeys    = p_authkeys,
                  return_type = l_return_type,
                  args_cnt    = l_args_cnt,
                  arg_types   = l_arg_types,
                  arg_inouts  = l_arg_inouts
               WHERE
                  id = l_id;
            COMMIT;

            -- notify via pipe
            --
            --DBMS_PIPE.pack_message(l_id);
            --l_status := DBMS_PIPE.send_message('{{ pipe_onexport }}');
         END IF;

      EXCEPTION WHEN NO_DATA_FOUND THEN

         SELECT endpoint_id.nextval INTO l_id FROM dual;

         INSERT INTO endpoint
            (id, created_at, created_by, schema, package, procedure, object_id, subprogram_id, return_type, args_cnt, arg_types, arg_inouts, uri, authkeys) VALUES
               (l_id, l_now, l_user, l_schema, l_package, l_proc, l_object_id, l_subprogram_id, l_return_type, l_args_cnt, l_arg_types, l_arg_inouts, p_endpoint, p_authkeys);
         COMMIT;

         -- notify via pipe
         --
         --DBMS_PIPE.pack_message(l_id);
         --l_status := DBMS_PIPE.send_message('{{ pipe_onexport }}');
      END;

      RETURN l_id;

   END export;


   PROCEDURE export(p_package   IN VARCHAR2,
                    p_proc      IN VARCHAR2,
                    p_endpoint  IN NVARCHAR2,
                    p_authkeys  IN crossbar_authkeys      DEFAULT NULL)
   IS
      l_id   NUMBER;
   BEGIN
      l_id := export(NULL, p_package, p_proc, p_endpoint, p_authkeys);
   END export;


   PROCEDURE raise (p_uri VARCHAR2, p_desc VARCHAR2, p_kill_session BOOLEAN)
   IS
      l_obj    JSON := JSON();
   BEGIN
      l_obj.put('uri', p_uri);
      l_obj.put('desc', p_desc);
      l_obj.put('kill', p_kill_session);
      l_obj.put('callstack', DBMS_UTILITY.FORMAT_CALL_STACK);
      --l_obj.put('backtrace', DBMS_UTILITY.FORMAT_ERROR_BACKTRACE);
      --l_obj.put('errorstack', DBMS_UTILITY.FORMAT_ERROR_STACK);
      RAISE_APPLICATION_ERROR(-20999, l_obj.to_char(false));
   END raise;


   PROCEDURE raise (p_uri VARCHAR2, p_desc VARCHAR2, p_detail JSON_VALUE, p_kill_session BOOLEAN)
   IS
      l_obj    JSON := JSON();
   BEGIN
      l_obj.put('uri', p_uri);
      l_obj.put('desc', p_desc);
      IF p_detail IS NOT NULL THEN
         l_obj.put('detail', p_detail);
      END IF;
      l_obj.put('kill', p_kill_session);
      l_obj.put('callstack', DBMS_UTILITY.FORMAT_CALL_STACK);
      --l_obj.put('backtrace', DBMS_UTILITY.FORMAT_ERROR_BACKTRACE);
      --l_obj.put('errorstack', DBMS_UTILITY.FORMAT_ERROR_STACK);
      RAISE_APPLICATION_ERROR(-20999, l_obj.to_char(false));
   END raise;


   PROCEDURE raise (p_uri VARCHAR2, p_desc VARCHAR2, p_detail JSON, p_kill_session BOOLEAN)
   IS
      l_obj    JSON := JSON();
   BEGIN
      l_obj.put('uri', p_uri);
      l_obj.put('desc', p_desc);
      IF p_detail IS NOT NULL THEN
         l_obj.put('detail', p_detail);
      END IF;
      l_obj.put('kill', p_kill_session);
      l_obj.put('callstack', DBMS_UTILITY.FORMAT_CALL_STACK);
      --l_obj.put('backtrace', DBMS_UTILITY.FORMAT_ERROR_BACKTRACE);
      --l_obj.put('errorstack', DBMS_UTILITY.FORMAT_ERROR_STACK);
      RAISE_APPLICATION_ERROR(-20999, l_obj.to_char(false));
   END raise;


   PROCEDURE raise (p_uri VARCHAR2, p_desc VARCHAR2, p_detail JSON_LIST, p_kill_session BOOLEAN)
   IS
      l_obj    JSON := JSON();
   BEGIN
      l_obj.put('uri', p_uri);
      l_obj.put('desc', p_desc);
      IF p_detail IS NOT NULL THEN
         l_obj.put('detail', p_detail);
      END IF;
      l_obj.put('kill', p_kill_session);
      l_obj.put('callstack', DBMS_UTILITY.FORMAT_CALL_STACK);
      --l_obj.put('backtrace', DBMS_UTILITY.FORMAT_ERROR_BACKTRACE);
      --l_obj.put('errorstack', DBMS_UTILITY.FORMAT_ERROR_STACK);
      RAISE_APPLICATION_ERROR(-20999, l_obj.to_char(false));
   END raise;

END crossbar;
/

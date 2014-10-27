CREATE OR REPLACE PACKAGE BODY crossbar
AS

   /**
    * Event delivery quality-of-service is "best-effort".
    *
    * Any subscriber currently subscribed on the topic the event was
    * published to SHOULD receive the event once. However, there is
    * no strict guarantee for this to happen: the event may be delivered
    * once, more than once, or get lost completely.
    */
   QOS_BEST_EFFORT       CONSTANT INTEGER := 1;


   /**
    * Event payload type is plain string.
    */
   PAYLOAD_TYPE_STRING   CONSTANT INTEGER := 1;

   /**
    * Event payload type is JSON.
    */
   PAYLOAD_TYPE_JSON     CONSTANT INTEGER := 2;

   /**
    * crossbar.io repository user.
    */
   REPOUSER              CONSTANT VARCHAR2(30) := sys_context('USERENV', 'CURRENT_SCHEMA');


   FUNCTION publish(p_uri        IN NVARCHAR2,
                    p_args       IN json_list,
                    p_kwargs     IN json,
                    p_exclude    IN crossbar_sessionids,
                    p_eligible   IN crossbar_sessionids) RETURN INTEGER
   AS
      PRAGMA AUTONOMOUS_TRANSACTION;

      l_id           NUMBER;
      l_status       NUMBER;

      l_now          TIMESTAMP;
      l_user         VARCHAR2(30);

      l_payload      json;
      l_payload_str  VARCHAR2(32767);
      l_payload_lob  CLOB;
   BEGIN
      --
      -- check args
      --
/*      
      IF p_qos NOT IN (QOS_BEST_EFFORT) THEN
         RAISE_APPLICATION_ERROR(-20001, 'illegal QoS mode ' || p_qos);
      END IF;
*/
      l_payload := json();
      l_payload.put('topic', p_uri);

      IF p_args IS NOT NULL THEN
         l_payload.put('args', p_args);
      END IF;

      IF p_kwargs IS NOT NULL THEN
         l_payload.put('kwargs', p_kwargs);
      END IF;

      -- FIXME: p_exclude, p_eligible

      BEGIN
         -- try serializing into VARCHAR2 with target column length limit
         --
         l_payload_str := l_payload.to_char();
         l_id := 0;

         -- notify pipe
         --
         DBMS_PIPE.pack_message(l_id);
         DBMS_PIPE.pack_message(l_payload_str);
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

      EXCEPTION
         WHEN OTHERS THEN

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

            --
            -- if serialization is too long for VARCHAR2, try again using LOB
            --
            DBMS_LOB.createtemporary(lob_loc => l_payload_lob,
                                     cache => true,
                                     dur => DBMS_LOB.call);
            l_payload.to_clob(l_payload_lob);

            -- persist event
            --
            INSERT INTO event (id, published_at, published_by, topic, qos, payload_type, payload_str, payload_lob, exclude_sids, eligible_sids)
               VALUES
                  (l_id, l_now, l_user, p_uri, crossbar.QOS_BEST_EFFORT, crossbar.PAYLOAD_TYPE_JSON, NULL, l_payload_lob, p_exclude, p_eligible);

            DBMS_LOB.freetemporary(l_payload_lob);

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

      END;

   END publish;


   FUNCTION register(p_schema    IN VARCHAR2,
                     p_package   IN VARCHAR2,
                     p_proc      IN VARCHAR2,
                     p_uri       IN NVARCHAR2) RETURN INTEGER
   IS
   BEGIN
      RETURN 0;
   END register;


   PROCEDURE unregister(p_registration IN INTEGER)
   IS
   BEGIN
      NULL;
   END unregister;


   FUNCTION subscribe(p_schema    IN VARCHAR2,
                      p_package   IN VARCHAR2,
                      p_proc      IN VARCHAR2,
                      p_uri       IN NVARCHAR2) RETURN INTEGER
   IS
   BEGIN
      RETURN 0;
   END subscribe;

   PROCEDURE unsubscribe(p_subscription IN INTEGER)
   IS
   BEGIN
      NULL;
   END unsubscribe;

END crossbar;
/

CREATE OR REPLACE PACKAGE crossbar
AS
   /**
    * Crossbar.io Oracle PL/SQL API.
    *
    * Copyright (C) 2011-2014 Tavendo GmbH.
    * Licensed under Apache 2.0 license (http://www.apache.org/licenses/LICENSE-2.0.html)
    *
    * Publish and Subscribe:
    *
    *   The package provides functions to publish events to crossbar.io from within
    *   Oracle which are dispatched to any clients subscribed and authorized
    *   to receive events on the respective topic.
    *
    * Remote Procedure Calls:
    *
    *   The package provides functions to export Oracle stored procedures which
    *   then can be called by clients authorized to do so. crossbar.io will forward
    *   client calls to stored procedure invocations.
    */

   /**
    * Event payload type is plain string.
    */
   PAYLOAD_TYPE_STRING   CONSTANT INTEGER := 1;

   /**
    * Event payload type is JSON.
    */
   PAYLOAD_TYPE_JSON     CONSTANT INTEGER := 2;

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
    * crossbar.io repository user.
    */
   REPOUSER              CONSTANT VARCHAR2(30) := sys_context('USERENV', 'CURRENT_SCHEMA');


   /**
    * Publish event without payload to topic.
    *
    * @param p_topic           URI of topic to publish to.
    * @param p_exclude         If present, exclude this list of WAMP session IDs from receivers.
    * @param p_eligible        If present, only this list of WAMP session IDs is eligible for receiving.
    * @param p_qos             Quality-of-Service for event delivery.
    * @return                  Event ID.
    */
   FUNCTION publish(p_topic     IN NVARCHAR2,
                    p_exclude   IN crossbar_sessionids   DEFAULT NULL,
                    p_eligible  IN crossbar_sessionids   DEFAULT NULL,
                    p_qos       IN INTEGER            DEFAULT QOS_BEST_EFFORT) RETURN NUMBER;

   /**
    * Publish event without payload to topic.
    *
    * @param p_topic           URI of topic to publish to.
    * @param p_exclude         If present, exclude this list of WAMP session IDs from receivers.
    * @param p_eligible        If present, only this list of WAMP session IDs is eligible for receiving.
    * @param p_qos             Quality-of-Service for event delivery.
    */
   PROCEDURE publish(p_topic     IN NVARCHAR2,
                     p_exclude   IN crossbar_sessionids   DEFAULT NULL,
                     p_eligible  IN crossbar_sessionids   DEFAULT NULL,
                     p_qos       IN INTEGER            DEFAULT QOS_BEST_EFFORT);

   /**
    * Publish event with plain string payload to topic.
    *
    * @param p_topic           URI of topic to publish to.
    * @param p_payload         Event payload.
    * @param p_exclude         If present, exclude this list of WAMP session IDs from receivers.
    * @param p_eligible        If present, only this list of WAMP session IDs is eligible for receiving.
    * @param p_qos             Quality-of-Service for event delivery.
    * @return                  Event ID.
    */
   FUNCTION publish(p_topic     IN NVARCHAR2,
                    p_payload   IN NVARCHAR2,
                    p_exclude   IN crossbar_sessionids   DEFAULT NULL,
                    p_eligible  IN crossbar_sessionids   DEFAULT NULL,
                    p_qos       IN INTEGER            DEFAULT QOS_BEST_EFFORT) RETURN NUMBER;

   /**
    * Publish event with plain string payload to topic.
    *
    * @param p_topic           URI of topic to publish to.
    * @param p_payload         Event payload.
    * @param p_exclude         If present, exclude this list of WAMP session IDs from receivers.
    * @param p_eligible        If present, only this list of WAMP session IDs is eligible for receiving.
    * @param p_qos             Quality-of-Service for event delivery.
    */
   PROCEDURE publish(p_topic     IN NVARCHAR2,
                     p_payload   IN NVARCHAR2,
                     p_exclude   IN crossbar_sessionids   DEFAULT NULL,
                     p_eligible  IN crossbar_sessionids   DEFAULT NULL,
                     p_qos       IN INTEGER            DEFAULT QOS_BEST_EFFORT);

   /**
    * Publish event with large string payload to topic.
    *
    * @param p_topic           URI of topic to publish to.
    * @param p_payload         Event payload.
    * @param p_exclude         If present, exclude this list of WAMP session IDs from receivers.
    * @param p_eligible        If present, only this list of WAMP session IDs is eligible for receiving.
    * @param p_qos             Quality-of-Service for event delivery.
    * @return                  Event ID.
    */
   FUNCTION publish(p_topic     IN NVARCHAR2,
                    p_payload   IN NCLOB,
                    p_exclude   IN crossbar_sessionids   DEFAULT NULL,
                    p_eligible  IN crossbar_sessionids   DEFAULT NULL,
                    p_qos       IN INTEGER            DEFAULT QOS_BEST_EFFORT) RETURN NUMBER;

   /**
    * Publish event with large string payload to topic.
    *
    * @param p_topic           URI of topic to publish to.
    * @param p_payload         Event payload.
    * @param p_exclude         If present, exclude this list of WAMP session IDs from receivers.
    * @param p_eligible        If present, only this list of WAMP session IDs is eligible for receiving.
    * @param p_qos             Quality-of-Service for event delivery.
    */
   PROCEDURE publish(p_topic     IN NVARCHAR2,
                     p_payload   IN NCLOB,
                     p_exclude   IN crossbar_sessionids   DEFAULT NULL,
                     p_eligible  IN crossbar_sessionids   DEFAULT NULL,
                     p_qos       IN INTEGER            DEFAULT QOS_BEST_EFFORT);

   /**
    * Publish event with JSON (value) payload to topic.
    *
    * @param p_topic           URI of topic to publish to.
    * @param p_payload         Event payload.
    * @param p_exclude         If present, exclude this list of WAMP session IDs from receivers.
    * @param p_eligible        If present, only this list of WAMP session IDs is eligible for receiving.
    * @param p_qos             Quality-of-Service for event delivery.
    * @return                  Event ID.
    */
   FUNCTION publish(p_topic     IN NVARCHAR2,
                    p_payload   IN JSON_VALUE,
                    p_exclude   IN crossbar_sessionids   DEFAULT NULL,
                    p_eligible  IN crossbar_sessionids   DEFAULT NULL,
                    p_qos       IN INTEGER            DEFAULT QOS_BEST_EFFORT) RETURN NUMBER;

   /**
    * Publish event with JSON (value) payload to topic.
    *
    * @param p_topic           URI of topic to publish to.
    * @param p_payload         Event payload.
    * @param p_exclude         If present, exclude this list of WAMP session IDs from receivers.
    * @param p_eligible        If present, only this list of WAMP session IDs is eligible for receiving.
    * @param p_qos             Quality-of-Service for event delivery.
    */
   PROCEDURE publish(p_topic     IN NVARCHAR2,
                     p_payload   IN JSON_VALUE,
                     p_exclude   IN crossbar_sessionids   DEFAULT NULL,
                     p_eligible  IN crossbar_sessionids   DEFAULT NULL,
                     p_qos       IN INTEGER            DEFAULT QOS_BEST_EFFORT);

   /**
    * Publish event with JSON (object) payload to topic.
    *
    * @param p_topic           URI of topic to publish to.
    * @param p_payload         Event payload.
    * @param p_exclude         If present, exclude this list of WAMP session IDs from receivers.
    * @param p_eligible        If present, only this list of WAMP session IDs is eligible for receiving.
    * @param p_qos             Quality-of-Service for event delivery.
    * @return                  Event ID.
    */
   FUNCTION publish(p_topic     IN NVARCHAR2,
                    p_payload   IN JSON,
                    p_exclude   IN crossbar_sessionids   DEFAULT NULL,
                    p_eligible  IN crossbar_sessionids   DEFAULT NULL,
                    p_qos       IN INTEGER            DEFAULT QOS_BEST_EFFORT) RETURN NUMBER;

   /**
    * Publish event with JSON (object) payload to topic.
    *
    * @param p_topic           URI of topic to publish to.
    * @param p_payload         Event payload.
    * @param p_exclude         If present, exclude this list of WAMP session IDs from receivers.
    * @param p_eligible        If present, only this list of WAMP session IDs is eligible for receiving.
    * @param p_qos             Quality-of-Service for event delivery.
    */
   PROCEDURE publish(p_topic     IN NVARCHAR2,
                     p_payload   IN JSON,
                     p_exclude   IN crossbar_sessionids   DEFAULT NULL,
                     p_eligible  IN crossbar_sessionids   DEFAULT NULL,
                     p_qos       IN INTEGER            DEFAULT QOS_BEST_EFFORT);

   /**
    * Publish event with JSON (list) payload to topic.
    *
    * @param p_topic           URI of topic to publish to.
    * @param p_payload         Event payload.
    * @param p_exclude         If present, exclude this list of WAMP session IDs from receivers.
    * @param p_eligible        If present, only this list of WAMP session IDs is eligible for receiving.
    * @param p_qos             Quality-of-Service for event delivery.
    * @return                  Event ID.
    */
   FUNCTION publish(p_topic     IN NVARCHAR2,
                    p_payload   IN JSON_LIST,
                    p_exclude   IN crossbar_sessionids   DEFAULT NULL,
                    p_eligible  IN crossbar_sessionids   DEFAULT NULL,
                    p_qos       IN INTEGER            DEFAULT QOS_BEST_EFFORT) RETURN NUMBER;

   /**
    * Publish event with JSON (list) payload to topic.
    *
    * @param p_topic           URI of topic to publish to.
    * @param p_payload         Event payload.
    * @param p_exclude         If present, exclude this list of WAMP session IDs from receivers.
    * @param p_eligible        If present, only this list of WAMP session IDs is eligible for receiving.
    * @param p_qos             Quality-of-Service for event delivery.
    */
   PROCEDURE publish(p_topic     IN NVARCHAR2,
                     p_payload   IN JSON_LIST,
                     p_exclude   IN crossbar_sessionids   DEFAULT NULL,
                     p_eligible  IN crossbar_sessionids   DEFAULT NULL,
                     p_qos       IN INTEGER            DEFAULT QOS_BEST_EFFORT);

   /**
    * Export a stored procedure or function for RPC.
    *
    * You may export a given stored procedure under different endpoint URIs,
    * but there can only be at most one export per given URI.
    *
    * @param p_schema           Schema (owner) of stored procedure to be exported.
    * @param p_package          Package containing stored procedure to be exported.
    * @param p_proc             Procedure within package to be exported.
    * @param p_uri              URI under which the endpoint will be reachable via WAMP RPC.
    * @param p_authkeys         List of authentication keys that may access this endpoint.
    * @return                   Endpoint ID.
    */
   FUNCTION export(p_schema    IN VARCHAR2,
                   p_package   IN VARCHAR2,
                   p_proc      IN VARCHAR2,
                   p_endpoint  IN NVARCHAR2,
                   p_authkeys  IN crossbar_authkeys      DEFAULT NULL) RETURN NUMBER;


   /**
    * Export a stored procedure or function for RPC.
    *
    * Convenience shortcut procedure.
    */
   PROCEDURE export(p_package   IN VARCHAR2,
                    p_proc      IN VARCHAR2,
                    p_endpoint  IN NVARCHAR2,
                    p_authkeys  IN crossbar_authkeys      DEFAULT NULL);

   /**
    * Delete existing RPC export of a stored procedure. To delete an export,
    * you need to be the owner (= original creator) of the exported endpoint.
    *
    * @param p_endpoint_id     ID of endpoint as returned from creating the export.
    */
   PROCEDURE remove_export(p_endpoint_id   IN NUMBER);

   /**
    * Delete all existing RPC exports for the given schema/package/procedure.
    * You must be owner (= original creator) of _all_ exported endpoints for
    * this to succeed.
    *
    * @param p_schema          Schema name of exported procedures to delete or NULL for current schema.
    * @param p_package         Package name of exported procedures to delete or NULL for any package.
    * @param p_proc            Procedure name of exported procedures to delete or NULL for any procedure.
    * @return                  Number of exported endpoints deleted.
    */
   FUNCTION remove_exports(p_schema    IN VARCHAR2,
                           p_package   IN VARCHAR2,
                           p_proc      IN VARCHAR2) RETURN NUMBER;

   /**
    * Delete all existing RPC exports for the given schema/package/procedure.
    * You must be owner (= original creator) of _all_ exported endpoints for
    * this to succeed.
    *
    * @param p_schema          Schema name of exported procedures to delete or NULL for current schema.
    * @param p_package         Package name of exported procedures to delete or NULL for any package.
    * @param p_proc            Procedure name of exported procedures to delete or NULL for any procedure.
    */
   PROCEDURE remove_exports(p_schema    IN VARCHAR2,
                            p_package   IN VARCHAR2,
                            p_proc      IN VARCHAR2 DEFAULT NULL);

   /**
    * Delete all existing RPC exports for the given package/procedure within the current schema.
    * You must be owner (= original creator) of _all_ exported endpoints for
    * this to succeed.
    *
    * @param p_package         Package name of exported procedures to delete or NULL for any package.
    * @param p_proc            Procedure name of exported procedures to delete or NULL for any procedure.
    */
   PROCEDURE remove_exports(p_package   IN VARCHAR2,
                            p_proc      IN VARCHAR2 DEFAULT NULL);

   /**
    * Delete all existing RPC exports for stored procedures exported
    * under given URI pattern. The pattern is applied via a WHERE .. LIKE ..
    * expression. You must be owner (= original creator) of _all_ exported
    * endpoints for this to succeed.
    *
    * @param p_uri             URI of exported endpoints to delete.
    * @return                  Number of exported endpoints deleted.
    */
   FUNCTION remove_exports_by_uri(p_uri_pattern   IN NVARCHAR2) RETURN NUMBER;

   /**
    * Delete all existing RPC exports for stored procedures exported
    * under given URI pattern. The pattern is applied via a WHERE .. LIKE ..
    * expression. You must be owner (= original creator) of _all_ exported
    * endpoints for this to succeed.
    *
    * @param p_uri             URI of exported endpoints to delete.
    */
   PROCEDURE remove_exports_by_uri(p_uri_pattern   IN NVARCHAR2);

   /**
    * Raise application level exception. The WAMP client session will receive
    * an RPC error return.
    *
    * @param p_uri             Application error URI that identifies the error.
    * @param p_desc            Error description (for development/logging).
    * @param p_kill_session    Iff true, close the client's WAMP session (after sending the error).
    */
   PROCEDURE raise (p_uri             IN VARCHAR2,
                    p_desc            IN VARCHAR2,
                    p_kill_session    IN BOOLEAN DEFAULT FALSE);

   /**
    * Raise application level exception. The WAMP client session will receive
    * an RPC error return.
    *
    * @param p_uri             Application error URI that identifies the error.
    * @param p_desc            Error description (for development/logging).
    * @param p_detail          Optional application error details.
    * @param p_kill_session    Iff true, close the client's WAMP session (after sending the error).
    */
   PROCEDURE raise (p_uri             IN VARCHAR2,
                    p_desc            IN VARCHAR2,
                    p_detail          IN JSON_VALUE,
                    p_kill_session    IN BOOLEAN DEFAULT FALSE);

   /**
    * Raise application level exception. The WAMP client session will receive
    * an RPC error return.
    *
    * @param p_uri             Application error URI that identifies the error.
    * @param p_desc            Error description (for development/logging).
    * @param p_detail          Optional application error details.
    * @param p_kill_session    Iff true, close the client's WAMP session (after sending the error).
    */
   PROCEDURE raise (p_uri             IN VARCHAR2,
                    p_desc            IN VARCHAR2,
                    p_detail          IN JSON,
                    p_kill_session    IN BOOLEAN DEFAULT FALSE);

   /**
    * Raise application level exception. The WAMP client session will receive
    * an RPC error return.
    *
    * @param p_uri             Application error URI that identifies the error.
    * @param p_desc            Error description (for development/logging).
    * @param p_detail          Optional application error details.
    * @param p_kill_session    Iff true, close the client's WAMP session (after sending the error).
    */
   PROCEDURE raise (p_uri             IN VARCHAR2,
                    p_desc            IN VARCHAR2,
                    p_detail          IN JSON_LIST,
                    p_kill_session    IN BOOLEAN DEFAULT FALSE);

END crossbar;
/

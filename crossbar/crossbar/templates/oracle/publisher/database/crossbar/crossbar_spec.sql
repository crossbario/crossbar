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
    * Publish an event. This implements the WAMP "Publisher" role.
    *
    * @param p_uri             URI of topic to publish to.
    * @param p_args            The positional arguments of the event.
    * @param p_kwargs          The keyword arguments of the event.
    * @param p_exclude         If present, exclude this list of WAMP session IDs from receivers.
    * @param p_eligible        If present, only this list of WAMP session IDs is eligible for receiving.
    * @param p_qos             Quality-of-Service for event delivery.
    *
    * @return                  Event ID.
    */
   FUNCTION publish(p_uri       IN NVARCHAR2,
                    p_args      IN json_list             DEFAULT NULL,
                    p_kwargs    IN json                  DEFAULT NULL,
                    p_exclude   IN crossbar_sessionids   DEFAULT NULL,
                    p_eligible  IN crossbar_sessionids   DEFAULT NULL) RETURN INTEGER;


   /**
    * Register a stored procedure for remote calling. This implements the WAMP "Callee" role.
    *
    * Note: You may register a given stored procedure under different URIs,
    * but there can only be at most one registration per given URI.
    *
    * @param p_schema           Schema (owner) of stored procedure to be exported.
    * @param p_package          Package containing stored procedure to be exported.
    * @param p_proc             Procedure within package to be exported.
    * @param p_uri              URI under which the endpoint will be reachable via WAMP RPC.
    *
    * @return                   Registration ID.
    */
   FUNCTION register(p_schema    IN VARCHAR2,
                     p_package   IN VARCHAR2,
                     p_proc      IN VARCHAR2,
                     p_uri       IN NVARCHAR2) RETURN INTEGER;

   /**
    * End previous registration of a stored procedure.
    *
    * Note: To unregister, you need to be the owner (= original creator) of the
    * registered procedure.
    *
    * @param p_registration_id     ID of registration to unregister.
    */
   PROCEDURE unregister(p_registration IN INTEGER);


   /**
    * Subscribe a stored procedure as an event handler.
    *
    * Note: You may subscribe to a given URI multiple times, and you may subscribe
    * a given stored procedure for different URIs.
    *
    * @param p_schema           Schema (owner) of stored procedure to be exported.
    * @param p_package          Package containing stored procedure to be exported.
    * @param p_proc             Procedure within package to be exported.
    * @param p_uri              URI under which the endpoint will be reachable via WAMP RPC.
    *
    * @return                   Subscription ID.
    */
   FUNCTION subscribe(p_schema    IN VARCHAR2,
                      p_package   IN VARCHAR2,
                      p_proc      IN VARCHAR2,
                      p_uri       IN NVARCHAR2) RETURN INTEGER;

   /**
    * End previous subscription for a stored procedure.
    *
    * Note: To unsubscribe, you need to be the owner (= original creator) of the
    * subscribed procedure.
    *
    * @param p_subscription     ID of subscription to unsubscribe from.
    */
   PROCEDURE unsubscribe(p_subscription IN INTEGER);

END crossbar;
/

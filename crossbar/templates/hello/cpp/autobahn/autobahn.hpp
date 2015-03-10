///////////////////////////////////////////////////////////////////////////////
//
//  Copyright (C) 2014 Tavendo GmbH
//
//  Licensed under the Apache License, Version 2.0 (the "License");
//  you may not use this file except in compliance with the License.
//  You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
//  Unless required by applicable law or agreed to in writing, software
//  distributed under the License is distributed on an "AS IS" BASIS,
//  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//  See the License for the specific language governing permissions and
//  limitations under the License.
//
///////////////////////////////////////////////////////////////////////////////

#ifndef AUTOBAHN_HPP
#define AUTOBAHN_HPP

#include <cstdint>
#include <stdexcept>
#include <istream>
#include <ostream>
#include <string>
#include <utility>
#include <vector>
#include <map>
#include <functional>

#include <msgpack.hpp>

// http://stackoverflow.com/questions/22597948/using-boostfuture-with-then-continuations/
#define BOOST_THREAD_PROVIDES_FUTURE
#define BOOST_THREAD_PROVIDES_FUTURE_CONTINUATION
#define BOOST_THREAD_PROVIDES_FUTURE_WHEN_ALL_WHEN_ANY
#include <boost/thread/future.hpp>
//#include <future>

#include <boost/any.hpp>
#include <boost/asio.hpp>


/*! \mainpage Reference Documentation
 *
 * Welcome to the reference documentation of <b>Autobahn</b>|Cpp.<br>
 *
 * For a more gentle introduction, please visit http://autobahn.ws/cpp/.
 */


/*!
 * Autobahn namespace.
 */
namespace autobahn {

   /// A map holding any values and string keys.
   typedef std::map<std::string, boost::any> anymap;

   /// A vector holding any values.
   typedef std::vector<boost::any> anyvec;

   /// A pair of ::anyvec and ::anymap.
   typedef std::pair<anyvec, anymap> anyvecmap;


   /// Handler type for use with session::subscribe(const std::string&, handler_t)
   typedef std::function<void(const anyvec&, const anymap&)> handler_t;


   /// Endpoint type for use with session::provide(const std::string&, endpoint_t)
   typedef std::function<boost::any(const anyvec&, const anymap&)> endpoint_t;

   /// Endpoint type for use with session::provide_v(const std::string&, endpoint_v_t)
   typedef std::function<anyvec(const anyvec&, const anymap&)> endpoint_v_t;

   /// Endpoint type for use with session::provide_m(const std::string&, endpoint_m_t)
   typedef std::function<anymap(const anyvec&, const anymap&)> endpoint_m_t;

   /// Endpoint type for use with session::provide_vm(const std::string&, endpoint_vm_t)
   typedef std::function<anyvecmap(const anyvec&, const anymap&)> endpoint_vm_t;


   /// Endpoint type for use with session::provide(const std::string&, endpoint_ft)
   typedef std::function<boost::future<boost::any>(const anyvec&, const anymap&)> endpoint_f_t;

   /// Endpoint type for use with session::provide_fv(const std::string&, endpoint_fv_t)
   typedef std::function<boost::future<anyvec>(const anyvec&, const anymap&)> endpoint_fv_t;

   /// Endpoint type for use with session::provide_fm(const std::string&, endpoint_fm_t)
   typedef std::function<boost::future<anymap>(const anyvec&, const anymap&)> endpoint_fm_t;

   /// Endpoint type for use with session::provide_fvm(const std::string&, endpoint_fvm_t)
   typedef std::function<boost::future<anyvecmap>(const anyvec&, const anymap&)> endpoint_fvm_t;


   /// Represents a procedure registration.
   struct registration {
      registration() : id(0) {};
      registration(uint64_t id) : id(id) {};
      uint64_t id;
   };

   /// Represents a topic subscription.
   struct subscription {
      subscription() : id(0) {};
      subscription(uint64_t id) : id(id) {};
      uint64_t id;
   };

   /// Represents an event publication (for acknowledged publications).
   struct publication {
      publication() : id(0) {};
      publication(uint64_t id) : id(id) {};
      uint64_t id;
   };


   /*!
    * A WAMP session.
    */
   template<typename IStream, typename OStream>
   class session {

      public:

         /*!
          * Create a new WAMP session.
          *
          * \param in The input stream to run this session on.
          * \param out THe output stream to run this session on.
          */
         session(boost::asio::io_service& io, IStream& in, OStream& out, bool debug = false);

         /*!
          * Start listening on the IStream provided to the constructor
          * of this session.
          */
         inline
         void start();

         /*!
          * Closes the IStream and the OStream provided to the constructor
          * of this session.
          */
         inline
         void stop();

         /*!
          * Join a realm with this session.
          *
          * \param realm The realm to join on the WAMP router connected to.
          * \return A future that resolves with the session ID when the realm was joined.
          */
         inline
         boost::future<uint64_t> join(const std::string& realm);

         /*!
          * Leave the realm.
          *
          * \param reason An optional WAMP URI providing a reason for leaving.
          * \return A future that resolves with the reason sent by the peer.
          */
         inline
         boost::future<std::string> leave(const std::string& reason = std::string("wamp.error.close_realm"));


         /*!
          * Publish an event with empty payload to a topic.
          *
          * \param topic The URI of the topic to publish to.
          */
         inline
         void publish(const std::string& topic);

         /*!
          * Publish an event with positional payload to a topic.
          *
          * \param topic The URI of the topic to publish to.
          * \param args The positional payload for the event.
          */
         inline
         void publish(const std::string& topic, const anyvec& args);

         /*!
          * Publish an event with both positional and keyword payload to a topic.
          *
          * \param topic The URI of the topic to publish to.
          * \param args The positional payload for the event.
          * \param kwargs The keyword payload for the event.
          */
         inline
         void publish(const std::string& topic, const anyvec& args, const anymap& kwargs);


         /*!
          * Subscribe a handler to a topic to receive events.
          *
          * \param topic The URI of the topic to subscribe to.
          * \param handler The handler that will receive events under the subscription.
          * \return A future that resolves to a autobahn::subscription
          */
         inline
         boost::future<subscription> subscribe(const std::string& topic, handler_t handler);


         /*!
          * Calls a remote procedure with no arguments.
          *
          * \param procedure The URI of the remote procedure to call.
          * \return A future that resolves to the result of the remote procedure call.
          */
         inline
         boost::future<boost::any> call(const std::string& procedure);

         /*!
          * Calls a remote procedure with positional arguments.
          *
          * \param procedure The URI of the remote procedure to call.
          * \param args The positional arguments for the call.
          * \return A future that resolves to the result of the remote procedure call.
          */
         inline
         boost::future<boost::any> call(const std::string& procedure, const anyvec& args);

         /*!
          * Calls a remote procedure with positional and keyword arguments.
          *
          * \param procedure The URI of the remote procedure to call.
          * \param args The positional arguments for the call.
          * \param kwargs The keyword arguments for the call.
          * \return A future that resolves to the result of the remote procedure call.
          */
         inline
         boost::future<boost::any> call(const std::string& procedure, const anyvec& args, const anymap& kwargs);


         /*!
          * Register an endpoint as a procedure that can be called remotely.
          *
          * \param procedure The URI under which the procedure is to be exposed.
          * \param endpoint The endpoint to be exposed as a remotely callable procedure.
          * \return A future that resolves to a autobahn::registration
          */
         inline boost::future<registration> provide(const std::string& procedure, endpoint_t endpoint);

         inline boost::future<registration> provide_v(const std::string& procedure, endpoint_v_t endpoint);

         inline boost::future<registration> provide_m(const std::string& procedure, endpoint_m_t endpoint);

         inline boost::future<registration> provide_vm(const std::string& procedure, endpoint_vm_t endpoint);

         inline boost::future<registration> provide_f(const std::string& procedure, endpoint_f_t endpoint);

         inline boost::future<registration> provide_fv(const std::string& procedure, endpoint_fv_t endpoint);

         inline boost::future<registration> provide_fm(const std::string& procedure, endpoint_fm_t endpoint);

         inline boost::future<registration> provide_fvm(const std::string& procedure, endpoint_fvm_t endpoint);

      private:

         template<typename E>
         inline boost::future<registration> _provide(const std::string& procedure, E endpoint);


         //////////////////////////////////////////////////////////////////////////////////////
         /// Caller

         /// An outstanding WAMP call.
         struct call_t {
            boost::promise<boost::any> m_res;
         };

         /// Map of outstanding WAMP calls (request ID -> call).
         typedef std::map<uint64_t, call_t> calls_t;

         /// Map of WAMP call ID -> call
         calls_t m_calls;


         //////////////////////////////////////////////////////////////////////////////////////
         /// Subscriber

         /// An outstanding WAMP subscribe request.
         struct subscribe_request_t {
            subscribe_request_t() {};
            subscribe_request_t(handler_t handler) : m_handler(handler) {};
            handler_t m_handler;
            boost::promise<subscription> m_res;
         };

         /// Map of outstanding WAMP subscribe requests (request ID -> subscribe request).
         typedef std::map<uint64_t, subscribe_request_t> subscribe_requests_t;

         /// Map of WAMP subscribe request ID -> subscribe request
         subscribe_requests_t m_subscribe_requests;

         /// Map of subscribed handlers (subscription ID -> handler)
         typedef std::multimap<uint64_t, handler_t> handlers_t;

         /// Map of WAMP subscription ID -> handler
         handlers_t m_handlers;


         //////////////////////////////////////////////////////////////////////////////////////
         /// Callee

         /// An outstanding WAMP register request.
         struct register_request_t {
            register_request_t() {};
            register_request_t(boost::any endpoint) : m_endpoint(endpoint) {};
            boost::any m_endpoint;
            boost::promise<registration> m_res;
         };

         /// Map of outstanding WAMP register requests (request ID -> register request).
         typedef std::map<uint64_t, register_request_t> register_requests_t;

         /// Map of WAMP register request ID -> register request
         register_requests_t m_register_requests;

         /// Map of registered endpoints (registration ID -> endpoint)
         typedef std::map<uint64_t, boost::any> endpoints_t;

         /// Map of WAMP registration ID -> endpoint
         endpoints_t m_endpoints;

         /// An unserialized, raw WAMP message.
         typedef std::vector<msgpack::object> wamp_msg_t;


         /// Process a WAMP ERROR message.
         inline void process_error(const wamp_msg_t& msg);

         /// Process a WAMP HELLO message.
         inline void process_welcome(const wamp_msg_t& msg);

         /// Process a WAMP RESULT message.
         inline void process_call_result(const wamp_msg_t& msg);

         /// Process a WAMP SUBSCRIBED message.
         inline void process_subscribed(const wamp_msg_t& msg);

         /// Process a WAMP EVENT message.
         inline void process_event(const wamp_msg_t& msg);

         /// Process a WAMP REGISTERED message.
         inline void process_registered(const wamp_msg_t& msg);

         /// Process a WAMP INVOCATION message.
         inline void process_invocation(const wamp_msg_t& msg);

         /// Process a WAMP GOODBYE message.
         inline void process_goodbye(const wamp_msg_t& msg);


         /// Unpacks any MsgPack object into boost::any value.
         inline boost::any unpack_any(msgpack::object& obj);

         /// Unpacks MsgPack array into anyvec.
         inline void unpack_anyvec(std::vector<msgpack::object>& raw_args, anyvec& args);

         /// Unpacks MsgPack map into anymap.
         inline void unpack_anymap(std::map<std::string, msgpack::object>& raw_kwargs, anymap& kwargs);

         /// Pack any value into serializion buffer.
         inline void pack_any(const boost::any& value);

         /// Send out message serialized in serialization buffer to ostream.
         inline void send();

         /// Receive one message from istream in m_unpacker.
         inline void receive_msg();


         void got_msg_header(const boost::system::error_code& error);

         void got_msg_body(const boost::system::error_code& error);

         void got_msg(const msgpack::object& obj);


         bool m_debug;

         bool m_stopped;

         boost::asio::io_service& m_io;

         /// Input stream this session runs on.
         IStream& m_in;

         /// Output stream this session runs on.
         OStream& m_out;


         char m_buffer_msg_len[4];
         uint32_t m_msg_len;

         boost::promise<boost::any> m_test_promise;


         /// MsgPack serialization buffer.
         msgpack::sbuffer m_buffer;

         /// MsgPacker serialization packer.
         msgpack::packer<msgpack::sbuffer> m_packer;

         /// MsgPack unserialization unpacker.
         msgpack::unpacker m_unpacker;

         /// WAMP session ID (if the session is joined to a realm).
         uint64_t m_session_id;

         /// Future to be fired when session was joined.
         boost::promise<uint64_t> m_session_join;

         /// Last request ID of outgoing WAMP requests.
         uint64_t m_request_id;


         bool m_goodbye_sent;

         boost::promise<std::string> m_session_leave;

         /// WAMP message type codes.
         enum class msg_code : int {
            HELLO = 1,
            WELCOME = 2,
            ABORT = 3,
            CHALLENGE = 4,
            AUTHENTICATE = 5,
            GOODBYE = 6,
            HEARTBEAT = 7,
            ERROR = 8,
            PUBLISH = 16,
            PUBLISHED = 17,
            SUBSCRIBE = 32,
            SUBSCRIBED = 33,
            UNSUBSCRIBE = 34,
            UNSUBSCRIBED = 35,
            EVENT = 36,
            CALL = 48,
            CANCEL = 49,
            RESULT = 50,
            REGISTER = 64,
            REGISTERED = 65,
            UNREGISTER = 66,
            UNREGISTERED = 67,
            INVOCATION = 68,
            INTERRUPT = 69,
            YIELD = 70
         };
   };


   class protocol_error : public std::runtime_error {
      public:
         protocol_error(const std::string& msg) : std::runtime_error(msg) {};
   };

   class no_session_error : public std::runtime_error {
      public:
         no_session_error() : std::runtime_error("session not joined") {};
   };

}

#include "autobahn_impl.hpp"

#endif // AUTOBAHN_HPP

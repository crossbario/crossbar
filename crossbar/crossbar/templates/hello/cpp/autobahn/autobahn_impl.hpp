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

#include <arpa/inet.h>
#include <unistd.h>
#include <stdlib.h>


#include <cstdint>
#include <iostream>
#include <vector>
#include <map>
#include <string>
#include <sstream>
#include <stdexcept>


namespace autobahn {

   template<typename IStream, typename OStream>
   session<IStream, OStream>::session(boost::asio::io_service& io, IStream& in, OStream& out, bool debug)
      : m_debug(debug),
        m_stopped(false),
        m_io(io),
        m_in(in),
        m_out(out),
        m_packer(&m_buffer),
        m_session_id(0),
        m_request_id(0)
   {
//      receive_msg();
   }

/*
   void session<IStream, OStream>::stop(int exit_code) {
      std::cerr << "stopping .." << std::endl;
      m_stopped = true;
      close(STDIN_FILENO);
      close(STDOUT_FILENO);
      close(STDERR_FILENO);
      exit(exit_code);
   }
*/

   template<typename IStream, typename OStream>
   void session<IStream, OStream>::start() {
      receive_msg();
   }


   template<typename IStream, typename OStream>
   void session<IStream, OStream>::stop() {
      m_stopped = true;
      try {
         m_in.close();
      } catch (...) {
      }
      try {
         m_out.close();
      } catch (...) {
      }
   }


   template<typename IStream, typename OStream>
   boost::future<uint64_t> session<IStream, OStream>::join(const std::string& realm) {
//   boost::shared_future<uint64_t> session<IStream, OStream>::join(const std::string& realm) {

      // [HELLO, Realm|uri, Details|dict]

      m_packer.pack_array(3);

      m_packer.pack(static_cast<int> (msg_code::HELLO));
      m_packer.pack(realm);

      m_packer.pack_map(1);
      m_packer.pack(std::string("roles"));

      m_packer.pack_map(4);

      m_packer.pack(std::string("caller"));
      m_packer.pack_map(0);

      m_packer.pack(std::string("callee"));
      m_packer.pack_map(0);

      m_packer.pack(std::string("publisher"));
      m_packer.pack_map(0);

      m_packer.pack(std::string("subscriber"));
      m_packer.pack_map(0);

      send();

//      return m_session_join.get_future().share();
//      return boost::shared_future<uint64_t>(m_session_join.get_future());
//      return std::move(m_session_join.get_future());
      return m_session_join.get_future();
   }


   template<typename IStream, typename OStream>
   boost::future<subscription> session<IStream, OStream>::subscribe(const std::string& topic, handler_t handler) {

      if (!m_session_id) {
         throw no_session_error();
      }

      // [SUBSCRIBE, Request|id, Options|dict, Topic|uri]

      m_request_id += 1;
      m_subscribe_requests[m_request_id] = subscribe_request_t(handler);

      m_packer.pack_array(4);
      m_packer.pack(static_cast<int> (msg_code::SUBSCRIBE));
      m_packer.pack(m_request_id);
      m_packer.pack_map(0);
      m_packer.pack(topic);
      send();

      return m_subscribe_requests[m_request_id].m_res.get_future();
   }



   template<typename IStream, typename OStream>
   boost::future<registration> session<IStream, OStream>::provide(const std::string& procedure, endpoint_t endpoint) {
      return _provide(procedure, static_cast<endpoint_t> (endpoint));
   }


   template<typename IStream, typename OStream>
   boost::future<registration> session<IStream, OStream>::provide_v(const std::string& procedure, endpoint_v_t endpoint) {
      return _provide(procedure, static_cast<endpoint_v_t> (endpoint));
   }


   template<typename IStream, typename OStream>
   boost::future<registration> session<IStream, OStream>::provide_m(const std::string& procedure, endpoint_m_t endpoint) {
      return _provide(procedure, static_cast<endpoint_m_t> (endpoint));
   }


   template<typename IStream, typename OStream>
   boost::future<registration> session<IStream, OStream>::provide_vm(const std::string& procedure, endpoint_vm_t endpoint) {
      return _provide(procedure, static_cast<endpoint_vm_t> (endpoint));
   }


   template<typename IStream, typename OStream>
   boost::future<registration> session<IStream, OStream>::provide_f(const std::string& procedure, endpoint_f_t endpoint) {
      return _provide(procedure, static_cast<endpoint_f_t> (endpoint));
   }


   template<typename IStream, typename OStream>
   boost::future<registration> session<IStream, OStream>::provide_fv(const std::string& procedure, endpoint_fv_t endpoint) {
      return _provide(procedure, static_cast<endpoint_fv_t> (endpoint));
   }


   template<typename IStream, typename OStream>
   boost::future<registration> session<IStream, OStream>::provide_fm(const std::string& procedure, endpoint_fm_t endpoint) {
      return _provide(procedure, static_cast<endpoint_fm_t> (endpoint));
   }


   template<typename IStream, typename OStream>
   boost::future<registration> session<IStream, OStream>::provide_fvm(const std::string& procedure, endpoint_fvm_t endpoint) {
      return _provide(procedure, static_cast<endpoint_fvm_t> (endpoint));
   }


   template<typename IStream, typename OStream>
   template<typename E>
   boost::future<registration> session<IStream, OStream>::_provide(const std::string& procedure, E endpoint) {

      if (!m_session_id) {
         throw no_session_error();
      }

      m_request_id += 1;
      m_register_requests[m_request_id] = register_request_t(endpoint);

      // [REGISTER, Request|id, Options|dict, Procedure|uri]

      m_packer.pack_array(4);
      m_packer.pack(static_cast<int> (msg_code::REGISTER));
      m_packer.pack(m_request_id);
      m_packer.pack_map(0);
      m_packer.pack(procedure);
      send();

      return m_register_requests[m_request_id].m_res.get_future();
   }


   template<typename IStream, typename OStream>
   void session<IStream, OStream>::publish(const std::string& topic) {

      if (!m_session_id) {
         throw no_session_error();
      }

      m_request_id += 1;

      // [PUBLISH, Request|id, Options|dict, Topic|uri]

      m_packer.pack_array(4);
      m_packer.pack(static_cast<int> (msg_code::PUBLISH));
      m_packer.pack(m_request_id);
      m_packer.pack_map(0);
      m_packer.pack(topic);
      send();
   }


   template<typename IStream, typename OStream>
   void session<IStream, OStream>::publish(const std::string& topic, const anyvec& args) {

      if (!m_session_id) {
         throw no_session_error();
      }

      if (args.size() > 0) {

         m_request_id += 1;

         // [PUBLISH, Request|id, Options|dict, Topic|uri, Arguments|list]

         m_packer.pack_array(5);
         m_packer.pack(static_cast<int> (msg_code::PUBLISH));
         m_packer.pack(m_request_id);
         m_packer.pack_map(0);
         m_packer.pack(topic);
         pack_any(args);
         send();

      } else {

         publish(topic);
      }
   }


   template<typename IStream, typename OStream>
   void session<IStream, OStream>::publish(const std::string& topic, const anyvec& args, const anymap& kwargs) {

      if (!m_session_id) {
         throw no_session_error();
      }

      if (kwargs.size() > 0) {

         m_request_id += 1;

         // [PUBLISH, Request|id, Options|dict, Topic|uri, Arguments|list, ArgumentsKw|dict]

         m_packer.pack_array(6);
         m_packer.pack(static_cast<int> (msg_code::PUBLISH));
         m_packer.pack(m_request_id);
         m_packer.pack_map(0);
         m_packer.pack(topic);
         pack_any(args);
         pack_any(kwargs);
         send();

      } else {

         publish(topic, args);
      }
   }


   template<typename IStream, typename OStream>
   boost::future<boost::any> session<IStream, OStream>::call(const std::string& procedure) {

      if (!m_session_id) {
         throw no_session_error();
      }

      m_request_id += 1;
      m_calls[m_request_id] = call_t();

      // [CALL, Request|id, Options|dict, Procedure|uri]

      m_packer.pack_array(4);
      m_packer.pack(static_cast<int> (msg_code::CALL));
      m_packer.pack(m_request_id);
      m_packer.pack_map(0);
      m_packer.pack(procedure);
      send();

      return m_calls[m_request_id].m_res.get_future();
   }


   template<typename IStream, typename OStream>
   boost::future<boost::any> session<IStream, OStream>::call(const std::string& procedure, const anyvec& args) {

      if (!m_session_id) {
         throw no_session_error();
      }

      if (args.size() > 0) {

         m_request_id += 1;
         m_calls[m_request_id] = call_t();

         // [CALL, Request|id, Options|dict, Procedure|uri, Arguments|list]

         m_packer.pack_array(5);
         m_packer.pack(static_cast<int> (msg_code::CALL));
         m_packer.pack(m_request_id);
         m_packer.pack_map(0);
         m_packer.pack(procedure);
         pack_any(args);
         send();

         return m_calls[m_request_id].m_res.get_future();

      } else {

         return call(procedure);
      }
   }


   template<typename IStream, typename OStream>
   boost::future<boost::any> session<IStream, OStream>::call(const std::string& procedure, const anyvec& args, const anymap& kwargs) {

      if (!m_session_id) {
         throw no_session_error();
      }

      if (kwargs.size() > 0) {

         m_request_id += 1;
         m_calls[m_request_id] = call_t();

         // [CALL, Request|id, Options|dict, Procedure|uri, Arguments|list, ArgumentsKw|dict]

         m_packer.pack_array(6);
         m_packer.pack(static_cast<int> (msg_code::CALL));
         m_packer.pack(m_request_id);
         m_packer.pack_map(0);
         m_packer.pack(procedure);
         pack_any(args);
         pack_any(kwargs);
         send();

         return m_calls[m_request_id].m_res.get_future();

      } else {
         return call(procedure, args);
      }
   }




   template<typename IStream, typename OStream>
   void session<IStream, OStream>::pack_any(const boost::any& value) {

      if (value.empty()) {

         m_packer.pack_nil();

      } else if (value.type() == typeid(anyvec)) {

         anyvec v = boost::any_cast<anyvec>(value);

         m_packer.pack_array(v.size());

         anyvec::iterator it = v.begin();
         while (it != v.end()) {
            pack_any(*it);
            ++it;
         }

      } else if (value.type() == typeid(anymap)) {

         anymap m = boost::any_cast<anymap>(value);

         m_packer.pack_map(m.size());

         anymap::iterator it = m.begin();
         while (it != m.end()) {
            m_packer.pack(it->first); // std::string
            pack_any(it->second);
            ++it;
         }

      } else if (value.type() == typeid(int)) {

         int val = boost::any_cast<int>(value);
         m_packer.pack(val);

      } else if (value.type() == typeid(uint64_t)) {

         uint64_t val = boost::any_cast<uint64_t>(value);
         m_packer.pack(val);

      } else if (value.type() == typeid(bool)) {

         bool val = boost::any_cast<bool>(value);
         m_packer.pack(val);

      } else if (value.type() == typeid(float)) {

         float val = boost::any_cast<float>(value);
         m_packer.pack(val);

      } else if (value.type() == typeid(double)) {

         double val = boost::any_cast<double>(value);
         m_packer.pack(val);

      } else if (value.type() == typeid(std::string)) {

         std::string val = boost::any_cast<std::string>(value);
         m_packer.pack(val);

      } else {
         std::cerr << "Warning: don't know how to pack type " << value.type().name() << std::endl;
      }
   }


   template<typename IStream, typename OStream>
   void session<IStream, OStream>::process_welcome(const wamp_msg_t& msg) {
      m_session_id = msg[1].as<uint64_t>();
      m_session_join.set_value(m_session_id);
   }


   template<typename IStream, typename OStream>
   void session<IStream, OStream>::process_goodbye(const wamp_msg_t& msg) {

/*
      if (!m_session_id) {
         throw protocol_error("GOODBYE received an no session established");
      }
*/
      m_session_id = 0;

      if (!m_goodbye_sent) {

         // if we did not initiate closing, reply ..

         // [GOODBYE, Details|dict, Reason|uri]

         m_packer.pack_array(3);

         m_packer.pack(static_cast<int> (msg_code::GOODBYE));
         m_packer.pack_map(0);
         m_packer.pack(std::string("wamp.error.goodbye_and_out"));
         send();

      } else {
         // we previously initiated closing, so this
         // is the peer reply
      }
      std::string reason = msg[2].as<std::string>();
      m_session_leave.set_value(reason);
   }


   template<typename IStream, typename OStream>
   boost::future<std::string> session<IStream, OStream>::leave(const std::string& reason) {

      if (!m_session_id) {
         throw no_session_error();
      }

      m_goodbye_sent = true;
      m_session_id = 0;

      // [GOODBYE, Details|dict, Reason|uri]

      m_packer.pack_array(3);

      m_packer.pack(static_cast<int> (msg_code::GOODBYE));
      m_packer.pack_map(0);
      m_packer.pack(reason);
      send();

      return m_session_leave.get_future();
   }


   template<typename IStream, typename OStream>
   void session<IStream, OStream>::unpack_anyvec(std::vector<msgpack::object>& raw_args, anyvec& args) {
      for (int i = 0; i < raw_args.size(); ++i) {
         args.push_back(unpack_any(raw_args[i]));
      }
   }


   template<typename IStream, typename OStream>
   void session<IStream, OStream>::unpack_anymap(std::map<std::string, msgpack::object>& raw_kwargs, anymap& kwargs) {
       for (auto& raw_args : raw_kwargs) {
           kwargs[raw_args.first] = unpack_any(raw_args.second);
       }
   }


   template<typename IStream, typename OStream>
   boost::any session<IStream, OStream>::unpack_any(msgpack::object& obj) {
      switch (obj.type) {

         case msgpack::type::STR:
            return boost::any(obj.as<std::string>());

         case msgpack::type::POSITIVE_INTEGER:
            return boost::any(obj.as<uint64_t>());

         case msgpack::type::NEGATIVE_INTEGER:
            return boost::any(obj.as<int64_t>());

         case msgpack::type::BOOLEAN:
            return boost::any(obj.as<bool>());

         case msgpack::type::DOUBLE:
            return boost::any(obj.as<double>());

         case msgpack::type::NIL:
            return boost::any();

         case msgpack::type::ARRAY:
            {
               anyvec out_vec;
               std::vector<msgpack::object> in_vec;

               obj.convert(&in_vec);
               unpack_anyvec(in_vec, out_vec);

               return out_vec;
            }

         case msgpack::type::MAP:
            {
               anymap out_map;
               std::map<std::string, msgpack::object> in_map;

               obj.convert(&in_map);
               unpack_anymap(in_map, out_map);
               return out_map;
            }

         default:
            return boost::any();
      }
   }


   template<typename IStream, typename OStream>
   void session<IStream, OStream>::process_error(const wamp_msg_t& msg) {

      // [ERROR, REQUEST.Type|int, REQUEST.Request|id, Details|dict, Error|uri]
      // [ERROR, REQUEST.Type|int, REQUEST.Request|id, Details|dict, Error|uri, Arguments|list]
      // [ERROR, REQUEST.Type|int, REQUEST.Request|id, Details|dict, Error|uri, Arguments|list, ArgumentsKw|dict]

      // message length
      //
      if (msg.size() != 5 && msg.size() != 6 && msg.size() != 7) {
         throw protocol_error("invalid ERROR message structure - length must be 5, 6 or 7");
      }

      // REQUEST.Type|int
      //
      if (msg[1].type != msgpack::type::POSITIVE_INTEGER) {
         throw protocol_error("invalid ERROR message structure - REQUEST.Type must be an integer");
      }
      msg_code request_type = static_cast<msg_code> (msg[1].as<int>());

      if (request_type != msg_code::CALL &&
          request_type != msg_code::REGISTER &&
          request_type != msg_code::UNREGISTER &&
          request_type != msg_code::PUBLISH &&
          request_type != msg_code::SUBSCRIBE &&
          request_type != msg_code::UNSUBSCRIBE) {
         throw protocol_error("invalid ERROR message - ERROR.Type must one of CALL, REGISTER, UNREGISTER, SUBSCRIBE, UNSUBSCRIBE");
      }

      // REQUEST.Request|id
      //
      if (msg[2].type != msgpack::type::POSITIVE_INTEGER) {
         throw protocol_error("invalid ERROR message structure - REQUEST.Request must be an integer");
      }
      uint64_t request_id = msg[2].as<uint64_t>();

      // Details
      //
      if (msg[3].type != msgpack::type::MAP) {
         throw protocol_error("invalid ERROR message structure - Details must be a dictionary");
      }

      // Error|uri
      //
      if (msg[4].type != msgpack::type::STR) {
         throw protocol_error("invalid ERROR message - Error must be a string (URI)");
      }
      std::string error = msg[4].as<std::string>();

      // Arguments|list
      //
      if (msg.size() > 5) {
         if (msg[5].type  != msgpack::type::ARRAY) {
            throw protocol_error("invalid ERROR message structure - Arguments must be a list");
         }
      }

      // ArgumentsKw|list
      //
      if (msg.size() > 6) {
         if (msg[6].type  != msgpack::type::MAP) {
            throw protocol_error("invalid ERROR message structure - ArgumentsKw must be a dictionary");
         }
      }

      switch (request_type) {

         case msg_code::CALL:
            {
               //
               // process CALL ERROR
               //
               typename calls_t::iterator call = m_calls.find(request_id);

               if (call != m_calls.end()) {

                  // FIXME: forward all error info .. also not sure if this is the correct
                  // way to use set_exception()
                  call->second.m_res.set_exception(boost::copy_exception(std::runtime_error(error)));

               } else {
                  throw protocol_error("bogus ERROR message for non-pending CALL request ID");
               }
            }
            break;

         // FIXME: handle other error messages
         default:
            std::cerr << "unhandled ERROR message" << std::endl;
      }
   }


   template<typename IStream, typename OStream>
   void session<IStream, OStream>::process_invocation(const wamp_msg_t& msg) {

      // [INVOCATION, Request|id, REGISTERED.Registration|id, Details|dict]
      // [INVOCATION, Request|id, REGISTERED.Registration|id, Details|dict, CALL.Arguments|list]
      // [INVOCATION, Request|id, REGISTERED.Registration|id, Details|dict, CALL.Arguments|list, CALL.ArgumentsKw|dict]

      if (msg.size() != 4 && msg.size() != 5 && msg.size() != 6) {
         throw protocol_error("invalid INVOCATION message structure - length must be 4, 5 or 6");
      }

      if (msg[1].type != msgpack::type::POSITIVE_INTEGER) {
         throw protocol_error("invalid INVOCATION message structure - INVOCATION.Request must be an integer");
      }
      uint64_t request_id = msg[1].as<uint64_t>();

      if (msg[2].type != msgpack::type::POSITIVE_INTEGER) {
         throw protocol_error("invalid INVOCATION message structure - INVOCATION.Registration must be an integer");
      }
      uint64_t registration_id = msg[2].as<uint64_t>();

      endpoints_t::iterator endpoint = m_endpoints.find(registration_id);

      if (endpoint != m_endpoints.end()) {

         if (msg[3].type != msgpack::type::MAP) {
            throw protocol_error("invalid INVOCATION message structure - Details must be a dictionary");
         }

         anyvec args;
         anymap kwargs;

         if (msg.size() > 4) {

            if (msg[4].type != msgpack::type::ARRAY) {
               throw protocol_error("invalid INVOCATION message structure - INVOCATION.Arguments must be a list");
            }

            std::vector<msgpack::object> raw_args;
            msg[4].convert(&raw_args);
            unpack_anyvec(raw_args, args);

            if (msg.size() > 5) {
               std::map<std::string, msgpack::object> raw_kwargs;
               msg[5].convert(&raw_kwargs);
               unpack_anymap(raw_kwargs, kwargs);
            }
         }

         // [YIELD, INVOCATION.Request|id, Options|dict]
         // [YIELD, INVOCATION.Request|id, Options|dict, Arguments|list]
         // [YIELD, INVOCATION.Request|id, Options|dict, Arguments|list, ArgumentsKw|dict]
         try {

            if ((endpoint->second).type() == typeid(endpoint_t)) {

               if (m_debug) {
                  std::cerr << "Invoking endpoint registered under " << registration_id << " as of type endpoint_t" << std::endl;
               }

               boost::any res = ( boost::any_cast<endpoint_t>(endpoint->second) )(args, kwargs);

               m_packer.pack_array(4);
               m_packer.pack(static_cast<int> (msg_code::YIELD));
               m_packer.pack(request_id);
               m_packer.pack_map(0);
               m_packer.pack_array(1);
               pack_any(res);
               send();

            } else if ((endpoint->second).type() == typeid(endpoint_v_t)) {

               if (m_debug) {
                  std::cerr << "Invoking endpoint registered under " << registration_id << " as of type endpoint_v_t" << std::endl;
               }

               anyvec res = ( boost::any_cast<endpoint_v_t>(endpoint->second) )(args, kwargs);

               m_packer.pack_array(4);
               m_packer.pack(static_cast<int> (msg_code::YIELD));
               m_packer.pack(request_id);
               m_packer.pack_map(0);
               pack_any(res);
               send();

            } else if ((endpoint->second).type() == typeid(endpoint_fvm_t)) {

               if (m_debug) {
                  std::cerr << "Invoking endpoint registered under " << registration_id << " as of type endpoint_fvm_t" << std::endl;
               }

               boost::future<anyvecmap> f_res = ( boost::any_cast<endpoint_fvm_t>(endpoint->second) )(args, kwargs);

               auto done = f_res.then([&](decltype(f_res) f) {

                  anyvecmap res = f.get();

                  m_packer.pack_array(5);
                  m_packer.pack(static_cast<int> (msg_code::YIELD));
                  m_packer.pack(request_id);
                  m_packer.pack_map(0);
                  pack_any(res.first);
                  pack_any(res.second);
                  send();
               });

               done.wait();

            } else {
               // FIXME
               std::cerr << "FIX ME INVOCATION " << std::endl;
               std::cerr << typeid(endpoint_t).name() << std::endl;
               std::cerr << ((endpoint->second).type()).name() << std::endl;
            }

         }
         catch (...) {
            // FIXME: send ERROR
            std::cerr << "INVOCATION failed" << std::endl;
         }

      } else {
         throw protocol_error("bogus INVOCATION message for non-registered registration ID");
      }
   }


   template<typename IStream, typename OStream>
   void session<IStream, OStream>::process_call_result(const wamp_msg_t& msg) {

      // [RESULT, CALL.Request|id, Details|dict]
      // [RESULT, CALL.Request|id, Details|dict, YIELD.Arguments|list]
      // [RESULT, CALL.Request|id, Details|dict, YIELD.Arguments|list, YIELD.ArgumentsKw|dict]

      if (msg.size() != 3 && msg.size() != 4 && msg.size() != 5) {
         throw protocol_error("invalid RESULT message structure - length must be 3, 4 or 5");
      }

      if (msg[1].type != msgpack::type::POSITIVE_INTEGER) {
         throw protocol_error("invalid RESULT message structure - CALL.Request must be an integer");
      }

      uint64_t request_id = msg[1].as<uint64_t>();

      typename calls_t::iterator call = m_calls.find(request_id);

      if (call != m_calls.end()) {

         if (msg[2].type != msgpack::type::MAP) {
            throw protocol_error("invalid RESULT message structure - Details must be a dictionary");
         }

         if (msg.size() > 3) {

            if (msg[3].type != msgpack::type::ARRAY) {
               throw protocol_error("invalid RESULT message structure - YIELD.Arguments must be a list");
            }

            std::vector<msgpack::object> raw_args;
            msg[3].convert(&raw_args);

            anyvec args;

            unpack_anyvec(raw_args, args);

            if (args.size() > 0) {
               call->second.m_res.set_value(args[0]);
            } else {
               call->second.m_res.set_value(boost::any());
            }

         } else {
            // empty result
            call->second.m_res.set_value(boost::any());
         }
      } else {
         throw protocol_error("bogus RESULT message for non-pending request ID");
      }
   }


   template<typename IStream, typename OStream>
   void session<IStream, OStream>::process_subscribed(const wamp_msg_t& msg) {

      // [SUBSCRIBED, SUBSCRIBE.Request|id, Subscription|id]

      if (msg.size() != 3) {
         throw protocol_error("invalid SUBSCRIBED message structure - length must be 3");
      }

      if (msg[1].type != msgpack::type::POSITIVE_INTEGER) {
         throw protocol_error("invalid SUBSCRIBED message structure - SUBSCRIBED.Request must be an integer");
      }

      uint64_t request_id = msg[1].as<uint64_t>();

      typename subscribe_requests_t::iterator subscribe_request = m_subscribe_requests.find(request_id);

      if (subscribe_request != m_subscribe_requests.end()) {

         if (msg[2].type != msgpack::type::POSITIVE_INTEGER) {
            throw protocol_error("invalid SUBSCRIBED message structure - SUBSCRIBED.Subscription must be an integer");
         }

         uint64_t subscription_id = msg[2].as<uint64_t>();

         m_handlers.insert(std::make_pair(subscription_id, subscribe_request->second.m_handler));

         subscribe_request->second.m_res.set_value(subscription(subscription_id));

         m_subscribe_requests.erase(request_id);

      } else {
         throw protocol_error("bogus SUBSCRIBED message for non-pending request ID");
      }
   }


   template<typename IStream, typename OStream>
   void session<IStream, OStream>::process_event(const wamp_msg_t& msg) {

      // [EVENT, SUBSCRIBED.Subscription|id, PUBLISHED.Publication|id, Details|dict]
      // [EVENT, SUBSCRIBED.Subscription|id, PUBLISHED.Publication|id, Details|dict, PUBLISH.Arguments|list]
      // [EVENT, SUBSCRIBED.Subscription|id, PUBLISHED.Publication|id, Details|dict, PUBLISH.Arguments|list, PUBLISH.ArgumentsKw|dict]

      if (msg.size() != 4 && msg.size() != 5 && msg.size() != 6) {
         throw protocol_error("invalid EVENT message structure - length must be 4, 5 or 6");
      }

      if (msg[1].type != msgpack::type::POSITIVE_INTEGER) {
         throw protocol_error("invalid EVENT message structure - SUBSCRIBED.Subscription must be an integer");
      }

      uint64_t subscription_id = msg[1].as<uint64_t>();

      typename handlers_t::iterator handlersBegin = m_handlers.lower_bound(subscription_id);
      typename handlers_t::iterator handlersEnd = m_handlers.upper_bound(subscription_id);

      if (handlersBegin != m_handlers.end()
              && handlersBegin != handlersEnd) {

         if (msg[2].type != msgpack::type::POSITIVE_INTEGER) {
            throw protocol_error("invalid EVENT message structure - PUBLISHED.Publication|id must be an integer");
         }

         //uint64_t publication_id = msg[2].as<uint64_t>();

         if (msg[3].type != msgpack::type::MAP) {
            throw protocol_error("invalid EVENT message structure - Details must be a dictionary");
         }

         anyvec args;
         anymap kwargs;

         if (msg.size() > 4) {

            if (msg[4].type != msgpack::type::ARRAY) {
               throw protocol_error("invalid EVENT message structure - EVENT.Arguments must be a list");
            }

            std::vector<msgpack::object> raw_args;
            msg[4].convert(&raw_args);
            unpack_anyvec(raw_args, args);

            if (msg.size() > 5) {

               if (msg[5].type != msgpack::type::MAP) {
                  throw protocol_error("invalid EVENT message structure - EVENT.Arguments must be a list");
               }

               std::map<std::string, msgpack::object> raw_kwargs;
               msg[5].convert(&raw_kwargs);
               unpack_anymap(raw_kwargs, kwargs);
            }
         }

         try {

            // now trigger the user supplied event handler ..
            //
            while (handlersBegin != handlersEnd) {
                (handlersBegin->second)(args, kwargs);
                ++handlersBegin;
            }

         } catch (...) {
            if (m_debug) {
               std::cerr << "Warning: event handler fired exception" << std::endl;
            }
         }

      } else {
         // silently swallow EVENT for non-existent subscription IDs.
         // We may have just unsubscribed, the this EVENT might be have
         // already been in-flight.
         if (m_debug) {
            std::cerr << "Skipping EVENT for non-existent subscription ID " << subscription_id << std::endl;
         }
      }
   }


   template<typename IStream, typename OStream>
   void session<IStream, OStream>::process_registered(const wamp_msg_t& msg) {

      // [REGISTERED, REGISTER.Request|id, Registration|id]

      if (msg.size() != 3) {
         throw protocol_error("invalid REGISTERED message structure - length must be 3");
      }

      if (msg[1].type != msgpack::type::POSITIVE_INTEGER) {
         throw protocol_error("invalid REGISTERED message structure - REGISTERED.Request must be an integer");
      }

      uint64_t request_id = msg[1].as<uint64_t>();

      typename register_requests_t::iterator register_request = m_register_requests.find(request_id);

      if (register_request != m_register_requests.end()) {

         if (msg[2].type != msgpack::type::POSITIVE_INTEGER) {
            throw protocol_error("invalid REGISTERED message structure - REGISTERED.Registration must be an integer");
         }

         uint64_t registration_id = msg[2].as<uint64_t>();

         m_endpoints[registration_id] = register_request->second.m_endpoint;

         register_request->second.m_res.set_value(registration(registration_id));

      } else {
         throw protocol_error("bogus REGISTERED message for non-pending request ID");
      }
   }


   template<typename IStream, typename OStream>
   void session<IStream, OStream>::receive_msg() {

      if (m_debug) {
         std::cerr << "RX preparing to receive message .." << std::endl;
      }

      // read 4 octets msg length prefix ..
      boost::asio::async_read(m_in,
         boost::asio::buffer(m_buffer_msg_len, sizeof(m_buffer_msg_len)),
         bind(&session<IStream, OStream>::got_msg_header, this, boost::asio::placeholders::error));
   }


   template<typename IStream, typename OStream>
   void session<IStream, OStream>::got_msg_header(const boost::system::error_code& error) {
      if (!error) {

         m_msg_len = ntohl(*((uint32_t*) &m_buffer_msg_len));

         if (m_debug) {
            std::cerr << "RX message (" << m_msg_len << " octets) ..." << std::endl;
         }

         // read actual message
         m_unpacker.reserve_buffer(m_msg_len);

         boost::asio::async_read(m_in,
            boost::asio::buffer(m_unpacker.buffer(), m_msg_len),
            bind(&session<IStream, OStream>::got_msg_body, this, boost::asio::placeholders::error));

      } else {
      }
   }


   template<typename IStream, typename OStream>
   void session<IStream, OStream>::got_msg_body(const boost::system::error_code& error) {
      if (!error) {

         if (m_debug) {
            std::cerr << "RX message received." << std::endl;
         }

         m_unpacker.buffer_consumed(m_msg_len);

         msgpack::unpacked result;

         while (m_unpacker.next(&result)) {

            msgpack::object obj(result.get());

            if (m_debug) {
               std::cerr << "RX WAMP message: " << obj << std::endl;
            }

            got_msg(obj);
         }

         if (!m_stopped) {
            receive_msg();
         }

      } else {

      }
   }


   template<typename IStream, typename OStream>
   void session<IStream, OStream>::got_msg(const msgpack::object& obj) {

      if (obj.type != msgpack::type::ARRAY) {
         throw protocol_error("invalid message structure - message is not an array");
      }

      wamp_msg_t msg;
      obj.convert(&msg);

      if (msg.size() < 1) {
         throw protocol_error("invalid message structure - missing message code");
      }

      if (msg[0].type != msgpack::type::POSITIVE_INTEGER) {
         throw protocol_error("invalid message code type - not an integer");
      }

      msg_code code = static_cast<msg_code> (msg[0].as<int>());

      switch (code) {
         case msg_code::HELLO:
            throw protocol_error("received HELLO message unexpected for WAMP client roles");

         case msg_code::WELCOME:
            process_welcome(msg);
            break;

         case msg_code::ABORT:
            // FIXME
            break;

         case msg_code::CHALLENGE:
            throw protocol_error("received CHALLENGE message - not implemented");

         case msg_code::AUTHENTICATE:
            throw protocol_error("received AUTHENTICATE message unexpected for WAMP client roles");

         case msg_code::GOODBYE:
            process_goodbye(msg);
            break;

         case msg_code::HEARTBEAT:
            // FIXME
            break;

         case msg_code::ERROR:
            process_error(msg);
            break;

         case msg_code::PUBLISH:
            throw protocol_error("received PUBLISH message unexpected for WAMP client roles");

         case msg_code::PUBLISHED:
            // FIXME
            break;

         case msg_code::SUBSCRIBE:
            throw protocol_error("received SUBSCRIBE message unexpected for WAMP client roles");

         case msg_code::SUBSCRIBED:
            process_subscribed(msg);
            break;

         case msg_code::UNSUBSCRIBE:
            throw protocol_error("received UNSUBSCRIBE message unexpected for WAMP client roles");

         case msg_code::UNSUBSCRIBED:
            // FIXME
            break;

         case msg_code::EVENT:
            process_event(msg);
            break;

         case msg_code::CALL:
            throw protocol_error("received CALL message unexpected for WAMP client roles");

         case msg_code::CANCEL:
            throw protocol_error("received CANCEL message unexpected for WAMP client roles");

         case msg_code::RESULT:
            process_call_result(msg);
            break;

         case msg_code::REGISTER:
            throw protocol_error("received REGISTER message unexpected for WAMP client roles");

         case msg_code::REGISTERED:
            process_registered(msg);
            break;

         case msg_code::UNREGISTER:
            throw protocol_error("received UNREGISTER message unexpected for WAMP client roles");

         case msg_code::UNREGISTERED:
            // FIXME
            break;

         case msg_code::INVOCATION:
            process_invocation(msg);
            break;

         case msg_code::INTERRUPT:
            throw protocol_error("received INTERRUPT message - not implemented");

         case msg_code::YIELD:
            throw protocol_error("received YIELD message unexpected for WAMP client roles");
      }
   }


   template<typename IStream, typename OStream>
   void session<IStream, OStream>::send() {

      if (!m_stopped) {
         if (m_debug) {
            std::cerr << "TX message (" << m_buffer.size() << " octets) ..." << std::endl;
         }

         // FIXME: rework this for queuing, async_write using gathered write
         //
         // boost::asio::write(m_out, std::vector<boost::asio::const_buffer>& out_vec, handler);

         // http://www.boost.org/doc/libs/1_55_0/doc/html/boost_asio/reference/const_buffer/const_buffer/overload2.html
         // http://www.boost.org/doc/libs/1_55_0/doc/html/boost_asio/reference/async_write/overload1.html

         std::size_t written = 0;

         // write message length prefix
         uint32_t len = htonl(m_buffer.size());
         written += boost::asio::write(m_out, boost::asio::buffer((char*) &len, sizeof(len)));

         // write actual serialized message
         written += boost::asio::write(m_out, boost::asio::buffer(m_buffer.data(), m_buffer.size()));

         if (m_debug) {
            std::cerr << "TX message sent (" << written << " / " << (sizeof(len) + m_buffer.size()) << " octets)" << std::endl;
         }
      } else {
         if (m_debug) {
            std::cerr << "TX message skipped since session stopped (" << m_buffer.size() << " octets)." << std::endl;
         }
      }

      // clear serialization buffer
      m_buffer.clear();
   }
}

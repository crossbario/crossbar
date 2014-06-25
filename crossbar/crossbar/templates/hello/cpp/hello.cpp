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

#include <string>
#include <iostream>

#include "autobahn.hpp"

#include <boost/asio.hpp>
#include <boost/version.hpp>

using namespace std;
using namespace boost;
using namespace autobahn;

using boost::asio::ip::tcp;


any add2(const anyvec& args, const anymap& kwargs) {

   cerr << "Someone is calling add2() .." << endl;

   uint64_t x = any_cast<uint64_t> (args[0]);
   uint64_t y = any_cast<uint64_t> (args[1]);
   return x + y;
}



int main () {

   cerr << "Running on " << BOOST_VERSION << endl;

   try {
      // ASIO service object
      //
      asio::io_service io;

      // the TCP socket we connect
      //
      tcp::socket socket(io);

      // connect to this server/port
      //
      tcp::resolver resolver(io);
      auto endpoint_iterator = resolver.resolve({"127.0.0.1", "8090"});

      // create a WAMP session that talks over TCP
      //
      bool debug = false;
      autobahn::session<tcp::socket,
                        tcp::socket> session(io, socket, socket, debug);

      // make sure the future returned from the session joining a realm (see below)
      // does not run out of scope (being destructed prematurely ..)
      //
      future<void> session_future;

      // now do an asynchronous connect ..
      //
      boost::asio::async_connect(socket, endpoint_iterator,

         // we either connected or an error happened during connect ..
         //
         [&](boost::system::error_code ec, tcp::resolver::iterator) {

            if (!ec) {
               cerr << "Connected to server" << endl;

               // start the WAMP session on the transport that has been connected
               //
               session.start();

               // join a realm with the WAMP session
               //
               session_future = session.join("realm1").then([&](future<uint64_t> s) {

                  cerr << "Session joined to realm with session ID " << s.get() << endl;

                  // register a free standing function for remoting
                  //
                  auto r1 = session.provide("com.myapp.cpp.add2", &add2);

                  r1.then([](future<registration> reg) {
                     cerr << "Registered with registration ID " << reg.get().id << endl;
                  }).wait();


                  // register a lambda for remoting
                  //
                  session.provide("com.myapp.cpp.square",

                     [](const anyvec& args, const anymap& kwargs) {

                        cerr << "Someone is calling my lambda function .." << endl;

                        uint64_t x = any_cast<uint64_t> (args[0]);
                        return x * x;
                     }
                  ).wait();
               });

            } else {
               cerr << "Could not connect to server: " << ec.message() << endl;
            }
         }
      );

      cerr << "Starting ASIO I/O loop .." << endl;

      io.run();

      cerr << "ASIO I/O loop ended" << endl;
   }
   catch (std::exception& e) {
      cerr << e.what() << endl;
      return 1;
   }
   return 0;
}

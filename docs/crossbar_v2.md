# Getting Started

To initialize a new Crossbar.io instance, create a *data directory* for the instance
 
	crossbar init <data directory>

and startup the instance.

    crossbar start <data directory>

The new Crossbar.io instance will automatically connect to the Crossbar.io Management Cloud and print an *activation code*

    ...
    Instance key generated.
    Instance started.
    ...
    Connected to Crossbar.io Management Cloud.
    Log into https://console.crossbar.io to configure your instance using
    the activation code: 981240

Now open and log into the management interface at
  
	https://console.crossbar.io

and select "Pair Instance", and enter the activation code.

The instance will log it's pairing

    Instance paired. Owner is 'user1'.
    Configured as router.
    Starting instance.
    Starting management service.
    Starting routing service.
    Starting WebSocket transport on port 443/TLS.

# Instance Types

1. **Router**
2. Bridges
   * **PostgreSQL Bridge**
   * Oracle Bridge
   * REST Bridge
   * SRDP Bridge

# Misc

    session, realm, action = 'create' | 'join' => application, role | None
    application, role => list of permissions
    permission: (topic pattern, [pub|sub|list]*) |
                (procedure pattern, [call|register|list]* 



 * http://permalink.gmane.org/gmane.comp.python.twisted/26395
 * http://freeprogrammersblog.vhex.net/post/linux-39-introduced-new-way-of-writing-socket-servers/2
 * https://lwn.net/Articles/542629/
 * http://stackoverflow.com/questions/10077745/twistedweb-on-multicore-multiprocessor
 * http://stackoverflow.com/questions/14388706/socket-options-so-reuseaddr-and-so-reuseport-how-do-they-differ-do-they-mean-t
 * http://stackoverflow.com/questions/12542700/setsockopt-before-connect-for-reactor-connecttcp


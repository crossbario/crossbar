title: Stream Testee
toc: [Documentation, Administration, Going to Production, Stream Testee]

# Stream Testee

Crossbar.io includes a *testee* (pseudo) transport, which just echo's back anything at a stream level (TCP or Unix domain socket).

**This feature is for debugging, development and benchmarking purposes.**

Here is an example configuration:

```json
{
   "workers": [
      {
         "type": "router",
         "transports": [
            {
               "type": "stream.testee",
               "endpoint": {
                  "type": "tcp",
                  "port": 9000,
                  "backlog": 1024
               }
            }
         ]
      }
   ]
}
```

Now you can connect e.g. via telnet to the host on port 9000.

## Configuration

option | description
---|---
**`id`** | ID of the transport within the running node (default: **`transport<N>`** where `N` is numbered automatically starting from `1`)
**`type`** | Type of transport - must be `"stream.testee"`.
**`endpoint`** | Listening endpoint for transport. See [Transport Endpoints](Transport Endpoints) for configuration
**`debug`** | Turn on debug logging for this transport instance (default: **`false`**).

---

## Results

These tests were performed on 2 boxes running FreeBSD 10.1 / x86-64:

```console
[oberstet@brummer1 ~]$ sysctl -a | egrep -i 'hw.model|hw.ncpu|hw.physmem'
hw.model: Intel(R) Xeon(R) CPU E3-1240 v3 @ 3.40GHz
hw.ncpu: 8
hw.physmem: 34276188160
```

The boxes are networked via 10GbE.

## Netperf

The following is a dump of performance results using [netperf](http://linux.die.net/man/1/netperf). [Here](https://gist.github.com/cgbystrom/985475) are some numbers to compare the results with.

### TCP_RR

Over **10GbE** to netserver:

```console
[oberstet@brummer2 ~]$ netperf -H 10.0.0.10 -t TCP_RR -l 60
TCP REQUEST/RESPONSE TEST from 0.0.0.0 (0.0.0.0) port 0 AF_INET to 10.0.0.10 () port 0 AF_INET : histogram : interval : dirty data : demo : first burst 0
Local /Remote
Socket Size   Request  Resp.   Elapsed  Trans.
Send   Recv   Size     Size    Time     Rate
bytes  Bytes  bytes    bytes   secs.    per sec

32768  65536  1        1       60.01    26851.95
32768  65536
```

Over **10GbE** to Crossbar.io / PyPy 2.4:

```console
[oberstet@brummer2 ~]$ netperf -N -H 10.0.0.10 -t TCP_RR -l 60 -- -P 9000
TCP REQUEST/RESPONSE TEST from 0.0.0.0 (0.0.0.0) port 9000 AF_INET to 10.0.0.10 () port 9000 AF_INET : no control : histogram : interval : dirty data : demo : first burst 0
Local /Remote
Socket Size   Request  Resp.   Elapsed  Trans.
Send   Recv   Size     Size    Time     Rate
bytes  Bytes  bytes    bytes   secs.    per sec

32768  65536  1        1       60.03    20524.63
0      0
```

Over **10GbE** to Crossbar.io / CPython 2.7.9:

```console
[oberstet@brummer2 ~]$ netperf -N -H 10.0.0.10 -t TCP_RR -l 60 -- -P 9000
TCP REQUEST/RESPONSE TEST from 0.0.0.0 (0.0.0.0) port 9000 AF_INET to 10.0.0.10 () port 9000 AF_INET : no control : histogram : interval : dirty data : demo : first burst 0
Local /Remote
Socket Size   Request  Resp.   Elapsed  Trans.
Send   Recv   Size     Size    Time     Rate
bytes  Bytes  bytes    bytes   secs.    per sec

32768  65536  1        1       60.01    13342.51
0      0
```

Over **loopback** to netserver:

```console
[oberstet@brummer1 ~]$ netperf -H 127.0.0.1 -t TCP_RR -l 60
TCP REQUEST/RESPONSE TEST from 0.0.0.0 (0.0.0.0) port 0 AF_INET to 127.0.0.1 () port 0 AF_INET : histogram : interval : dirty data : demo : first burst 0
Local /Remote
Socket Size   Request  Resp.   Elapsed  Trans.
Send   Recv   Size     Size    Time     Rate
bytes  Bytes  bytes    bytes   secs.    per sec

32768  65536  1        1       60.02    114822.69
32768  65536
```

Over **loopback** to Crossbar.io / PyPy 2.4:

```console
[oberstet@brummer1 ~]$ netperf -N -H 127.0.0.1 -t TCP_RR -l 60 -- -P 9000
TCP REQUEST/RESPONSE TEST from 0.0.0.0 (0.0.0.0) port 9000 AF_INET to 127.0.0.1 () port 9000 AF_IN                                                                               ET : no control : histogram : interval : dirty data : demo : first burst 0
Local /Remote
Socket Size   Request  Resp.   Elapsed  Trans.
Send   Recv   Size     Size    Time     Rate
bytes  Bytes  bytes    bytes   secs.    per sec

32768  65536  1        1       60.02    63572.31
0      0
```

Over **loopback** to Crossbar.io / CPython 2.7.9:

```console
[oberstet@brummer1 ~]$ netperf -N -H 127.0.0.1 -t TCP_RR -l 60 -- -P 9000
TCP REQUEST/RESPONSE TEST from 0.0.0.0 (0.0.0.0) port 9000 AF_INET to 127.0.0.1 () port 9000 AF_INET :                                                                            no control : histogram : interval : dirty data : demo : first burst 0
Local /Remote
Socket Size   Request  Resp.   Elapsed  Trans.
Send   Recv   Size     Size    Time     Rate
bytes  Bytes  bytes    bytes   secs.    per sec

32768  65536  1        1       60.00    25266.67
0      0
```

### TCP_STREAM

Over **10GbE** to netserver:

```console
[oberstet@brummer2 ~]$ netperf -H 10.0.0.10 -t TCP_STREAM -l 60
TCP STREAM TEST from 0.0.0.0 (0.0.0.0) port 0 AF_INET to 10.0.0.10 () port 0 AF_INET : histogram : interval : dirty data : demo
Recv   Send    Send
Socket Socket  Message  Elapsed
Size   Size    Size     Time     Throughput
bytes  bytes   bytes    secs.    10^6bits/sec

 65536  32768  32768    60.00    9918.16
```

Over **10GbE** to Crossbar.io / PyPy 2.4:

```console
[oberstet@brummer2 ~]$ netperf -N -H 10.0.0.10 -t TCP_STREAM -l 60 -- -P 9000
TCP STREAM TEST from 0.0.0.0 (0.0.0.0) port 9000 AF_INET to 10.0.0.10 () port 9000 AF_INET : no control : histogram : interval : dirty data : demo
Recv   Send    Send
Socket Socket  Message  Elapsed
Size   Size    Size     Time     Throughput
bytes  bytes   bytes    secs.    10^6bits/sec

     0  32768  32768    60.00    1202.82
```

Over **10GbE** to Crossbar.io / CPython 2.7.9:

```console
[oberstet@brummer2 ~]$ netperf -N -H 10.0.0.10 -t TCP_STREAM -l 60 -- -P 9000
TCP STREAM TEST from 0.0.0.0 (0.0.0.0) port 9000 AF_INET to 10.0.0.10 () port 9000 AF_INET : no control : histogram : interval : dirty data : demo
Recv   Send    Send
Socket Socket  Message  Elapsed
Size   Size    Size     Time     Throughput
bytes  bytes   bytes    secs.    10^6bits/sec

     0  32768  32768    60.02    1368.46
```

Over **loopback** to netserver:

```console
[oberstet@brummer1 ~]$ netperf -H 127.0.0.1 -t TCP_STREAM -l 60
TCP STREAM TEST from 0.0.0.0 (0.0.0.0) port 0 AF_INET to 127.0.0.1 () port 0 AF_INET : histogram : interval : dirty data : demo
Recv   Send    Send
Socket Socket  Message  Elapsed
Size   Size    Size     Time     Throughput
bytes  bytes   bytes    secs.    10^6bits/sec

 65536  32768  32768    60.01    46675.42
```

Over **loopback** to Crossbar.io / PyPy 2.4:

```console
[oberstet@brummer1 ~]$ netperf -N -H 127.0.0.1 -t TCP_STREAM -l 10 -- -P 9000
TCP STREAM TEST from 0.0.0.0 (0.0.0.0) port 9000 AF_INET to 127.0.0.1 () port 9000                                                                                    AF_INET : no control : histogram : interval : dirty data : demo
Recv   Send    Send
Socket Socket  Message  Elapsed
Size   Size    Size     Time     Throughput
bytes  bytes   bytes    secs.    10^6bits/sec

     0  32768  32768    10.04    11420.84
```

Over **loopback** to Crossbar.io / CPython 2.7.9:

```console
[oberstet@brummer1 ~]$ netperf -N -H 127.0.0.1 -t TCP_STREAM -l 10 -- -P 9000
TCP STREAM TEST from 0.0.0.0 (0.0.0.0) port 9000 AF_INET to 127.0.0.1 () port 9000 AF_INET : no control : histogram : interval : dirty data : demo
Recv   Send    Send
Socket Socket  Message  Elapsed
Size   Size    Size     Time     Throughput
bytes  bytes   bytes    secs.    10^6bits/sec

     0  32768  32768    10.02    10335.18
```

### TCP_CRR

Over **10GbE** to netserver:

```console
[oberstet@brummer2 ~]$ netperf -H 10.0.0.10 -t TCP_CRR -l 60
TCP Connect/Request/Response TEST from 0.0.0.0 (0.0.0.0) port 0 AF_INET to 10.0.0.10 () port 0 AF_INET : histogram : interval : dirty data : demo
Local /Remote
Socket Size   Request  Resp.   Elapsed  Trans.
Send   Recv   Size     Size    Time     Rate
bytes  Bytes  bytes    bytes   secs.    per sec

32768  65536  1        1       60.02    13206.10
32768  65536
```

Over **loopback** to netserver:

```console
[oberstet@brummer1 ~]$ netperf -H 127.0.0.1 -t TCP_CRR -l 60
TCP Connect/Request/Response TEST from 0.0.0.0 (0.0.0.0) port 0 AF_INET to 127.0.0.1 () port 0 AF_INET : histogram : interval : dirty data : demo
Local /Remote
Socket Size   Request  Resp.   Elapsed  Trans.
Send   Recv   Size     Size    Time     Rate
bytes  Bytes  bytes    bytes   secs.    per sec

32768  65536  1        1       60.04    45586.91
32768  65536
```

## Accept Rate

These tests were performed on a notebook running Windows 7.

* http://stackoverflow.com/a/1824817/884770
* http://www.lenholgate.com/blog/2005/11/windows-tcpip-server-performance.html

```
oberstet@THINKPAD-T410S /c/Temp
$ ./EchoServerTest.exe -server 127.0.0.1 -port 9000 -connections 60000 -connectionBatchSize 1000 -connectionBatchDelay 600 -hold -pause
Creating 60000 connections
1000 connections created
2000 connections created
...
59000 connections created
60000 connections created
All connections in progress
All connections complete in 47545ms
60000 established. 0 failed.
Press return to close connections
```

## Resources

* [Why is TCP accept performance so bad under Xen?](http://serverfault.com/questions/272483/why-is-tcp-accept-performance-so-bad-under-xen)
* [Why virtualization reduces network performance](https://news.ycombinator.com/item?id=2574702)

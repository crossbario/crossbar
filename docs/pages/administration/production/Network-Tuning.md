[Documentation](.) > [Administration](Administration) > [Going to Production](Going to Production) > Network Tuning

# Network Tuning

## Linux

Linux TCP networking is tuned as in the following. This (or similar) is *required*, since we are really pushing the system.

Add the following to the end of `/etc/sysctl.conf` and do `sysctl -p`:

	net.core.somaxconn = 8192
	net.ipv4.tcp_max_orphans = 8192
	net.ipv4.tcp_max_syn_backlog = 8192
	net.core.netdev_max_backlog = 262144

	net.ipv4.ip_local_port_range = 1024 65535

	#net.ipv4.tcp_low_latency = 1
	#net.ipv4.tcp_window_scaling = 0
	#net.ipv4.tcp_syncookies = 0

	fs.file-max = 16777216
	fs.pipe-max-size = 134217728

Further system level tuning:

Modify `/etc/security/limits.conf` for the following

	# wildcard does not work for root, but for all other users
	*               soft     nofile           1048576
	*               hard     nofile           1048576
	# settings should also apply to root
	root            soft     nofile           1048576
	root            hard     nofile           1048576

and add the following line

	session required pam_limits.so

to both of these files at the end:

	/etc/pam.d/common-session
	/etc/pam.d/common-session-noninteractive

Reboot (or at least I don't know how to make it immediate without reboot).

Check that you actually got large (`1048576`) FD limit:

	ulimit -n

Probably also check that above `sysctl` settings actually are in place (`sysctl -a | grep ..` or such). I am paranoid.


## FreeBSD

Here are a couple of background articles:

* https://pleiades.ucsc.edu/hyades/FreeBSD_Network_Tuning
* https://blog.whatsapp.com/196/1-million-is-so-2011?
* https://wiki.freebsd.org/NetworkPerformanceTuning
* https://calomel.org/freebsd_network_tuning.html
* https://www.freebsd.org/doc/handbook/configtuning-kernel-limits.html


Add the following to `/boot/loader.conf`:

```
boot_verbose="YES"

# increase max. open sockets / files
kern.ipc.maxsockets=2400000
kern.maxfiles=3000000
kern.maxfilesperproc=2700000
kern.maxproc=16384

# tune up for high connection numbers
net.inet.tcp.tcbhashsize=524288
net.inet.tcp.hostcache.hashsize=4096
net.inet.tcp.hostcache.cachelimit=131072
net.inet.tcp.hostcache.bucketlimit=120

# misc
kern.hwpmc.nbuffers=32
kern.hwpmc.nsamples=64
kern.timecounter.smp_tsc=1
kern.random.sys.harvest.ethernet=0
```

Add the following to `/etc/sysctl.conf`

```
# increase range of ephemeral ports
net.inet.ip.portrange.first=1024
net.inet.ip.portrange.last=65535
net.inet.ip.portrange.randomized=0

# allow binding of ports <1024 by non-root processes
net.inet.ip.portrange.reservedhigh=0

# increase backlog
kern.ipc.somaxconn=32768

# set to 128MB
kern.ipc.maxsockbuf=134217728

# set autotuning maximum to 128MB too
net.inet.tcp.sendbuf_max=134217728
net.inet.tcp.recvbuf_max=134217728

# enable send/recv autotuning
net.inet.tcp.sendbuf_auto=1
net.inet.tcp.recvbuf_auto=1

# increase autotuning step size
net.inet.tcp.sendbuf_inc=16384
net.inet.tcp.recvbuf_inc=16384
```

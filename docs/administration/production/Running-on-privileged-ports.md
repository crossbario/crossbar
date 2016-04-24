[Documentation](.) > [Administration](Administration) > [Going to Production](Going to Production) > Running on Privileged Ports

# Running on Privileged Ports

For production, you might want to:

* make Crossbar.io listen on ports 80/443, which are the standard ports for both HTTP(S) and (secure) WebSocket
* run Crossbar.io under a dedicated non-root service user

However, Unix-like operating system by default do not allow programs that run non-root to listen on TCP/IP ports <1024.

There are different ways of achieving above, and those ways depend on the OS flavor you use (Linux, FreeBSD, etc).

## Linux

Here we describe one way that works using [Linux Capabilities](http://linux.die.net/man/7/capabilities) on kernels >= 2.6.24.

Install `libcap2`:

```
sudo apt-get install libcap2-bin
```

Now allow the Crossbar.io and PyPy executables to bind privileged ports:

```
sudo setcap cap_net_bind_service=+ep `which crossbar`
sudo setcap cap_net_bind_service=+ep `which pypy`
```

> Note that with above, any user on the host that is able to execute PyPy (or Crossbar) will be able to bind privileged ports *with any Python script*. If the host is used by others as well, you might want to restrict *execution permissions* on the binaries again.

> Also note that using capabilities will disable searching directories for shared libraries from `LD_LIBRARY_PATH`. See [here](http://stackoverflow.com/questions/9843178/linux-capabilities-setcap-seems-to-disable-ld-library-path)
>

## FreeBSD

On FreeBSD, the range of privileged ports which only may be opened by root-owned processes may be modified by the `net.inet.ip.portrange.reservedlow` and `net.inet.ip.portrange.reservedhigh` **sysctl** settings.

The values default to the traditional range, `0` through `IPPORT_RESERVED - 1` (`0` through `1023`), respectively.

To temporarily allow non-root process to bind ports <1024:

    sysctl net.inet.ip.portrange.reservedhigh=0

To make that setting persist reboots:

    echo "net.inet.ip.portrange.reservedhigh=0" >> /etc/sysctl.conf

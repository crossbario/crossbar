import json

txt = """{
    "Id": "5eca2ece88c8aa2de2507466ff1dd9ec7496169002d2942a45c42c2ad3b79676",
    "Created": "2019-06-10T10:29:00.581179505Z",
    "Path": "/bin/bash",
    "Args": [],
    "State": {
        "Status": "running",
        "Running": true,
        "Paused": false,
        "Restarting": false,
        "OOMKilled": false,
        "Dead": false,
        "Pid": 3793,
        "ExitCode": 0,
        "Error": "",
        "StartedAt": "2019-06-10T10:29:02.159524647Z",
        "FinishedAt": "0001-01-01T00:00:00Z"
    },
    "Image": "sha256:d131e0fa2585a7efbfb187f70d648aa50e251d9d3b7031edf4730ca6154e221e",
    "ResolvConfPath": "/var/lib/docker/containers/5eca2ece88c8aa2de2507466ff1dd9ec7496169002d2942a45c42c2ad3b79676/resolv.conf",
    "HostnamePath": "/var/lib/docker/containers/5eca2ece88c8aa2de2507466ff1dd9ec7496169002d2942a45c42c2ad3b79676/hostname",
    "HostsPath": "/var/lib/docker/containers/5eca2ece88c8aa2de2507466ff1dd9ec7496169002d2942a45c42c2ad3b79676/hosts",
    "LogPath": "/var/lib/docker/containers/5eca2ece88c8aa2de2507466ff1dd9ec7496169002d2942a45c42c2ad3b79676/5eca2ece88c8aa2de2507466ff1dd9ec7496169002d2942a45c42c2ad3b79676-json.log",
    "Name": "/mytest",
    "RestartCount": 0,
    "Driver": "overlay2",
    "Platform": "linux",
    "MountLabel": "",
    "ProcessLabel": "",
    "AppArmorProfile": "docker-default",
    "ExecIDs": null,
    "HostConfig": {
        "Binds": [
            "/home/gareth/target:/app"
        ],
        "ContainerIDFile": "",
        "LogConfig": {
            "Type": "json-file",
            "Config": {
                "max-file": "3",
                "max-size": "10m"
            }
        },
        "NetworkMode": "default",
        "PortBindings": {},
        "RestartPolicy": {
            "Name": "no",
            "MaximumRetryCount": 0
        },
        "AutoRemove": false,
        "VolumeDriver": "",
        "VolumesFrom": null,
        "CapAdd": null,
        "CapDrop": null,
        "Dns": [],
        "DnsOptions": [],
        "DnsSearch": [],
        "ExtraHosts": null,
        "GroupAdd": null,
        "IpcMode": "shareable",
        "Cgroup": "",
        "Links": null,
        "OomScoreAdj": 0,
        "PidMode": "",
        "Privileged": false,
        "PublishAllPorts": false,
        "ReadonlyRootfs": false,
        "SecurityOpt": null,
        "UTSMode": "",
        "UsernsMode": "",
        "ShmSize": 67108864,
        "Runtime": "runc",
        "ConsoleSize": [
            0,
            0
        ],
        "Isolation": "",
        "CpuShares": 0,
        "Memory": 0,
        "NanoCpus": 0,
        "CgroupParent": "",
        "BlkioWeight": 0,
        "BlkioWeightDevice": [],
        "BlkioDeviceReadBps": null,
        "BlkioDeviceWriteBps": null,
        "BlkioDeviceReadIOps": null,
        "BlkioDeviceWriteIOps": null,
        "CpuPeriod": 0,
        "CpuQuota": 0,
        "CpuRealtimePeriod": 0,
        "CpuRealtimeRuntime": 0,
        "CpusetCpus": "",
        "CpusetMems": "",
        "Devices": [],
        "DeviceCgroupRules": null,
        "DiskQuota": 0,
        "KernelMemory": 0,
        "MemoryReservation": 0,
        "MemorySwap": 0,
        "MemorySwappiness": null,
        "OomKillDisable": false,
        "PidsLimit": 0,
        "Ulimits": null,
        "CpuCount": 0,
        "CpuPercent": 0,
        "IOMaximumIOps": 0,
        "IOMaximumBandwidth": 0,
        "MaskedPaths": [
            "/proc/asound",
            "/proc/acpi",
            "/proc/kcore",
            "/proc/keys",
            "/proc/latency_stats",
            "/proc/timer_list",
            "/proc/timer_stats",
            "/proc/sched_debug",
            "/proc/scsi",
            "/sys/firmware"
        ],
        "ReadonlyPaths": [
            "/proc/bus",
            "/proc/fs",
            "/proc/irq",
            "/proc/sys",
            "/proc/sysrq-trigger"
        ]
    },
    "GraphDriver": {
        "Data": {
            "LowerDir": "/var/lib/docker/overlay2/b27734ba84d0f0348c009649f0214309068811f78b593dd591cb40f6d4bc248f-init/diff:/var/lib/docker/overlay2/c058f6c7adc6825f992d95416cae4712d934d205304752df97af59cbe5cb33ba/diff:/var/lib/docker/overlay2/c8943979c4f38bb7f70d75c5c4f3c8731efb186007cc59ae48af40f08122ac19/diff:/var/lib/docker/overlay2/63d70bc188349a336d61c10e8e434e20d01d9e3abbb769fd6c6023d6e4e5d753/diff:/var/lib/docker/overlay2/0d8b5965209095e6a93154ba0b24077e26b2e580ce17a6a2e496dd5454554e8b/diff",
            "MergedDir": "/var/lib/docker/overlay2/b27734ba84d0f0348c009649f0214309068811f78b593dd591cb40f6d4bc248f/merged",
            "UpperDir": "/var/lib/docker/overlay2/b27734ba84d0f0348c009649f0214309068811f78b593dd591cb40f6d4bc248f/diff",
            "WorkDir": "/var/lib/docker/overlay2/b27734ba84d0f0348c009649f0214309068811f78b593dd591cb40f6d4bc248f/work"
        },
        "Name": "overlay2"
    },
    "Mounts": [
        {
            "Type": "bind",
            "Source": "/var/lib/docker/root",
            "Destination": "/app",
            "Mode": "",
            "RW": true,
            "Propagation": "rprivate"
        },
        {
            "Type": "bind",
            "Source": "/var/lib/docker/home",
            "Destination": "/home",
            "Mode": "",
            "RW": true,
            "Propagation": "rprivate"
        }
    ],
    "Config": {
        "Hostname": "5eca2ece88c8",
        "Domainname": "",
        "User": "",
        "AttachStdin": false,
        "AttachStdout": false,
        "AttachStderr": false,
        "Tty": true,
        "OpenStdin": true,
        "StdinOnce": false,
        "Env": [
            "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        ],
        "Cmd": [
            "/bin/bash"
        ],
        "ArgsEscaped": true,
        "Image": "ubuntu:latest",
        "Volumes": null,
        "WorkingDir": "",
        "Entrypoint": null,
        "OnBuild": null,
        "Labels": {}
    },
    "NetworkSettings": {
        "Bridge": "",
        "SandboxID": "ae1271737d5b06c641f839b2184bdc312b46c0eed9180c3c244a832331f261fb",
        "HairpinMode": false,
        "LinkLocalIPv6Address": "",
        "LinkLocalIPv6PrefixLen": 0,
        "Ports": {},
        "SandboxKey": "/var/run/docker/netns/ae1271737d5b",
        "SecondaryIPAddresses": null,
        "SecondaryIPv6Addresses": null,
        "EndpointID": "9268246fe82700a8608484f8602989412000ce0f07ad0998ac9611670c0cff5b",
        "Gateway": "172.17.0.1",
        "GlobalIPv6Address": "",
        "GlobalIPv6PrefixLen": 0,
        "IPAddress": "172.17.0.4",
        "IPPrefixLen": 16,
        "IPv6Gateway": "",
        "MacAddress": "02:42:ac:11:00:04",
        "Networks": {
            "bridge": {
                "IPAMConfig": null,
                "Links": null,
                "Aliases": null,
                "NetworkID": "300d1064422714e93431c91e6abf32ac5e2c51a1f6ca5e69e3017187c2a7aa5d",
                "EndpointID": "9268246fe82700a8608484f8602989412000ce0f07ad0998ac9611670c0cff5b",
                "Gateway": "172.17.0.1",
                "IPAddress": "172.17.0.4",
                "IPPrefixLen": 16,
                "IPv6Gateway": "",
                "GlobalIPv6Address": "",
                "GlobalIPv6PrefixLen": 0,
                "MacAddress": "02:42:ac:11:00:04",
                "DriverOpts": null
            }
        }
    }
}"""
my_json = json.loads(txt)

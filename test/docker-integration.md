# Docker integration

## Show Docker details

```
(cpy373_1) oberstet@intel-nuci7:~/scm/crossbario/crossbarfx$ crossbarfx shell --realm mrealm1 show docker node1

{'Architecture': 'x86_64',
 'BridgeNfIp6tables': True,
 'BridgeNfIptables': True,
 'CPUSet': True,
 'CPUShares': True,
 'CgroupDriver': 'cgroupfs',
...
 'SystemTime': '2019-05-13T09:25:34.280230589+02:00',
 'Warnings': ['WARNING: No swap limit support']}
```

## Listing images

```
(cpy373_1) oberstet@intel-nuci7:~/scm/crossbario/crossbarfx$ crossbarfx shell --realm mrealm1 list nodes

['4752c752-a128-4ae4-a041-84208eabe49d']
(cpy373_1) oberstet@intel-nuci7:~/scm/crossbario/crossbarfx$ docker images
REPOSITORY              TAG                 IMAGE ID            CREATED             SIZE
ubuntu                  latest              d131e0fa2585        2 weeks ago         102MB
crossbario/crossbarfx   latest              4bbb66b3e0c6        2 months ago        502MB
(cpy373_1) oberstet@intel-nuci7:~/scm/crossbario/crossbarfx$ crossbarfx shell --realm mrealm1 list docker-images node1

['sha256:d131e0fa2585a7efbfb187f70d648aa50e251d9d3b7031edf4730ca6154e221e',
 'sha256:4bbb66b3e0c6f7fb5f1e254f8976c35a7fcf7ea82cd7e3885d1ab7702eedece1']
```

## Show image details

```
(cpy373_1) oberstet@intel-nuci7:~/scm/crossbario/crossbarfx$ crossbarfx shell --realm mrealm1 show docker-image node1 4bbb66

{'Architecture': 'amd64',
 'Author': 'The Crossbar.io Project <support@crossbario.com>',
 'Comment': '',
 'Config': {'ArgsEscaped': True,
            'AttachStderr': False,
            'AttachStdin': False,
            'AttachStdout': False,
            'Cmd': ['edge',
                    'start',
                    '--cbdir',
                    '/node/.crossbar',
                    '--loglevel',
                    'info'],
...
 'Size': 501562522,
 'VirtualSize': 501562522}
(cpy373_1) oberstet@intel-nuci7:~/scm/crossbario/crossbarfx$ 
```

## Listing containers

```
(cpy373_1) oberstet@intel-nuci7:~/scm/crossbario/crossbarfx$ crossbarfx shell --realm mrealm1 list docker-containers node1

['02137443e9568c2c5e2b5a0c994da4c4009f797207f8123dcbe77464cfead1f5',
 'a4550e94128736ce767c60c85c420382895e7d3a2aee398f6e623a8f6e50982c',
 'ca456feb41b5e995f493bb36180e13a8425b17d61201b2d7c1c38ac4f869017d',
 'f254963a5bee60e66ed314cb0cce0df29223e6e48497578d086f43d0de983f3f']
```

## Show container details

```
(cpy373_1) oberstet@intel-nuci7:~/scm/crossbario/crossbarfx$ crossbarfx shell --realm mrealm1 show docker-container node1 02137443e9

{'AppArmorProfile': 'docker-default',
 'Args': [],
 'Config': {'AttachStderr': True,
            'AttachStdin': True,
            'AttachStdout': True,
            'Cmd': ['/bin/bash'],
            'Domainname': '',
            'Entrypoint': None,
            'Env': ['PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'],
            'Hostname': '02137443e956',
            'Image': 'ubuntu',
...
           'Status': 'exited'}}
(cpy373_1) oberstet@intel-nuci7:~/scm/crossbario/crossbarfx$ 
```

## Creating containers

```
(cpy373_1) oberstet@intel-nuci7:~/scm/crossbario/crossbarfx$ crossbarfx shell --realm mrealm1 create docker-container node1 d131e0fa258 --config {}

{'id': '050c89a9ca0b7b930ad68d3cd7d93911510f426beddbea97881f907e974314ef'}
```

Eg:

```
(cpy373_1) oberstet@intel-nuci7:~/scm/crossbario/crossbarfx$ crossbarfx shell --realm mrealm1 create docker-container node1 d131e0fa258 --config {}

{'id': '050c89a9ca0b7b930ad68d3cd7d93911510f426beddbea97881f907e974314ef'}
(cpy373_1) oberstet@intel-nuci7:~/scm/crossbario/crossbarfx$ crossbarfx shell --realm mrealm1 list docker-images node1

['sha256:d131e0fa2585a7efbfb187f70d648aa50e251d9d3b7031edf4730ca6154e221e',
 'sha256:4bbb66b3e0c6f7fb5f1e254f8976c35a7fcf7ea82cd7e3885d1ab7702eedece1']
(cpy373_1) oberstet@intel-nuci7:~/scm/crossbario/crossbarfx$ crossbarfx shell --realm mrealm1 list docker-containers node1

['050c89a9ca0b7b930ad68d3cd7d93911510f426beddbea97881f907e974314ef',
 '02137443e9568c2c5e2b5a0c994da4c4009f797207f8123dcbe77464cfead1f5',
 'a4550e94128736ce767c60c85c420382895e7d3a2aee398f6e623a8f6e50982c',
 'ca456feb41b5e995f493bb36180e13a8425b17d61201b2d7c1c38ac4f869017d',
 'f254963a5bee60e66ed314cb0cce0df29223e6e48497578d086f43d0de983f3f']
(cpy373_1) oberstet@intel-nuci7:~/scm/crossbario/crossbarfx$ docker ps
CONTAINER ID        IMAGE               COMMAND             CREATED             STATUS              PORTS               NAMES
(cpy373_1) oberstet@intel-nuci7:~/scm/crossbario/crossbarfx$ docker ps -a
CONTAINER ID        IMAGE               COMMAND                  CREATED             STATUS                      PORTS               NAMES
050c89a9ca0b        d131e0fa258         "/bin/bash"              33 seconds ago      Created                                         naughty_brown
02137443e956        ubuntu              "/bin/bash"              41 minutes ago      Exited (0) 41 minutes ago                       test1
a4550e941287        ubuntu              "--name test1 sh"        41 minutes ago      Created                                         vigorous_snyder
ca456feb41b5        ubuntu              "--name test1 bash"      42 minutes ago      Created                                         boring_engelbart
f254963a5bee        ubuntu              "--name test1 /bin/b…"   42 minutes ago      Created                                         condescending_lehmann
```

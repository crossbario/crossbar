#!/usr/bin/env bash

orig_path=$(pwd)
parent_path=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )

# CROSSBAR_FABRIC_URL=ws://localhost:9000/ws
# CROSSBAR_FABRIC_SUPERUSER=${HOME}/.crossbarfx/default.pub

echo "Using CROSSBAR_FABRIC_URL=${CROSSBAR_FABRIC_URL}"
echo "Using CROSSBAR_FABRIC_SUPERUSER=${CROSSBAR_FABRIC_SUPERUSER}"

crossbarfx shell init --yes
crossbarfx master start --cbdir ./test/cfc/.crossbar &
sleep 5

crossbarfx shell init --yes
crossbarfx shell create mrealm mrealm1
crossbarfx shell pair node ./test/cf1/.crossbar/key.pub mrealm1 node1
crossbarfx shell pair node ./test/cf2/.crossbar/key.pub mrealm1 node2
crossbarfx shell pair node ./test/cf3/.crossbar/key.pub mrealm1 node3
crossbarfx edge start --cbdir ./test/cf1/.crossbar &
crossbarfx edge start --cbdir ./test/cf2/.crossbar &
crossbarfx edge start --cbdir ./test/cf3/.crossbar &
sleep 2

crossbarfx shell --realm mrealm1 list nodes
sleep 1

cd "$parent_path"

# [x] test/management/ex_cpu_affinity.py
# [x] test/management/ex_docker.py
# [x] test/management/ex_global_api.py
# [x] test/management/ex_global_status.py
# [x] test/management/ex_list_nodes.py
# [x] test/management/ex_list_sessions.py
# [x] test/management/ex_list_workers.py
# [x] test/management/ex_process_stats.py
# [x] test/management/ex_start_container.py
# [x] test/management/ex_start_guest.py
# [x] test/management/ex_start_router.py
# [x] test/management/ex_start_web_services.py
# [x] test/management/ex_status.py
# [x] test/management/ex_tracing.py
# [x] test/management/ex_worker_log.py

# [ ] test/management/ex_list_subs_regs.py
# [ ] test/management/ex_monitor_sessions.py

# [ ] test/management/ex_start_proxy.py
# [ ] test/management/ex_webcluster.py

# [ ] test/management/ex_tracing_actions.py
# [ ] test/management/ex_tracing_monitor_actions.py
# [ ] test/management/ex_tracing_monitor_by_action.py
# [ ] test/management/ex_tracing_monitor.py
# [ ] test/management/tracing/ex_manage_trace.py
# [ ] test/management/tracing/ex_monitor_trace.py

python3 -u ex_global_status.py --url "ws://localhost:9000/ws" --realm "com.crossbario.fabric" --keyfile ${HOME}/.crossbarfx/default.priv
python3 -u ex_global_api.py --url "ws://localhost:9000/ws" --realm "com.crossbario.fabric" --keyfile ${HOME}/.crossbarfx/default.priv

python3 -u ex_status.py --url "ws://localhost:9000/ws" --realm "mrealm1" --keyfile ${HOME}/.crossbarfx/default.priv
python3 -u ex_cpu_affinity.py --url "ws://localhost:9000/ws" --realm "mrealm1" --keyfile ${HOME}/.crossbarfx/default.priv

python3 -u ex_list_nodes.py --url "ws://localhost:9000/ws" --realm "mrealm1" --keyfile ${HOME}/.crossbarfx/default.priv
python3 -u ex_list_sessions.py --url "ws://localhost:9000/ws" --realm "mrealm1" --keyfile ${HOME}/.crossbarfx/default.priv
python3 -u ex_list_workers.py --url "ws://localhost:9000/ws" --realm "mrealm1" --keyfile ${HOME}/.crossbarfx/default.priv
# python3 -u ex_list_subs_regs.py --url "ws://localhost:9000/ws" --realm "mrealm1" --keyfile ${HOME}/.crossbarfx/default.priv

python3 -u ex_start_router.py --url "ws://localhost:9000/ws" --realm "mrealm1" --keyfile ${HOME}/.crossbarfx/default.priv
python3 -u ex_start_container.py --url "ws://localhost:9000/ws" --realm "mrealm1" --keyfile ${HOME}/.crossbarfx/default.priv
python3 -u ex_start_guest.py --url "ws://localhost:9000/ws" --realm "mrealm1" --keyfile ${HOME}/.crossbarfx/default.priv
python3 -u ex_start_web_services.py --url "ws://localhost:9000/ws" --realm "mrealm1" --keyfile ${HOME}/.crossbarfx/default.priv

python3 -u ex_worker_log.py --url "ws://localhost:9000/ws" --realm "mrealm1" --keyfile ${HOME}/.crossbarfx/default.priv
python3 -u ex_process_stats.py --url "ws://localhost:9000/ws" --realm "mrealm1" --keyfile ${HOME}/.crossbarfx/default.priv

python3 -u ex_docker.py --url "ws://localhost:9000/ws" --realm "mrealm1" --keyfile ${HOME}/.crossbarfx/default.priv

#python3 -u ex_start_proxy.py --url "ws://localhost:9000/ws" --realm "mrealm1" --keyfile ${HOME}/.crossbarfx/default.priv
python3 -u ex_tracing.py --url "ws://localhost:9000/ws" --realm "mrealm1" --keyfile ${HOME}/.crossbarfx/default.priv
#python3 -u ex_webcluster.py --url "ws://localhost:9000/ws" --realm "mrealm1" --keyfile ${HOME}/.crossbarfx/default.priv

# PROBLEMATIC: python3 -u ex_monitor_sessions.py --url "ws://localhost:9000/ws" --realm "mrealm1" --keyfile ${HOME}/.crossbarfx/default.priv

cd "$orig_path"

crossbarfx edge stop --cbdir ./test/cf1/.crossbar
crossbarfx edge stop --cbdir ./test/cf2/.crossbar
crossbarfx edge stop --cbdir ./test/cf3/.crossbar

crossbarfx master stop --cbdir ./test/cfc/.crossbar

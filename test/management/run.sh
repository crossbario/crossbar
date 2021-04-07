#!/usr/bin/env bash

orig_path=$(pwd)
parent_path=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )

# CROSSBAR_FABRIC_URL=ws://localhost:9000/ws
# CROSSBAR_FABRIC_SUPERUSER=${HOME}/.crossbar/default.pub

echo "Using CROSSBAR_FABRIC_URL=${CROSSBAR_FABRIC_URL}"
echo "Using CROSSBAR_FABRIC_SUPERUSER=${CROSSBAR_FABRIC_SUPERUSER}"

crossbar shell init --yes
crossbar master start --cbdir ./test/cfc/.crossbar &
sleep 5

crossbar shell init --yes
crossbar shell create mrealm mrealm1
crossbar shell pair node ./test/cf1/.crossbar/key.pub mrealm1 node1
crossbar shell pair node ./test/cf2/.crossbar/key.pub mrealm1 node2
crossbar shell pair node ./test/cf3/.crossbar/key.pub mrealm1 node3
crossbar edge start --cbdir ./test/cf1/.crossbar &
crossbar edge start --cbdir ./test/cf2/.crossbar &
crossbar edge start --cbdir ./test/cf3/.crossbar &
sleep 2

crossbar shell --realm mrealm1 list nodes
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

python3 -u ex_global_status.py --url "ws://localhost:9000/ws" --realm "com.crossbario.fabric" --keyfile ${HOME}/.crossbar/default.priv
python3 -u ex_global_api.py --url "ws://localhost:9000/ws" --realm "com.crossbario.fabric" --keyfile ${HOME}/.crossbar/default.priv

python3 -u ex_status.py --url "ws://localhost:9000/ws" --realm "mrealm1" --keyfile ${HOME}/.crossbar/default.priv
python3 -u ex_cpu_affinity.py --url "ws://localhost:9000/ws" --realm "mrealm1" --keyfile ${HOME}/.crossbar/default.priv

python3 -u ex_list_nodes.py --url "ws://localhost:9000/ws" --realm "mrealm1" --keyfile ${HOME}/.crossbar/default.priv
python3 -u ex_list_sessions.py --url "ws://localhost:9000/ws" --realm "mrealm1" --keyfile ${HOME}/.crossbar/default.priv
python3 -u ex_list_workers.py --url "ws://localhost:9000/ws" --realm "mrealm1" --keyfile ${HOME}/.crossbar/default.priv
# python3 -u ex_list_subs_regs.py --url "ws://localhost:9000/ws" --realm "mrealm1" --keyfile ${HOME}/.crossbar/default.priv

python3 -u ex_start_router.py --url "ws://localhost:9000/ws" --realm "mrealm1" --keyfile ${HOME}/.crossbar/default.priv
python3 -u ex_start_container.py --url "ws://localhost:9000/ws" --realm "mrealm1" --keyfile ${HOME}/.crossbar/default.priv
python3 -u ex_start_guest.py --url "ws://localhost:9000/ws" --realm "mrealm1" --keyfile ${HOME}/.crossbar/default.priv
python3 -u ex_start_web_services.py --url "ws://localhost:9000/ws" --realm "mrealm1" --keyfile ${HOME}/.crossbar/default.priv

python3 -u ex_worker_log.py --url "ws://localhost:9000/ws" --realm "mrealm1" --keyfile ${HOME}/.crossbar/default.priv
python3 -u ex_process_stats.py --url "ws://localhost:9000/ws" --realm "mrealm1" --keyfile ${HOME}/.crossbar/default.priv

python3 -u ex_docker.py --url "ws://localhost:9000/ws" --realm "mrealm1" --keyfile ${HOME}/.crossbar/default.priv

#python3 -u ex_start_proxy.py --url "ws://localhost:9000/ws" --realm "mrealm1" --keyfile ${HOME}/.crossbar/default.priv
python3 -u ex_tracing.py --url "ws://localhost:9000/ws" --realm "mrealm1" --keyfile ${HOME}/.crossbar/default.priv
#python3 -u ex_webcluster.py --url "ws://localhost:9000/ws" --realm "mrealm1" --keyfile ${HOME}/.crossbar/default.priv

# PROBLEMATIC: python3 -u ex_monitor_sessions.py --url "ws://localhost:9000/ws" --realm "mrealm1" --keyfile ${HOME}/.crossbar/default.priv

cd "$orig_path"

crossbar edge stop --cbdir ./test/cf1/.crossbar
crossbar edge stop --cbdir ./test/cf2/.crossbar
crossbar edge stop --cbdir ./test/cf3/.crossbar

crossbar master stop --cbdir ./test/cfc/.crossbar

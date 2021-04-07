#
# Examples, eg:
#
#	make ex_status url=ws://localhost:9000/ws realm=mrealm1
#

# eg: make examples realm=oberstet
realm := $(or ${realm},${realm},"mrealm1")
url := $(or ${url},${url},"ws://localhost:9000/ws")
trace := $(or ${trace},${trace},"trace1")
action := $(or ${action},${action},"")

examples: \
	ex_global_api \
	ex_status \
	ex_list_nodes \
	ex_list_workers \
	ex_start_router \
	ex_start_proxy \
	ex_start_container \
	ex_start_guest \
	ex_list_sessions \
	ex_list_subs_regs \
	ex_cpu_affinity \
	ex_process_stats \
	ex_worker_log \
	ex_tracing \
	ex_tracing_actions \
	ex_docker


#
# run code quality checks on the examples - not the examples (for that, see below: ex_...)
#
test:
	flake8 --ignore=E501,N802 examples
	pylint examples

#
# this example demonstrates some functions on the CFC global users realm
#
ex_global_status:
	python3 -u management/ex_global_status.py --url ${url} --realm "com.crossbario.fabric"  --authmethod anonymous

ex_global_api:
	python3 -u management/ex_global_api.py --url ${url} --realm "com.crossbario.fabric" --keyfile ${HOME}/.crossbarfx/default.priv


#
# the following examples all work on a user management realm on CFC
#
# make ex_status url=ws://localhost:9000/ws realm=test1
#
ex_status:
	python3 -u management/ex_status.py --url ${url} --realm ${realm} --keyfile ${HOME}/.crossbarfx/default.priv

ex_status_anon:
	python3 -u management/ex_status.py --url ${url} --realm ${realm} --authmethod anonymous

ex_list_nodes:
	python3 -u management/ex_list_nodes.py --url ${url} --realm ${realm} --keyfile ${HOME}/.crossbarfx/default.priv

ex_list_workers:
	python3 -u management/ex_list_workers.py --url ${url} --realm ${realm} --keyfile ${HOME}/.crossbarfx/default.priv

ex_start_router:
	python3 -u management/ex_start_router.py --url ${url} --realm ${realm} --keyfile ${HOME}/.crossbarfx/default.priv

ex_start_proxy:
	python3 -u management/ex_start_proxy.py --url ${url} --realm ${realm} --keyfile ${HOME}/.crossbarfx/default.priv

ex_start_container:
	python3 -u management/ex_start_container.py --url ${url} --realm ${realm} --keyfile ${HOME}/.crossbarfx/default.priv

ex_start_guest:
	python3 -u management/ex_start_guest.py --url ${url} --realm ${realm} --keyfile ${HOME}/.crossbarfx/default.priv

ex_start_web_services:
	python3 -u management/ex_start_web_services.py --url ${url} --realm ${realm} --keyfile ${HOME}/.crossbarfx/default.priv

ex_list_sessions:
	python3 -u management/ex_list_sessions.py --url ${url} --realm ${realm} --keyfile ${HOME}/.crossbarfx/default.priv

ex_list_sessions_anon:
	python3 -u management/ex_list_sessions.py --url ${url} --realm ${realm} --authmethod anonymous

ex_monitor_sessions:
	python3 -u management/ex_monitor_sessions.py --url ${url} --realm ${realm} --keyfile ${HOME}/.crossbarfx/default.priv

ex_list_subs_regs:
	python3 -u management/ex_list_subs_regs.py --url ${url} --realm ${realm} --keyfile ${HOME}/.crossbarfx/default.priv

ex_cpu_affinity:
	python3 -u management/ex_cpu_affinity.py --url ${url} --realm ${realm} --keyfile ${HOME}/.crossbarfx/default.priv

ex_process_stats:
	python3 -u management/ex_process_stats.py --url ${url} --realm ${realm} --keyfile ${HOME}/.crossbarfx/default.priv

ex_worker_log:
	python3 -u management/ex_worker_log.py --url ${url} --realm ${realm} --keyfile ${HOME}/.crossbarfx/default.priv

ex_tracing:
	python3 -u management/ex_tracing.py --url ${url} --realm ${realm} --keyfile ${HOME}/.crossbarfx/default.priv

ex_tracing_actions:
	python3 -u management/ex_tracing_actions.py --url ${url} --realm ${realm} --keyfile ${HOME}/.crossbarfx/default.priv

ex_tracing_monitor:
	python3 -u management/ex_tracing_monitor.py --url ${url} --realm ${realm} --keyfile ${HOME}/.crossbarfx/default.priv

#ex_tracing_monitor_actions:
#	python3 -u management/ex_tracing_monitor_actions.py --debug --authmethod anonymous --url ${url} --realm ${realm} --keyfile ${HOME}/.crossbarfx/default.priv

#ex_tracing_monitor_by_action:
#	python3 -u management/ex_tracing_monitor_by_action.py --url ${url} --realm ${realm} --keyfile ${HOME}/.crossbarfx/default.priv

ex_docker:
	python3 -u management/ex_docker.py --url ${url} --realm ${realm} --keyfile ${HOME}/.crossbarfx/default.priv


# make ex_tracing_manage_trace url=ws://localhost:9000/ws realm=test1 action=create
ex_tracing_manage_trace:
	python3 -u management/tracing/ex_manage_trace.py --url ${url} --realm ${realm} \
		--authmethod cryptosign --keyfile ${HOME}/.crossbarfx/default.priv \
		${action}

# make ex_tracing_monitor_trace url=ws://localhost:9000/ws realm=test1
ex_tracing_monitor_trace:
	python3 -u management/tracing/ex_monitor_trace.py --url ${url} --realm ${realm} \
		--authmethod anonymous


# make ex_wsrp_cluster url=ws://localhost:9000/ws realm=test1
#
ex_wsrp_cluster:
	python3 -u management/ex_wsrp_cluster.py --url ${url} --realm ${realm} --keyfile ${HOME}/.crossbarfx/default.priv

# make ex_webcluster url=ws://localhost:9000/ws realm=test1
#
ex_webcluster:
	python3 -u management/ex_webcluster.py --url ${url} --realm ${realm} --keyfile ${HOME}/.crossbarfx/default.priv

#
# Docker CF nodes / app containers for testing
#

# start 2x Crossbar.io Fabric (CF) node
run_cf:
	docker-compose up cf1 cf2

# start 4x app components connecting to the 2 CF nodes
run_app:
	docker-compose up app1a app1b app1c app1d

# start everything
run:
	docker-compose up

#
# Local testing (these targets are for CB developers only)
#
app_realm := $(or ${app_realm},${app_realm},"realm1")
app_url_1 := $(or ${app_url_1},${app_url_1},"ws://localhost:8080/ws")
app_url_2 := $(or ${app_url_2},${app_url_2},"ws://localhost:8081/ws")


run_local_cf1:
	crossbar start --personality fabric --cbdir test/cf1/.crossbar/

run_local_cf2:
	crossbar start --personality fabric --cbdir test/cf2/.crossbar/

#
# make run_local_app1a app_url_1=wss://cftest1.crossbario.com/ws
# make run_local_app1b app_url_1=wss://cftest1.crossbario.com/ws
# make run_local_app1c app_url_2=wss://cftest2.crossbario.com/ws
# make run_local_app1d app_url_2=wss://cftest2.crossbario.com/ws
#
run_local_app1a:
	python -u test/app1/client.py --url=${app_url_1} --realm ${app_realm} --service=service1

run_local_app1b:
	python -u test/app1/client.py --url=${app_url_1} --realm ${app_realm} --service=service2

run_local_app1c:
	python -u test/app1/client.py --url=${app_url_2} --realm ${app_realm} --service=service3

run_local_app1d:
	python -u test/app1/client.py --url=${app_url_2} --realm ${app_realm} --service=service4

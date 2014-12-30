all:
	@echo "Targets:"
	@echo ""
	@echo "   install          Local install"
	@echo "   clean            Cleanup"
	@echo "   publish          Clean build and publish to PyPI"
	@echo ""

install:
	#python setup.py install
	#pip install -e .[tls,msgpack,manhole,system]
	pip install -e .[all]

clean:
	rm -rf ./build
	rm -rf ./dist
	rm -rf ./crossbar.egg-info
	rm -rf ./.crossbar
	find . -name "*.db" -exec rm -f {} \;
	find . -name "*.pyc" -exec rm -f {} \;
	find . -name "*.log" -exec rm -f {} \;
	find . -name "__pycache__" -type d -exec rm -rf {} \;

version:
	PYTHONPATH=. python -m crossbar.controller.cli version

templates:
	PYTHONPATH=. python -m crossbar.controller.cli templates

init:
	PYTHONPATH=. python -m crossbar.controller.cli init

start_test_flash:
	PYTHONPATH=. python -m crossbar.controller.cli start --cbdir ./crossbar/templates/flash/.crossbar

init_hello_python:
	rm -rf ${HOME}/cbtest_hello
	PYTHONPATH=. python -m crossbar.controller.cli init --template hello:python --appdir ${HOME}/cbtest_hello

start_hello_python:
	PYTHONPATH=. python -m crossbar.controller.cli start --cbdir ${HOME}/cbtest_hello/.crossbar

init_votes_browser:
	rm -rf ${HOME}/cbtest_votes_browser
	PYTHONPATH=. python -m crossbar.controller.cli init --template votes:browser --appdir ${HOME}/cbtest_votes_browser

start_votes_browser:
	PYTHONPATH=. python -m crossbar.controller.cli start --cbdir ${HOME}/cbtest_votes_browser/.crossbar

init_votes_nodejs:
	rm -rf ${HOME}/cbtest_votes_nodejs
	PYTHONPATH=. python -m crossbar.controller.cli init --template votes:nodejs --appdir ${HOME}/cbtest_votes_nodejs

start_votes_nodejs:
	PYTHONPATH=. python -m crossbar.controller.cli start --cbdir ${HOME}/cbtest_votes_nodejs/.crossbar

init_demos:
	PYTHONPATH=. python -m crossbar.controller.cli init --template demos

check:
	PYTHONPATH=. python -m crossbar.controller.cli check

start:
	PYTHONPATH=. python -m crossbar.controller.cli start

start_pypy:
	PYTHONPATH=. pypy -m crossbar.controller.cli start

start_py34:
	PYTHONPATH=. /home/oberstet/python341/bin/python3 -m crossbar.controller.cli start

publish: clean
	python setup.py register
	python setup.py sdist upload

test:
	trial crossbar
#	trial crossbar.router.test

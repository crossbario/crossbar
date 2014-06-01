all:
	@echo "Targets:"
	@echo ""
	@echo "   install          Local install"
	@echo "   clean            Cleanup"
	@echo "   publish          Clean build and publish to PyPI"
	@echo ""

install:
	python setup.py install

clean:
	rm -rf ./build
	rm -rf ./dist
	rm -rf ./crossbar.egg-info
	#rm -rf ./.crossbar
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

init_hello_python:
	rm -rf test_hello
	PYTHONPATH=. python -m crossbar.controller.cli init --template hello:python --appdir test_hello

start_hello_python:
	PYTHONPATH=. python -m crossbar.controller.cli start --cbdir test_hello/.crossbar

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

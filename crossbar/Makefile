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
	rm -rf ./.crossbar
	find . -name "*.db" -exec rm -f {} \;
	find . -name "*.pyc" -exec rm -f {} \;
	find . -name "*.log" -exec rm -f {} \;

init:
	PYTHONPATH=. python -m crossbar.node.cli init

init_demos:
	PYTHONPATH=. python -m crossbar.node.cli init --template demos

check:
	PYTHONPATH=. python -m crossbar.node.cli check

start:
	PYTHONPATH=. python -m crossbar.node.cli start

publish: clean
	python setup.py register
	python setup.py sdist upload

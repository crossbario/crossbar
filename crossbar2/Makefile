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
	find . -name "*.pyc" -exec rm -f {} \;
	find . -name "*.log" -exec rm -f {} \;

init:
	PYTHONPATH=. python -m crossbar.cli init

start:
	PYTHONPATH=. python -m crossbar.cli start

publish: clean
	python setup.py register
	python setup.py sdist upload

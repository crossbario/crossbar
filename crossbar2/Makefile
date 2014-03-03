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
	find . -name "*.pyc" -exec rm -f {} \;

init:
	PYTHONPATH=. python -m crossbar.cli -d init

start:
	PYTHONPATH=. python -m crossbar.cli -d start

publish: clean
	python setup.py register
	python setup.py sdist upload

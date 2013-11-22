all:
	@echo "Targets:"
	@echo ""
	@echo "   install          Local install"
	@echo "   clean            Cleanup"
	@echo "   build            Clean build"
	@echo "   publish          Clean build and publish to PyPI"
	@echo ""

build:
	python setup.py bdist_egg

install:
	python setup.py install

clean:
	rm -rf ./build
	rm -rf ./dist
	rm -rf ./crossbar.egg-info
	find . -name "*.pyc" -exec rm -f {} \;

test:
	twistd.py -n crossbar

test_cli:
	python -m crossbar.cli

publish: clean
	python setup.py register
	python setup.py sdist upload
	python setup.py bdist_egg upload
	python setup.py bdist_wininst upload

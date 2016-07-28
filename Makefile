.PHONY: test docs

all:
	@echo "Targets:"
	@echo ""
	@echo "   clean            Cleanup"
	@echo "   test             Run unit tests"
	@echo "   flake8           Run flake tests"
	@echo "   install          Local install"
	@echo "   publish          Clean build and publish to PyPI"
	@echo "   docs             Build and test docs"
	@echo ""

clean:
	rm -rf ./build
	rm -rf ./dist
	rm -rf ./crossbar.egg-info
	rm -rf ./.crossbar
	rm -rf ./_trial_temp
	rm -rf ./.tox
	find . -name "*.db" -exec rm -f {} \;
	find . -name "*.pyc" -exec rm -f {} \;
	find . -name "*.log" -exec rm -f {} \;
	# Learn to love the shell! http://unix.stackexchange.com/a/115869/52500
	find . \( -name "*__pycache__" -type d \) -prune -exec rm -rf {} +

news: towncrier.ini crossbar/newsfragments/*.*
	# this produces a NEWS.md file, 'git rm's crossbar/newsfragmes/* and 'git add's NEWS.md
	# ...which we then use to update docs/pages/ChangeLog.md
	towncrier
	cat docs/templates/changelog_preamble.md > docs/pages/ChangeLog.md
	cat NEWS.md >> docs/pages/ChangeLog.md
	git add docs/pages/ChangeLog.md
	echo You should now 'git commit -m "update NEWS and ChangeLog"' the result, if happy.

docs:
	# towncrier --draft > docs/pages/ChangeLog.md
	python docs/test_server.py

# call this in a fresh virtualenv to update our frozen requirements.txt!
freeze:
	pip install --no-cache-dir -r requirements-in.txt
	pip freeze -r requirements-in.txt
	pip install hashin
	cat requirements-in.txt | grep -v crossbar | grep -v hashin > requirements.txt
	# FIXME: hashin each dependency in requirements.txt and remove the original entries (so no double entries are left)
	hashin click
	hashin setuptools
	hashin zope.interface
	hashin Twisted
	hashin autobahn
	hashin netaddr
	hashin PyTrie
	hashin Jinja2
	hashin mistune
	hashin Pygments
	hashin PyYAML
	hashin shutilwhich
	hashin sdnotify
	hashin psutil
	hashin lmdb
	hashin u-msgpack-python
	hashin cbor
	hashin py-ubjson
	hashin cryptography
	hashin pyOpenSSL
	hashin pyasn1
	hashin pyasn1-modules
	hashin service-identity
	hashin PyNaCl
	hashin treq
	hashin setproctitle
	hashin watchdog
	hashin argh
	hashin attrs
	hashin cffi
	hashin enum34
	hashin idna
	hashin ipaddress
	hashin MarkupSafe
	hashin pathtools
	hashin pycparser
	hashin requests
	hashin six
	hashin txaio

wheel:
	LMDB_FORCE_CFFI=1 SODIUM_INSTALL=bundled pip wheel --require-hashes --wheel-dir ./wheels -r requirements.txt

# install dependencies exactly
install_deps:
	LMDB_FORCE_CFFI=1 SODIUM_INSTALL=bundled pip install --ignore-installed --require-hashes -r requirements.txt

install:
	pip install -e .

# publish to PyPI
publish: clean
	python setup.py sdist bdist_wheel
	twine upload dist/*

test: flake8
	trial crossbar

full_test: clean flake8
	trial crossbar

# This will run pep8, pyflakes and can skip lines that end with # noqa
flake8:
	flake8 --ignore=E501,E731,N801,N802,N803,N805,N806 crossbar

flake8_stats:
	flake8 --statistics --max-line-length=119 -qq crossbar

version:
	PYTHONPATH=. python -m crossbar.controller.cli version

pyflakes:
	pyflakes crossbar

pep8:
	pep8 --statistics --ignore=E501 -qq .

pep8_show_e231:
	pep8 --select=E231 --show-source

autopep8:
	autopep8 -ri --aggressive --ignore=E501 .

pylint:
	pylint -d line-too-long,invalid-name crossbar

find_classes:
	find crossbar -name "*.py" -exec grep -Hi "^class" {} \; | grep -iv test

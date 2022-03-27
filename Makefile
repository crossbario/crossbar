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
	@echo "   prepareUbuntu    Prepare running tests on Ubuntu"
	@echo ""

clean:
	rm -rf ./build
	rm -rf ./dist
	rm -rf ./crossbar.egg-info
	rm -rf ./.crossbar
	-find . -type d -name _trial_temp -exec rm -rf {} \;
	rm -rf ./tests
	rm -rf ./.tox
	rm -rf ./vers
	rm -f .coverage.*
	rm -f .coverage
	rm -rf ./htmlcov
	-rm -rf ./_trial*
	-rm -rf ./pip-wheel-metadata
	-rm -rf ./docs/_build
	find . -name "*.db" -exec rm -f {} \;
	find . -name "*.pyc" -exec rm -f {} \;
	find . -name "*.log" -exec rm -f {} \;
	# Learn to love the shell! http://unix.stackexchange.com/a/115869/52500
	find . \( -name "*__pycache__" -type d \) -prune -exec rm -rf {} +

run_ganache:
	docker-compose up --force-recreate ganache

fix_ganache_permissions:
	sudo chown -R 1000:1000 ./test/ganache

clean_ganache:
	-rm -rf ./test/ganache/.data
	mkdir -p ./test/ganache/.data

logs_service:
	sudo journalctl -f -u github-actions-crossbar.service

# Targets for Sphinx-based documentation
#

#docs:
#	sphinx-build -b html docs docs/_build

# spellcheck the docs
#docs_spelling:
#	sphinx-build -b spelling -d docs/_build/doctrees docs docs/_build/spelling

docs:
	cd docs && sphinx-build -b html . _build

docs_check:
	cd docs && sphinx-build -nWT -b dummy . _build

docs_spelling:
	cd docs && sphinx-build -nWT -b spelling -d ./_build/doctrees . ./_build/spelling

docs_run: docs
	twistd --nodaemon web --path=docs/_build --listen=tcp:8090

docs_clean:
	-rm -rf ./docs/_build

# find . -type f -exec sed -i 's/Crossbar.io/Crossbar.io/g' {} \;
fix_fx_strings:
	find . -type f -exec sed -i 's/Copyright (c) Crossbar.io Technologies GmbH. All rights reserved./Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2./g' {} \;


# freeze our dependencies
freeze:
	# do everything in a fresh environment
	-rm -rf vers
	virtualenv vers
	vers/bin/pip3 install pip wheel hashin pip-licenses

	# install and freeze latest versions of minimum requirements
	vers/bin/pip3 install -r requirements-min.txt
	vers/bin/pip3 freeze --all | grep -v -e "wheel" -e "pip" -e "distribute" > requirements-pinned.txt

	# persist OSS license list of our exact dependencies
	vers/bin/pip-licenses --from=classifier -a -o name > LICENSES-OSS
	vers/bin/pip-licenses --from=classifier -a -o name --format=rst > docs/soss_licenses_table.rst
	sed -i '1s;^;OSS Licenses\n============\n\n;' docs/soss_licenses_table.rst

	# hash all dependencies for repeatable builds
	vers/bin/pip3 install hashin
	-rm requirements.txt
	# FIXME: we are using our own unpublished forks of "py-cid" and "py-multihash" for which hashin won't find version data on pypi
	-cat requirements-pinned.txt | grep -v "py-cid" | grep -v "py-multihash" | grep -v "vmprof" | xargs vers/bin/hashin > requirements.txt
	-cat requirements-pinned.txt | grep "py-cid" >> requirements.txt
	-cat requirements-pinned.txt | grep "py-multihash" >> requirements.txt
	-cat requirements-pinned.txt | grep "vmprof" >> requirements.txt

wheel:
	LMDB_FORCE_CFFI=1 SODIUM_INSTALL=bundled pip wheel --require-hashes --wheel-dir ./wheels -r requirements.txt

# install for development, using pinned dependencies, and including dev-only dependencies
install:
	-pip uninstall -y crossbar
	pip install --no-cache --upgrade -r requirements-dev.txt
	pip install -e .
	@python -c "import crossbar; print('*** crossbar-{} ***'.format(crossbar.__version__))"

# install using pinned/hashed dependencies, as we do for packaging
install_pinned:
	-pip uninstall -y crossbar
	LMDB_FORCE_CFFI=1 SODIUM_INSTALL=bundled pip install --ignore-installed --require-hashes -r requirements.txt
	pip install .
	@python -c "import crossbar; print('*** crossbar-{} ***'.format(crossbar.__version__))"

# upload to our internal deployment system
upload: clean
	python setup.py bdist_wheel
	aws s3 cp dist/*.whl s3://fabric-deploy/

# publish to PyPI
publish: clean
	python setup.py sdist bdist_wheel
	twine upload dist/*

test_trial: flake8
	trial crossbar

test_full:
	crossbar \
		--personality=standalone \
		--debug-lifecycle \
		--debug-programflow\
		start \
		--cbdir=./test/full/.crossbar

test_manhole:
	ssh -vvv -p 6022 oberstet@localhost

gen_ssh_keys:
#	ssh-keygen -t ed25519 -f test/full/.crossbar/ssh_host_ed25519_key
	ssh-keygen -t rsa -b 4096 -f test/full/.crossbar/ssh_host_rsa_key

test_coverage:
	tox -e coverage .

test:
	tox -e sphinx,flake8,py36-unpinned-trial,py36-cli,py36-examples,coverage .

test_bandit:
	tox -e bandit .

test_cli:
	./test/test_cli.sh

test_cli_tox:
	tox -e py36-cli .

test_examples:
	tox -e py36-examples .

test_mqtt:
#	trial crossbar.adapter.mqtt.test.test_wamp
	trial crossbar.adapter.mqtt.test.test_wamp.MQTTAdapterTests.test_basic_publish

test_router:
	trial crossbar.router.test.test_broker
	#trial crossbar.router.test.test_router

test_testament:
	trial crossbar.router.test.test_testament

test_auth_ticket:
	trial crossbar.router.test.test_authorize.TestDynamicAuth.test_authextra_ticket

test_auth:
	trial crossbar.router.test.test_authorize

test_reactors:
	clear
	-crossbar version --loglevel=debug
	-crossbar --reactor="select" version --loglevel=debug
	-crossbar --reactor="poll" version --loglevel=debug
	-crossbar --reactor="epoll" version --loglevel=debug
	-crossbar --reactor="kqueue" version --loglevel=debug
	-crossbar --reactor="iocp" version --loglevel=debug

full_test: clean flake8
	trial crossbar

# This will run pep8, pyflakes and can skip lines that end with # noqa
flake8:
	flake8 --ignore=E117,E402,F405,E501,E722,E741,E731,N801,N802,N803,N805,N806 crossbar

flake8_stats:
	flake8 --statistics --max-line-length=119 -qq crossbar

version:
	PYTHONPATH=. python -m crossbar.controller.cli version


# auto-format code - WARNING: this my change files, in-place!
autoformat:
	yapf -ri --style=yapf.ini \
		--exclude="crossbar/shell/reflection/*" \
		--exclude="crossbar/master/database/*" \
		--exclude="crossbar/worker/test/examples/syntaxerror.py" \
		crossbar


# sudo apt install gource ffmpeg
gource:
	gource \
	--path . \
	--seconds-per-day 0.15 \
	--title "crossbar" \
	-1280x720 \
	--file-idle-time 0 \
	--auto-skip-seconds 0.75 \
	--multi-sampling \
	--stop-at-end \
	--highlight-users \
	--hide filenames,mouse,progress \
	--max-files 0 \
	--background-colour 000000 \
	--disable-bloom \
	--font-size 24 \
	--output-ppm-stream - \
	--output-framerate 30 \
	-o - \
	| ffmpeg \
	-y \
	-r 60 \
	-f image2pipe \
	-vcodec ppm \
	-i - \
	-vcodec libx264 \
	-preset ultrafast \
	-pix_fmt yuv420p \
	-crf 1 \
	-threads 0 \
	-bf 0 \
	crossbar.mp4

# Some prerequisites needed on ubuntu to run the tests.
prepareUbuntu:
	sudo apt install libsnappy-dev
	sudo apt install python-tox

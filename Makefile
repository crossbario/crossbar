.PHONY: test docs

all:
	@echo "Targets:"
	@echo ""
	@echo "   clean            Cleanup"
	@echo "   test             Run unit tests"
	@echo "   install          Local install"
	@echo "   publish          Clean build and publish to PyPI"
	@echo "   docs             Build and test docs"
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

# install for development, using pinned dependencies, and including dev-only dependencies
install:
	-pip uninstall -y crossbar
	pip install --no-cache --upgrade -r requirements-dev.txt
	pip install -e .
	@python -c "import crossbar; print('*** crossbar-{} ***'.format(crossbar.__version__))"

# upload to our internal deployment system
upload: clean
	python setup.py bdist_wheel
	aws s3 cp dist/*.whl s3://fabric-deploy/

# publish to PyPI
publish: clean
	python setup.py sdist bdist_wheel
	twine upload dist/*

# auto-format code - WARNING: this my change files, in-place!
autoformat:
	yapf -ri --style=yapf.ini \
		--exclude="crossbar/shell/reflection/*" \
		--exclude="crossbar/master/database/*" \
		--exclude="crossbar/worker/test/examples/syntaxerror.py" \
		crossbar

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

# test all syntax check target on the host via tox
test_quick:
	tox -e  sphinx,flake8,mypy,yapf .

# test all targets on the host via tox
test:
	tox -e  sphinx,flake8,mypy,yapf,bandit,py39-pinned-trial,py39-unpinned-trial,py39-abtrunk-trial,py39-examples,pytest,functests-cb,functests-cfc,py39-api-1,py39-cli-0,py39-cli-1,py39-cli-2,py39-cli-3 .

# test all broken (FIXME) targets
test_fixme:
	tox -e	py39-automate-1,py39-automate-2,py39-xbrnetwork-1 .

test_cb_proxy:
	pytest -sv --no-install test/functests/cbtests/test_cb_proxy.py

test_wap:
	trial crossbar.webservice.test

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

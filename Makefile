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
	rm -rf ./vers
	find . -name "*.db" -exec rm -f {} \;
	find . -name "*.pyc" -exec rm -f {} \;
	find . -name "*.log" -exec rm -f {} \;
	# Learn to love the shell! http://unix.stackexchange.com/a/115869/52500
	find . \( -name "*__pycache__" -type d \) -prune -exec rm -rf {} +

news: towncrier.ini crossbar/newsfragments/*.*
	# this produces a NEWS.md file, 'git rm's crossbar/newsfragments/* and 'git add's NEWS.md
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
freeze: clean
	pip install -U virtualenv
	virtualenv vers
	vers/bin/pip install -r requirements-min.txt
	vers/bin/pip freeze --all | grep -v -e "wheel" -e "pip" -e "distribute" > requirements-pinned.txt
	vers/bin/pip install hashin
	rm requirements.txt
	cat requirements-pinned.txt | xargs vers/bin/hashin > requirements.txt

wheel:
	LMDB_FORCE_CFFI=1 SODIUM_INSTALL=bundled pip wheel --require-hashes --wheel-dir ./wheels -r requirements.txt

# install using pinned/hashed dependencies, as we do for packaging
install:
	LMDB_FORCE_CFFI=1 SODIUM_INSTALL=bundled pip install --ignore-installed --require-hashes -r requirements.txt
	pip install .

# install for development, using pinned dependencies, and including dev-only dependencies
install_dev:
	pip install -r requirements-dev.txt
	pip install -e .

# upload to our internal deployment system
upload: clean
	python setup.py bdist_wheel
	aws s3 cp dist/*.whl s3://fabric-deploy/

# publish to PyPI
publish: clean
	python setup.py sdist bdist_wheel
	twine upload dist/*

test: flake8
	trial crossbar

test_mqtt:
#	trial crossbar.adapter.mqtt.test.test_wamp
	trial crossbar.adapter.mqtt.test.test_wamp.MQTTAdapterTests.test_basic_publish

full_test: clean flake8
	trial crossbar

# This will run pep8, pyflakes and can skip lines that end with # noqa
flake8:
	flake8 --ignore=E402,F405,E501,E731,N801,N802,N803,N805,N806 crossbar

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

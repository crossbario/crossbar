#!/bin/sh

rm -f /tmp/*.whl

curl -o /tmp/txaio-latest-py2.py3-none-any.whl       https://crossbarbuilder.s3.eu-central-1.amazonaws.com/wheels/txaio-latest-py2.py3-none-any.whl
curl -o /tmp/autobahn-latest-py2.py3-none-any.whl    https://crossbarbuilder.s3.eu-central-1.amazonaws.com/wheels/autobahn-latest-py2.py3-none-any.whl
curl -o /tmp/zlmdb-latest-py2.py3-none-any.whl       https://crossbarbuilder.s3.eu-central-1.amazonaws.com/wheels/zlmdb-latest-py2.py3-none-any.whl
curl -o /tmp/crossbar-latest-py2.py3-none-any.whl    https://crossbarbuilder.s3.eu-central-1.amazonaws.com/wheels/crossbar-latest-py2.py3-none-any.whl
curl -o /tmp/cfxdb-latest-py2.py3-none-any.whl       https://crossbarbuilder.s3.eu-central-1.amazonaws.com/wheels/cfxdb-latest-py2.py3-none-any.whl
curl -o /tmp/crossbarfx-latest-py2.py3-none-any.whl  https://crossbarbuilder.s3.eu-central-1.amazonaws.com/wheels/crossbarfx-latest-py2.py3-none-any.whl

pip install /tmp/txaio-latest-py2.py3-none-any.whl
pip install /tmp/zlmdb-latest-py2.py3-none-any.whl
pip install /tmp/autobahn-latest-py2.py3-none-any.whl[all]
pip install /tmp/crossbar-latest-py2.py3-none-any.whl
pip install /tmp/cfxdb-latest-py2.py3-none-any.whl
pip install /tmp/crossbarfx-latest-py2.py3-none-any.whl

which crossbarfx

crossbarfx version

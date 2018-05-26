#!/bin/sh

# build the docs, source package and binary (executable). this will produce:
#
#  - $HOME/crossbar-docs
#
# upload to "crossbar.io" company S3 bucket

# build and deploy latest docs
tox -c tox.ini -e sphinx
aws s3 cp --recursive --acl public-read ${HOME}/crossbar-docs s3://crossbar.io/docs-latest

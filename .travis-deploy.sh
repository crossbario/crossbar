#!/bin/bash

# AWS_ACCESS_KEY_ID         : must be set in Travis CI build context
# AWS_SECRET_ACCESS_KEY     : must be set in Travis CI build context

#export AWS_S3_BUCKET_NAME=download.crossbario.com
#export AWS_DEFAULT_REGION=eu-central-1

export AWS_S3_BUCKET_NAME=crossbar.io
export AWS_DEFAULT_REGION=eu-west-1

set -ev

# TRAVIS_BRANCH, TRAVIS_PULL_REQUEST, TRAVIS_TAG

# PR
if [ "$TRAVIS_PULL_REQUEST" = "true" ]; then
    echo '[1] deploy script called for PR - exiting ..';
    exit 0;

# direct push to master
elif [ "$TRAVIS_BRANCH" = "master" -a "$TRAVIS_PULL_REQUEST" = "false" ]; then
    echo '[2] deploy script called for direct push to master: continuing to deploy!';

# tagged release
elif [ -n "$TRAVIS_TAG" ]; then
    echo '[3] deploy script called for tagged release: continuing to deploy!';

else
    echo '[?] deploy script called for unhandled case (FIXME) - exiting ..';
    exit 0;

fi

# only show number of env vars .. should be 4 on master branch!
# https://docs.travis-ci.com/user/pull-requests/#Pull-Requests-and-Security-Restrictions
# Travis CI makes encrypted variables and data available only to pull requests coming from the same repository.
echo 'aws env vars (should be 4 - but only on master branch!):'
env | grep AWS | wc -l

# set up awscli package
echo 'installing aws tools ..'
pip install awscli
which aws
aws --version
aws s3 ls ${AWS_S3_BUCKET_NAME}

# build python source dist and wheels
echo 'building package ..'
python setup.py sdist bdist_wheel --universal
ls -la ./dist

# upload to S3: https://s3.eu-central-1.amazonaws.com/crossbarbuilder/wheels/
echo 'uploading package ..'
aws s3 cp --recursive ./dist s3://crossbarbuilder/wheels

# tell crossbar-builder about this new wheel push
# get 'wamp' command, always with latest autobahn master
pip install https://github.com/crossbario/autobahn-python/archive/master.zip#egg=autobahn[twisted,serialization,encryption]
# use 'wamp' to notify crossbar-builder
wamp --max-failures 3 --authid wheel_pusher --url ws://office2dmz.crossbario.com:8008/ --realm webhook call builder.wheel_pushed --keyword name crossbar --keyword publish true


# build and deploy latest docs: for now, this is hosted under
# https://s3.eu-central-1.amazonaws.com/download.crossbario.com/docs/crossbar/index.html
echo 'building and uploading docs ..'
tox -c tox.ini -e sphinx
#aws s3 cp --recursive --acl public-read ${HOME}/crossbar-docs s3://${AWS_S3_BUCKET_NAME}/docs
#aws s3 cp --recursive --acl public-read ${HOME}/crossbar-docs s3://${AWS_S3_BUCKET_NAME}/docs/crossbar
aws s3 cp --recursive --acl public-read ${HOME}/crossbar-docs s3://${AWS_S3_BUCKET_NAME}/docs

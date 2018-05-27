#!/bin/sh

# AWS_ACCESS_KEY_ID         : must be set in Travis CI build context
# AWS_SECRET_ACCESS_KEY     : must be set in Travis CI build context

export AWS_S3_BUCKET_NAME=download.crossbario.com
export AWS_DEFAULT_REGION=eu-central-1

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

# build and deploy latest docs
echo 'building and uploading docs ..'
tox -c tox.ini -e sphinx
#aws s3 cp --recursive --acl public-read ${HOME}/crossbar-docs s3://${AWS_S3_BUCKET_NAME}/docs
aws s3 cp --recursive --acl public-read ${HOME}/crossbar-docs s3://${AWS_S3_BUCKET_NAME}/docs/crossbar

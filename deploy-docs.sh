#!/bin/bash

set +o verbose -o errexit

export AWS_S3_BUCKET_NAME=crossbar.io
export AWS_DEFAULT_REGION=eu-west-1

echo 'building docs ..'

tox -c tox.ini -e sphinx

echo 'uploading docs to bucket "arn:aws:s3:::crossbar.io" ..'

aws s3 cp --recursive --acl public-read ${HOME}/crossbar-docs s3://${AWS_S3_BUCKET_NAME}/docs

echo ''
echo 'docs ready at:'
echo ''
echo '      https://s3-eu-west-1.amazonaws.com/crossbar.io/docs/index.html'
echo ''

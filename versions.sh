#!/bin/sh

export CROSSBAR_BUILD_DATE=`date -u +"%Y-%m-%d"`
export CROSSBAR_BUILD_ID=$(date --utc +%Y%m%d)-$(git rev-parse --short HEAD)
export CROSSBAR_VCS_REF=`git rev-parse --short HEAD`
# export CROSSBAR_VCS_REF=`git --git-dir="./.git" rev-list -n 1 v${CROSSBAR_VERSION} --abbrev-commit`
export CROSSBAR_VERSION=$(grep -E '^(__version__)' ./crossbar/_version.py | cut -d ' ' -f3 | sed -e 's|[u"'\'']||g')
export CROSSBAR_EXE_FILENAME="crossbar-linux-amd64-${CROSSBAR_BUILD_ID}"

echo ""
echo "Build environment configured:"
echo ""
echo "  CROSSBAR_BUILD_DATE   = ${CROSSBAR_BUILD_DATE}"
echo "  CROSSBAR_BUILD_ID     = ${CROSSBAR_BUILD_ID}"
echo "  CROSSBAR_VCS_REF      = ${CROSSBAR_VCS_REF}"
echo "  CROSSBAR_VERSION      = ${CROSSBAR_VERSION}"
echo "  CROSSBAR_EXE_FILENAME = ${CROSSBAR_EXE_FILENAME}"
echo ""

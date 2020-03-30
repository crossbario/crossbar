#!/bin/sh

export CROSSBAR_VERSION=$(grep -E '^(__version__)' ./crossbar/_version.py | cut -d ' ' -f3 | sed -e 's|[u"'\'']||g')
export CROSSBAR_VCS_REF=`git --git-dir="./.git" rev-list -n 1 v${CROSSBAR_VERSION} --abbrev-commit`
export BUILD_DATE=`date -u +"%Y-%m-%d"`

echo ""
echo "Build environment configured:"
echo ""
echo "  CROSSBAR_VERSION = ${CROSSBAR_VERSION}"
echo "  CROSSBAR_VCS_REF = ${CROSSBAR_VCS_REF}"
echo "  BUILD_DATE       = ${BUILD_DATE}"
echo ""

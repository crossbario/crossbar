#!/bin/sh

export CROSSBARFX_BUILD_DATE=`date -u +"%Y-%m-%d"`
export CROSSBARFX_BUILD_ID=$(date --utc +%Y%m%d)-$(git rev-parse --short HEAD)
export CROSSBARFX_VCS_REF=`git rev-parse --short HEAD`
# export CROSSBARFX_VCS_REF=`git --git-dir="./.git" rev-list -n 1 v${CROSSBARFX_VERSION} --abbrev-commit`
export CROSSBARFX_VERSION=$(grep -E '^(__version__)' ./crossbarfx/_version.py | cut -d ' ' -f3 | sed -e 's|[u"'\'']||g')
export CROSSBARFX_EXE_FILENAME="crossbarfx-linux-amd64-${CROSSBARFX_BUILD_ID}"

echo ""
echo "Build environment configured:"
echo ""
echo "  CROSSBARFX_BUILD_DATE   = ${CROSSBARFX_BUILD_DATE}"
echo "  CROSSBARFX_BUILD_ID     = ${CROSSBARFX_BUILD_ID}"
echo "  CROSSBARFX_VCS_REF      = ${CROSSBARFX_VCS_REF}"
echo "  CROSSBARFX_VERSION      = ${CROSSBARFX_VERSION}"
echo "  CROSSBARFX_EXE_FILENAME = ${CROSSBARFX_EXE_FILENAME}"
echo ""

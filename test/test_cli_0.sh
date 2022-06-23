#!/bin/sh

# SCRIPT_DIR=$(dirname "${BASH_SOURCE[0]}")
SCRIPT_DIR=$(pwd)/test

echo "Using SCRIPT_DIR=${SCRIPT_DIR}"
echo "Using CROSSBAR_FABRIC_URL=${CROSSBAR_FABRIC_URL}"
echo "Using CROSSBAR_FABRIC_SUPERUSER=${CROSSBAR_FABRIC_SUPERUSER}"

#
# test all crossbar CLI commands:
#
#   * init
#   * start
#   * stop
#   * status
#   * check
#   * convert
#   * upgrade
#   * keys
#   * version
#   * legal
#

OLDCWD=$(pwd)
PERSONALITY='standalone'
CB='crossbar'
APPDIR='/tmp/testnode'
CBDIR=$APPDIR'/.crossbar'

echo 'OLDCWD='$OLDCWD
echo 'PERSONALITY='$PERSONALITY
echo 'CB='$CB
echo 'APPDIR='$APPDIR
echo 'CBDIRCBDIR='$CBDIR

# "usage" (no command given), version, legal
#
$CB
$CB version
$CB legal


# start (from empty node directory), stop, keys
#
rm -rf $APPDIR
mkdir -p $CBDIR
( $CB start --cbdir=$CBDIR ) &
sleep 2
$CB stop --cbdir=$CBDIR
$CB keys --cbdir=$CBDIR
$CB keys --private --cbdir=$CBDIR


# init, check, start (from default initialized node directory), status, stop
#
rm -rf $APPDIR
$CB init --appdir=$APPDIR
find $APPDIR
$CB check --cbdir=$CBDIR
$CB status --cbdir=$CBDIR --assert=stopped
( $CB start --cbdir=$CBDIR ) &
sleep 2
$CB status --cbdir=$CBDIR --assert=running
sleep 2
$CB stop --cbdir=$CBDIR
$CB status --cbdir=$CBDIR --assert=stopped


# start with debug options, and auto-shutdown
#
$CB --debug-lifecycle --debug-programflow start --cbdir=$CBDIR --shutdownafter 5


# convert, check, start, status, stop
#
rm -rf $APPDIR
$CB init --appdir=$APPDIR
$CB check --cbdir=$CBDIR
$CB convert --cbdir=$CBDIR
cat $CBDIR/config.json
cat $CBDIR/config.yaml
rm $CBDIR/config.json
$CB check --cbdir=$CBDIR
( $CB start --cbdir=$CBDIR ) &
sleep 2
$CB status --cbdir=$CBDIR --assert=running
$CB stop --cbdir=$CBDIR


# test "full" configuration (all features and options)
#
$CB \
    --debug-lifecycle \
    --debug-programflow\
    start \
    --cbdir=./test/full/.crossbar \
    --shutdownafter=20

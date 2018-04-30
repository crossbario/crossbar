#!/bin/sh

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
PERSONALITY=standalone
CB='crossbar --personality='$PERSONALITY
APPDIR=/tmp/testnode
CBDIR=$APPDIR/.crossbar

echo 'OLDCWD='$OLDCWD
echo 'PERSONALITY='$PERSONALITY
echo 'CB='$CB
echo 'APPDIR='$APPDIR
echo 'CBDIRCBDIR='$CBDIR

# "usage" (no command given), version, legal
#
$CB
$CB version
$CB version --loglevel=debug
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

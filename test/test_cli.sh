#!/bin/sh

#
# test all crossbar CLI commands:
#
# init,start,stop,restart,status,check,convert,upgrade,keygen,keys,version,legal
#
# FIXME: add tests for commands "keygen"

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

# version, legal
#
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


# init, check, start (from default initialized node directory), status, stop
#
rm -rf $APPDIR
$CB init --appdir=$APPDIR
find $APPDIR
$CB check --cbdir=$CBDIR
$CB status --cbdir=$CBDIR --assertstate=stopped
( $CB start --cbdir=$CBDIR ) &
sleep 2
$CB status --cbdir=$CBDIR --assertstate=running
sleep 2
$CB stop --cbdir=$CBDIR
$CB status --cbdir=$CBDIR --assertstate=stopped


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
$CB status --cbdir=$CBDIR --assertstate=running
$CB stop --cbdir=$CBDIR

#!/bin/sh

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

# version
#
$CB version

# legal
#
$CB  legal

# init, start and status
#
rm -rf $APPDIR
$CB init --appdir=$APPDIR
find $APPDIR
( $CB start --cbdir=$CBDIR ) &
sleep 2
$CB status --cbdir=$CBDIR
sleep 2
$CB stop --cbdir=$CBDIR
$CB status --cbdir=$CBDIR

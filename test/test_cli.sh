#!/bin/sh

#
# test all crossbar CLI commands:
#
# init,start,stop,restart,status,check,convert,upgrade,keygen,keys,version,legal
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

# version, legal
#
$CB version
$CB legal

# init, check, start, status, stop, keys
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
$CB keys --cbdir=$CBDIR



#    restart             Restart a Crossbar.io node.
#    check               Check a Crossbar.io node`s local configuration file.
#    convert             Convert a Crossbar.io node`s local configuration file
#                        from JSON to YAML or vice versa.
#    upgrade             Upgrade a Crossbar.io node`s local configuration file
#                        to current configuration file format.
#    keygen              Generate public/private keypairs for use with
#                        autobahn.wamp.cryptobox.KeyRing
#    keys                Print Crossbar.io release and node keys.

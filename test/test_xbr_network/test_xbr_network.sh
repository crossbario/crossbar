#!/bin/sh

set +e

# stop & rm blockchain
docker stop xbr_blockchain || true

# start blockchain
docker run --detach --rm --name xbr_blockchain \
    --net host --env XBR_HDWALLET_SEED \
        crossbario/crossbarfx-blockchain:latest

sleep 10
docker logs xbr_blockchain

# initialize blockchain
python ../../crossbar/network/test/init_blockchain.py --gateway http://localhost:1545

# stop & rm crossbar
crossbar stop --cbdir ./.crossbar || true
rm -rf ./.crossbar/.ipfs_files/
rm -rf ./.crossbar/.xbrnetwork/
rm -rf ./.crossbar/.verifications/
rm -f ./.crossbar/key.*
rm -f ./.crossbar/xbrnetwork-eth.key
mkdir ./.crossbar/.ipfs_files/
mkdir ./.crossbar/.xbrnetwork/
mkdir ./.crossbar/.verifications/

# set eth key used by crossbar
python set-xbrnetwork-ethkey.py 1 ./.crossbar/xbrnetwork-eth.key

# start crossbar
CROSSBAR_FABRIC_URL= crossbar edge start --cbdir ./.crossbar/ &
# docker run --detach --rm --name xbr_node \
#     --net host --env XBR_HDWALLET_SEED -v ${PWD}:/node \
#     crossbario/crossbar:latest \
#     edge start --cbdir /node/.crossbar/

sleep 20
crossbar status

echo "*** START ************************************************************************"

# now test ..
python ../../crossbar/network/test/test_connect.py --gateway http://localhost:1545

if [[ -z $XBR_FULLTESTS ]]; then
    echo "WARNING: extended test deactive! set environment variable XBR_FULLTESTS to activate."
else
    python ../../crossbar/network/test/test_api01_echo.py \
        --url ws://localhost:8080/ws --realm xbrnetwork \
        --cskey=42146252e65814b3d82f1f94debcb985862ff1d650ac598f5811917d38d33912

    python ../../crossbar/network/test/test_api02_onboard.py \
        --url ws://localhost:8080/ws --realm xbrnetwork \
        --verifications ./.crossbar/.verifications \
        --username=alice1 --email=alice1@nodomain \
        --cskey=42146252e65814b3d82f1f94debcb985862ff1d650ac598f5811917d38d33912 \
        --ethkey=ae9a2e131e9b359b198fa280de53ddbe2247730b881faae7af08e567e58915bd

    python ../../crossbar/network/test/test_api03_login.py --debug \
        --url ws://localhost:8080/ws --realm xbrnetwork \
        --verifications ./.crossbar/.verifications \
        --email=alice1@nodomain \
        --cskey=e78df30a6ad13502960dddb477a8ff977c37442678753581f147a131efdb67d7 \
        --ethkey=ae9a2e131e9b359b198fa280de53ddbe2247730b881faae7af08e567e58915bd

    python ../../crossbar/network/test/test_api03_logout.py --debug \
        --url ws://localhost:8080/ws --realm xbrnetwork \
        --cskey=e78df30a6ad13502960dddb477a8ff977c37442678753581f147a131efdb67d7 \
        --ethkey=ae9a2e131e9b359b198fa280de53ddbe2247730b881faae7af08e567e58915bd

    python ../../crossbar/network/test/test_api04_member.py \
        --url ws://localhost:8080/ws --realm xbrnetwork \
        --cskey=42146252e65814b3d82f1f94debcb985862ff1d650ac598f5811917d38d33912 \
        --ethkey=ae9a2e131e9b359b198fa280de53ddbe2247730b881faae7af08e567e58915bd

    python ../../crossbar/network/test/test_api05_market.py \
        --url ws://localhost:8080/ws --realm xbrnetwork \
        --verifications ./.crossbar/.verifications \
        --cskey=42146252e65814b3d82f1f94debcb985862ff1d650ac598f5811917d38d33912 \
        --ethkey=ae9a2e131e9b359b198fa280de53ddbe2247730b881faae7af08e567e58915bd

    python ../../crossbar/network/test/test_api02_onboard.py \
        --url ws://localhost:8080/ws --realm xbrnetwork \
        --username=james --email=james@nodomain \
        --cskey=0db085a389c1216ad62b88b408e1d830abca9c9f9dad67eb8c8f8734fe7575eb \
        --ethkey=2e114163041d2fb8d45f9251db259a68ee6bdbfd6d10fe1ae87c5c4bcd6ba491

    python ../../crossbar/network/test/test_api06_market.py \
        --url ws://localhost:8080/ws --realm xbrnetwork \
        --verifications ./.crossbar/.verifications \
        --cskey=0db085a389c1216ad62b88b408e1d830abca9c9f9dad67eb8c8f8734fe7575eb \
        --ethkey=2e114163041d2fb8d45f9251db259a68ee6bdbfd6d10fe1ae87c5c4bcd6ba491

    python ../../crossbar/network/test/test_api07_market.py \
        --url ws://localhost:8080/ws --realm xbrnetwork \
        --cskey=42146252e65814b3d82f1f94debcb985862ff1d650ac598f5811917d38d33912 \
        --ethkey=ae9a2e131e9b359b198fa280de53ddbe2247730b881faae7af08e567e58915bd

    python ../../crossbar/network/test/test_api08_catalog.py \
        --url ws://localhost:8080/ws --realm xbrnetwork \
        --verifications ./.crossbar/.verifications \
        --cskey=0db085a389c1216ad62b88b408e1d830abca9c9f9dad67eb8c8f8734fe7575eb \
        --ethkey=2e114163041d2fb8d45f9251db259a68ee6bdbfd6d10fe1ae87c5c4bcd6ba491

    python ../../crossbar/network/test/test_api09_catalog.py \
        --url ws://localhost:8080/ws --realm xbrnetwork \
        --cskey=0db085a389c1216ad62b88b408e1d830abca9c9f9dad67eb8c8f8734fe7575eb \
        --ethkey=2e114163041d2fb8d45f9251db259a68ee6bdbfd6d10fe1ae87c5c4bcd6ba491

    python ../../crossbar/network/test/test_api10_api.py \
        --url ws://localhost:8080/ws --realm xbrnetwork \
        --verifications ./.crossbar/.verifications \
        --cskey=0db085a389c1216ad62b88b408e1d830abca9c9f9dad67eb8c8f8734fe7575eb \
        --ethkey=2e114163041d2fb8d45f9251db259a68ee6bdbfd6d10fe1ae87c5c4bcd6ba491
fi

sleep 5
echo "*** END ************************************************************************"

# stop crossbar
crossbar stop --cbdir ./.crossbar
# docker stop xbr_node

# stop and remove blockchain
docker stop xbr_blockchain || true

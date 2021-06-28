import os
import sys
import binascii

import txaio
txaio.use_twisted()

from autobahn.xbr import account_from_seedphrase


seedphrase = os.environ['XBR_HDWALLET_SEED']
account_idx = int(sys.argv[1])
keyfile = os.path.abspath(sys.argv[2])

account = account_from_seedphrase(seedphrase, account_idx)
adr = account.address
pkey_hex = binascii.b2a_hex(account.privateKey).decode()

print('Using account {} with address {} computed from wallet seedphrase "{}.."'.format(account_idx, adr, seedphrase[:12]))

with open(keyfile, 'wb') as f:
    f.write(account.privateKey)

print('Success! Private key written to file "{}".'.format(keyfile))

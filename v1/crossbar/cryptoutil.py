###############################################################################
##
##  Copyright (C) 2011-2013 Tavendo GmbH
##
##  This program is free software: you can redistribute it and/or modify
##  it under the terms of the GNU Affero General Public License, version 3,
##  as published by the Free Software Foundation.
##
##  This program is distributed in the hope that it will be useful,
##  but WITHOUT ANY WARRANTY; without even the implied warranty of
##  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
##  GNU Affero General Public License for more details.
##
##  You should have received a copy of the GNU Affero General Public License
##  along with this program. If not, see <http://www.gnu.org/licenses/>.
##
###############################################################################


import os, binascii, hashlib

from Crypto.PublicKey import RSA
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util import Counter
from Crypto.Util.number import long_to_bytes, bytes_to_long

## We use fixed AES-256-CTR mode!
##
CIPHERBITS = 256

## PKCS-5 padding for AES
##
BS = 16
pad = lambda s: s + (BS - len(s) % BS) * chr(BS - len(s) % BS)
unpad = lambda s : s[0:-ord(s[-1])]


# For AES-CTR encrypt/decrypt using PyCrypto, see:
# https://bugs.launchpad.net/pycrypto/+bug/899818


def encrypt_and_sign(msg,
                     senderPrivPem,
                     receiverPubPem):
   """
   Encrypts a message using AES256-CTR. The procedure first creates a new
   random key/nonce for symmetric encryption and encrypt/signs that via RSA.
   The procedure then symmatrically encrypts the actual message using that key/nonce.

   :param msg: Message to be encrypted.
   :type msg: str
   :param senderPrivPem: Sender private RSA key in PEM format.
   :type senderPrivPem: str
   :param receiverPubPem: Receiver public RSA key in PEM format.
   :type receiverPubPem: str
   :returns tuple -- (AES256-CTR encrypted message, RSA Encrypted Key+IV, RSA Signature) all Base64 encoded.
   """
   ## read in sender/receiver RSA keys
   ##
   skey = RSA.importKey(senderPrivPem)
   rkey = RSA.importKey(receiverPubPem)

   ## create new random key/nonce for AES
   ##
   key = get_random_bytes(CIPHERBITS/8)
   nonce = get_random_bytes(8)
   kv = key + nonce

   #print binascii.b2a_hex(kv)
   #print binascii.b2a_hex(key)
   #print binascii.b2a_hex(nonce)

   ## encrypt key/nonce using RSA
   ##
   emsg = rkey.encrypt(kv, 0)[0]

   ## encrypt msg using AES-256 in CTR mode
   ##
   c = AES.new(key, AES.MODE_CTR, counter = Counter.new(64, prefix = nonce))
   pmsg = c.encrypt(pad(msg))

   ## create a digest of the unencrypted message
   ##
   md = hashlib.sha256()
   md.update(msg)
   dmsg = md.digest()

   ## create a RSA signature over encrypted message + key/nonce
   ##
   ed = hashlib.sha256()
   ed.update(pmsg)
   ed.update(emsg)
   sig = long_to_bytes(skey.sign(ed.digest(), 0)[0])

   return (binascii.b2a_base64(pmsg).strip(),
           binascii.b2a_base64(emsg).strip(),
           binascii.b2a_base64(dmsg).strip(),
           binascii.b2a_base64(sig).strip())



def verify_and_decrypt(pmsg,
                       emsg,
                       dmsg,
                       sig,
                       senderPubPem,
                       receiverPrivPem):
   """

   """
   ## read in sender/receiver RSA keys
   ##
   skey = RSA.importKey(senderPubPem)
   rkey = RSA.importKey(receiverPrivPem)

   ## Base64 decode payloads
   ##
   pmsg = binascii.a2b_base64(pmsg)
   emsg = binascii.a2b_base64(emsg)
   dmsg = binascii.a2b_base64(dmsg)
   sig = binascii.a2b_base64(sig)

   ## verify RSA signature
   ##
   md = hashlib.sha256()
   md.update(pmsg)
   md.update(emsg)
   digest = md.digest()
   if not skey.verify(digest, (bytes_to_long(sig),)):
      raise Exception("could not verify signature")

   ## decrypt symmetric key / nonce
   ##
   kv = rkey.decrypt(emsg)
   key = kv[:CIPHERBITS/8]
   nonce = kv[CIPHERBITS/8:CIPHERBITS/8+8]

   #print binascii.b2a_hex(kv)
   #print binascii.b2a_hex(key)
   #print binascii.b2a_hex(nonce)

   ## decrypt msg using AES-256 in CTR mode
   ##
   c = AES.new(key, AES.MODE_CTR, counter = Counter.new(64, prefix = nonce))
   msg = unpad(c.decrypt(pmsg))

   ## create a digest of the unencrypted message
   ##
   md = hashlib.sha256()
   md.update(msg)
   if dmsg != md.digest():
      raise Exception("invalid key")

   return msg


if __name__ == '__main__':

   msg = "Hello, world  !!!" * 1

   key1prv = open("key1.priv").read()
   key1pub = open("key1.pub").read()
   key2prv = open("key2.priv").read()
   key2pub = open("key2.pub").read()
   key3prv = open("key3.priv").read()
   key3pub = open("key3.pub").read()

   (pmsg, emsg, sig) = encrypt_and_sign(msg, key1prv, key2pub)
   msg2 = verify_and_decrypt(pmsg, emsg, sig, key1pub, key2prv)
   print msg == msg2

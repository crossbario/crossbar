title: TLS Certificates
toc: [Documentation, Administration, Going to Production, TLS Certificates]

# TLS Certificates

This page provides some information about how to create and use TLS certificates for secure connections with Crossbar.io.

For configuring TLS in Crossbar.io in principle, see [Secure WebSocket and HTTPS](Secure WebSocket and HTTPS).

## Using Self-signed Certificates

For production use, the use of self-signed certificates is *not recommended*. However, for testing, development, Intranet or controlled deployments, you can of course.

The following provides a recipe for creating a new server key and self-signed certificate for use with Crossbar.io.

First, check your OpenSSL version:

```console
C:\Users\oberstet>openssl version
OpenSSL 1.0.1f 6 Jan 2014
```

> If running on Windows, make sure you start the command shell "as administrator". It seems OpenSSL requires this at least during key generation.

Then, create a new server key (RSA with 2048 bits in this case):

    openssl genrsa -out .crossbar/server_key.pem 2048
    chmod 600 .crossbar/server_key.pem

> A server key must not be protected with a passphrase, since it needs to be loaded unattended. However, you should make sure that file permissions are set so that only the user under which the server starts is able to read the key.

Next, create a new certificate signing request ("CSR") for the key generated formerly:

    openssl req -new -key .crossbar/server_key.pem -out .crossbar/server_csr.pem

You must set the "Common Name" (CN) to the fully qualified domain name (or IP address) of the server, e.g. `server23.tavendo.com` (or `62.146.25.40`). Do NOT include a port number - a certificate is always for a server, not a service running on a specific port.

> Note: to view the contents of a CSR: `openssl req -text -noout -verify -in .crossbar/server_csr.pem`

Finally, create a new self-signed certificate (valid for 1 year) from the CSR created formerly:

    openssl x509 -req -days 365 -in .crossbar/server_csr.pem \
        -signkey .crossbar/server_key.pem -out .crossbar/server_cert.pem

> Note: to view the contents of a certificate: `openssl x509 -text -noout -in .crossbar/server_cert.pem`

---

## Using commercial certificates

For production use, you will usually deploy certificates issues by commercial CAs, since only for those, browsers will have the CA certificates preinstalled, and hence users won't be bothered with invalid certificate dialogs.

> If you are looking for a free certificate, we recommend [StartSSL](http://www.startssl.com/).

Remove the passphrase protection from the private key with the OpenSSL (should there be any):

    openssl rsa -in server_key_with_passphrase.pem -out server_key.pem

> Note: This is needed since we want the server to start automatically without administrator interaction.

Append any intermediate CA certificates to the server certificate:

    cat ../sub.class1.server.sha2.ca.pem >> server_cert.pem

> The certificates must be in PEM format and must be sorted starting with the subject's certificate (actual client or server certificate), followed by *intermediate* CA certificates if applicable, but *excluding* the
> highest level (root) CA.

Upload the key and certificate to your server host:

    scp server_cert.pem server_key.pem serveruser@server.example.com:/home/serveruser

Login to the server and make sure you restrict the key's file permissions

    cd /home/serveruser
    chmod 600 server_key.pem
    chmod 644 server_cert.pem

> This step is extremely important, especially since we removed the passphrase from the private key! The certificate file is non-critical.

Move the files to your Crossbar.io node directory:

    mv server_key.pem server_cert.pem .crossbar

---

## Creating your own Certificate Authority

The following recipe is for creating your own root certificate authority ("CA"), and certify your server certificates with your own CA to create server certificates.

First, create a new private key for your CA:

    openssl genrsa -aes256 -out ca_key.pem 4096
    chmod 600 ca_key.pem

> As "Common Name" (CN), you could choose something like "Tavendo Certificate Authority". This is different from servers, where CN should be the FQDN, and personal certificates, where the CN should be the Email of the person.

Next, create a certificate for your CA valid for 10 years:

    openssl req -new -x509 -days 3650 -extensions v3_ca -key ca_key.pem -out ca_cert.pem

To check and view your CA certificate:

    openssl x509 -in ca_cert.pem -noout -text

Create a server certificate signed by your CA:

    openssl x509 -req -days 365 -CA ca_cert.pem -CAkey ca_key.pem -CAcreateserial \
       -addreject emailProtection -addreject clientAuth -addtrust serverAuth \
       -in .crossbar/server_csr.pem -out .crossbar/server_cert.pem

View the server certificate:

    openssl x509 -text -noout -in .crossbar/server_cert.pem

---

## Testing

You can use `openssl client` command to check your server in the end:

```console
oberstet@corei7ub1310:~/scm/3rdparty/openssl$ ~/openssl/bin/openssl s_client -brief -connect demo.crossbar.io:443
depth=1 C = IL, O = StartCom Ltd., OU = Secure Digital Certificate Signing, CN = StartCom Class 1 Primary Intermediate Server CA
verify error:num=20:unable to get local issuer certificate
CONNECTION ESTABLISHED
Protocol version: TLSv1.2
Ciphersuite: ECDHE-RSA-AES128-GCM-SHA256
Peer certificate: description = 3FfmiF3b24n8r1Hz, C = DE, CN = demo.crossbar.io, emailAddress = postmaster@crossbar.io
Hash used: SHA384
Supported Elliptic Curve Point Formats: uncompressed:ansiX962_compressed_prime:ansiX962_compressed_char2
Server Temp Key: ECDH, P-256, 256 bits
...
```

---

## Using Lets Encrypt with Crossbar.io

[Let's Encrypt](https://letsencrypt.org/), to quote [Wikipedia](https://en.wikipedia.org/wiki/Let's_Encrypt) (I am lazy), "is a certificate authority that entered public beta on December 3, 2015 that provides free X.509 certificates for Transport Layer Security encryption (TLS) via an automated process designed to eliminate the current complex process of manual creation, validation, signing, installation and renewal of certificates for secure websites."

Alright, anyone who dealt with x509 certs and "classical" CAs will have felt some pain, and should get excited about above!

And the cool thing: it works. Today. And here is how to use Let's Encrypt to secure your Crossbar.io nodes.

So let's encrypt and get busy;)

### Installation

Let's Encrypt works from a tool which is installed on the server for which TLS keys and certificates should be generated.

The client is a Python program, hence you'll need Python on the server.

The client also (at least in "standalone mode") wants to fire up a terminal dialog thing. On Ubuntu, do

```
sudo apt-get install dialog
```

Then clone the official Let's Encrypt repo (`sudo apt-get install git` if you need Git)

```
cd ~
git clone git@github.com:letsencrypt/letsencrypt.git
cd letsencrypt
git checkout v0.1.0
python setup.py install
```

### Create server key and certificate

Assume your server will be reachable under the fully qualified hostname `box1.example.com`, here is how you generate all files needs (public-private key pairs, certificate and such).

In "standalone mode", the Let's Encrypt tool will do an outgoing connection to the Let's Encrypt servers and **shortly** fire up an embedded Web server which the Let's Encrypt servers will contact to verify that you are actually under control of the server.

From a terminal, run

```
sudo `which letsencrypt` certonly --standalone -d box1.example.com
```

The tool will ask you for an Email address, but that's it. Here is the output when successful:


```
IMPORTANT NOTES:
 - If you lose your account credentials, you can recover through
   e-mails sent to tobias.oberstein@tavendo.de.
 - Congratulations! Your certificate and chain have been saved at
   /etc/letsencrypt/live/box1.example.com/fullchain.pem. Your
   cert will expire on 2016-03-13. To obtain a new version of the
   certificate in the future, simply run Let's Encrypt again.
 - Your account credentials have been saved in your Let's Encrypt
   configuration directory at /etc/letsencrypt. You should make a
   secure backup of this folder now. This configuration directory will
   also contain certificates and private keys obtained by Let's
   Encrypt so making regular backups of this folder is ideal.
 - If like Let's Encrypt, please consider supporting our work by:

   Donating to ISRG / Let's Encrypt:   https://letsencrypt.org/donate
   Donating to EFF:                    https://eff.org/donate-le
```

You should now change the owner of the Let's Encrypt folder so that your server software (that will be using the TLS keys and certificates that have been generated) can access and **read** those files.

E.g. assuming you are running Ubuntu on AWS in a EC2 instance from the Ubuntu official image, the default account is named `ubuntu`, and when you plan to run Crossbar.io under that user, you would need to:

```console
sudo chown -R ubuntu:ubuntu /etc/letsencrypt
```

The files in that folder are:

```console
(cpy2_1)ubuntu@ip-172-31-4-183:~$ sudo find /etc/letsencrypt/
/etc/letsencrypt/
/etc/letsencrypt/archive
/etc/letsencrypt/archive/box1.example.com
/etc/letsencrypt/archive/box1.example.com/cert1.pem
/etc/letsencrypt/archive/box1.example.com/chain1.pem
/etc/letsencrypt/archive/box1.example.com/fullchain1.pem
/etc/letsencrypt/archive/box1.example.com/privkey1.pem
/etc/letsencrypt/csr
/etc/letsencrypt/csr/0000_csr-letsencrypt.pem
/etc/letsencrypt/live
/etc/letsencrypt/live/box1.example.com
/etc/letsencrypt/live/box1.example.com/privkey.pem
/etc/letsencrypt/live/box1.example.com/fullchain.pem
/etc/letsencrypt/live/box1.example.com/cert.pem
/etc/letsencrypt/live/box1.example.com/chain.pem
/etc/letsencrypt/renewal
/etc/letsencrypt/renewal/box1.example.com.conf
/etc/letsencrypt/keys
/etc/letsencrypt/keys/0000_key-letsencrypt.pem
/etc/letsencrypt/accounts
/etc/letsencrypt/accounts/acme-v01.api.letsencrypt.org
/etc/letsencrypt/accounts/acme-v01.api.letsencrypt.org/directory
/etc/letsencrypt/accounts/acme-v01.api.letsencrypt.org/directory/0417840b9724dff8a342834a0e82b72e
/etc/letsencrypt/accounts/acme-v01.api.letsencrypt.org/directory/0417840b9724dff8a342834a0e82b72e/private_key.json
/etc/letsencrypt/accounts/acme-v01.api.letsencrypt.org/directory/0417840b9724dff8a342834a0e82b72e/regr.json
/etc/letsencrypt/accounts/acme-v01.api.letsencrypt.org/directory/0417840b9724dff8a342834a0e82b72e/meta.json
```

Essentially, Let's Encrypt has generated a mini-database contained in those files with all the info needed to refresh your certs as well!


### Generate a new Diffie-Hellman group

**optional**

We want to run modern ciphers, and one of those involves [Diffie-Hellman key exchange](https://en.wikipedia.org/wiki/Diffie%E2%80%93Hellman_key_exchange). To use that **safely**, you have to generate another things (a so called group):


```console
openssl dhparam -2 4096 -out /etc/letsencrypt/live/box1.example.com/dhparam.pem
```

> Again, make sure that file is readable by the user Crossbar.io is run under.


### Configure Crossbar.io

Alright, awesome. We have server keys and a certificate. To use that on a Crossbar.io listening transport, you'll need a transport configuration with a `tls` attribute giving the paths to `key`, `certificate` and `chain_certificates`:

```json
"endpoint": {
    "type": "tcp",
    "port": 443,
    "tls": {
        "key": "/etc/letsencrypt/live/box1.example.com/privkey.pem",
        "certificate": "/etc/letsencrypt/live/box1.example.com/cert.pem",
        "chain_certificates": ["/etc/letsencrypt/live/box1.example.com/chain.pem"],
        "dhparam": "/etc/letsencrypt/live/box1.example.com/dhparam.pem",
        "ciphers": "ECDHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-SHA256:DHE-RSA-AES128-SHA256:"
    }
}
```

In above, we are also pointing `dhparam` to the Diffie-Hellman group generated, and we provide an explicit `ciphers` list. Essentially, we disallow all but 4 ciphers altogether. Those ciphers are supported by modern gear, but won't work with deprecated stuff like Windows XP. You shouldn't care much about that, instead press users to upgrade.

---

## Tracking down issues

Tracking down TLS issues can be done using OpenSSL. Eg here is how to check the TLS opening handshake (adjust `-CApath /etc/ssl/certs/` to fit your system .. this works for Ubuntu):


```console
oberstet@thinkpad-t430s:~$ openssl s_client -CApath /etc/ssl/certs/ -showcerts -connect demo.crossbar.io:443
CONNECTED(00000003)
depth=2 O = Digital Signature Trust Co., CN = DST Root CA X3
verify return:1
depth=1 C = US, O = Let's Encrypt, CN = Let's Encrypt Authority X1
verify return:1
depth=0 CN = cbdemo-eu-central-1.crossbar.io
verify return:1
---
Certificate chain
 0 s:/CN=cbdemo-eu-central-1.crossbar.io
   i:/C=US/O=Let's Encrypt/CN=Let's Encrypt Authority X1
-----BEGIN CERTIFICATE-----
MIIFNDCCBBygAwIBAgISAWvkTNHswSHEDMW/5kJc5MaDMA0GCSqGSIb3DQEBCwUA
MEoxCzAJBgNVBAYTAlVTMRYwFAYDVQQKEw1MZXQncyBFbmNyeXB0MSMwIQYDVQQD
ExpMZXQncyBFbmNyeXB0IEF1dGhvcml0eSBYMTAeFw0xNTEyMjAxMDE3MDBaFw0x
NjAzMTkxMDE3MDBaMCoxKDAmBgNVBAMTH2NiZGVtby1ldS1jZW50cmFsLTEuY3Jv
c3NiYXIuaW8wggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCZYgp9QNnQ
phT7r+hbP1TxVCdKdkECyhXW0sLd8qXHGokHZ3HvXbsOc1gLeMPEJtqeMsOW2z0C
aU2dOh4ZzRCO0fCJJqX8wvAgqI3sndubDLUgNI0fbOtrJBnCjLCUPxBqTv+/+KYy
ZOuT3no0l+DZ8E42OG91YRkk+kviJh/MxBpTHrFAcZXuRoeqz6LtyYGIX/+TMcts
kUvtCSVwym1rRYKsGPCCeGv0quBUoOfQtA3rpFuahnFgTS3AK0C2v7jMroGeJavu
B3VeiWe2E4TiSrLaIF1vrKldJKcM3E0sO8mSGIKEg4/dqNusW7KKIPB4/bmFfHt6
g02ey1ALtOk3AgMBAAGjggIyMIICLjAOBgNVHQ8BAf8EBAMCBaAwHQYDVR0lBBYw
FAYIKwYBBQUHAwEGCCsGAQUFBwMCMAwGA1UdEwEB/wQCMAAwHQYDVR0OBBYEFII3
EyHm6bBFbgjDpUoT/GSEQ6fMMB8GA1UdIwQYMBaAFKhKamMEfd265tE5t6ZFZe/z
qOyhMHAGCCsGAQUFBwEBBGQwYjAvBggrBgEFBQcwAYYjaHR0cDovL29jc3AuaW50
LXgxLmxldHNlbmNyeXB0Lm9yZy8wLwYIKwYBBQUHMAKGI2h0dHA6Ly9jZXJ0Lmlu
dC14MS5sZXRzZW5jcnlwdC5vcmcvMDwGA1UdEQQ1MDOCH2NiZGVtby1ldS1jZW50
cmFsLTEuY3Jvc3NiYXIuaW+CEGRlbW8uY3Jvc3NiYXIuaW8wgf4GA1UdIASB9jCB
8zAIBgZngQwBAgEwgeYGCysGAQQBgt8TAQEBMIHWMCYGCCsGAQUFBwIBFhpodHRw
Oi8vY3BzLmxldHNlbmNyeXB0Lm9yZzCBqwYIKwYBBQUHAgIwgZ4MgZtUaGlzIENl
cnRpZmljYXRlIG1heSBvbmx5IGJlIHJlbGllZCB1cG9uIGJ5IFJlbHlpbmcgUGFy
dGllcyBhbmQgb25seSBpbiBhY2NvcmRhbmNlIHdpdGggdGhlIENlcnRpZmljYXRl
IFBvbGljeSBmb3VuZCBhdCBodHRwczovL2xldHNlbmNyeXB0Lm9yZy9yZXBvc2l0
b3J5LzANBgkqhkiG9w0BAQsFAAOCAQEAZZzfsXv7SKNPzsot2vFN7tRnRml7P/YC
JMgRFwdpqcdKKsAhld4vcJPv3kaRMCyfb/02/ckLG4qrvLdply22LBtTyV+/9yJ1
cmiIRRGtplSEVpU9Aqanao4kxG9ZIASdQ9vkv4botYK2x8kWvrtt4eUg9rb68q0x
I0ecFPy3iT3AlFCkf5Ph4SorJvG/y4LyatAMM5sZF0C5XFe35o2ORWjToMAzEBAl
bcCgXLK30+FmHFsHnTultF8zJ358EYtpbNmwLu6CkRB8YV6GI4gjsgOXBCX3KQk2
FNcHRMD7RrXdeS1+vrFMolcRK48jeIpd6E2R9+SSTzkD3mQz7siHYw==
-----END CERTIFICATE-----
 1 s:/C=US/O=Let's Encrypt/CN=Let's Encrypt Authority X1
   i:/O=Digital Signature Trust Co./CN=DST Root CA X3
-----BEGIN CERTIFICATE-----
MIIEqDCCA5CgAwIBAgIRAJgT9HUT5XULQ+dDHpceRL0wDQYJKoZIhvcNAQELBQAw
PzEkMCIGA1UEChMbRGlnaXRhbCBTaWduYXR1cmUgVHJ1c3QgQ28uMRcwFQYDVQQD
Ew5EU1QgUm9vdCBDQSBYMzAeFw0xNTEwMTkyMjMzMzZaFw0yMDEwMTkyMjMzMzZa
MEoxCzAJBgNVBAYTAlVTMRYwFAYDVQQKEw1MZXQncyBFbmNyeXB0MSMwIQYDVQQD
ExpMZXQncyBFbmNyeXB0IEF1dGhvcml0eSBYMTCCASIwDQYJKoZIhvcNAQEBBQAD
ggEPADCCAQoCggEBAJzTDPBa5S5Ht3JdN4OzaGMw6tc1Jhkl4b2+NfFwki+3uEtB
BaupnjUIWOyxKsRohwuj43Xk5vOnYnG6eYFgH9eRmp/z0HhncchpDpWRz/7mmelg
PEjMfspNdxIknUcbWuu57B43ABycrHunBerOSuu9QeU2mLnL/W08lmjfIypCkAyG
dGfIf6WauFJhFBM/ZemCh8vb+g5W9oaJ84U/l4avsNwa72sNlRZ9xCugZbKZBDZ1
gGusSvMbkEl4L6KWTyogJSkExnTA0DHNjzE4lRa6qDO4Q/GxH8Mwf6J5MRM9LTb4
4/zyM2q5OTHFr8SNDR1kFjOq+oQpttQLwNh9w5MCAwEAAaOCAZIwggGOMBIGA1Ud
EwEB/wQIMAYBAf8CAQAwDgYDVR0PAQH/BAQDAgGGMH8GCCsGAQUFBwEBBHMwcTAy
BggrBgEFBQcwAYYmaHR0cDovL2lzcmcudHJ1c3RpZC5vY3NwLmlkZW50cnVzdC5j
b20wOwYIKwYBBQUHMAKGL2h0dHA6Ly9hcHBzLmlkZW50cnVzdC5jb20vcm9vdHMv
ZHN0cm9vdGNheDMucDdjMB8GA1UdIwQYMBaAFMSnsaR7LHH62+FLkHX/xBVghYkQ
MFQGA1UdIARNMEswCAYGZ4EMAQIBMD8GCysGAQQBgt8TAQEBMDAwLgYIKwYBBQUH
AgEWImh0dHA6Ly9jcHMucm9vdC14MS5sZXRzZW5jcnlwdC5vcmcwPAYDVR0fBDUw
MzAxoC+gLYYraHR0cDovL2NybC5pZGVudHJ1c3QuY29tL0RTVFJPT1RDQVgzQ1JM
LmNybDATBgNVHR4EDDAKoQgwBoIELm1pbDAdBgNVHQ4EFgQUqEpqYwR93brm0Tm3
pkVl7/Oo7KEwDQYJKoZIhvcNAQELBQADggEBANHIIkus7+MJiZZQsY14cCoBG1hd
v0J20/FyWo5ppnfjL78S2k4s2GLRJ7iD9ZDKErndvbNFGcsW+9kKK/TnY21hp4Dd
ITv8S9ZYQ7oaoqs7HwhEMY9sibED4aXw09xrJZTC9zK1uIfW6t5dHQjuOWv+HHoW
ZnupyxpsEUlEaFb+/SCI4KCSBdAsYxAcsHYI5xxEI4LutHp6s3OT2FuO90WfdsIk
6q78OMSdn875bNjdBYAqxUp2/LEIHfDBkLoQz0hFJmwAbYahqKaLn73PAAm1X2kj
f1w8DdnkabOLGeOVcj9LQ+s67vBykx4anTjURkbqZslUEUsn2k5xeua2zUk=
-----END CERTIFICATE-----
---
Server certificate
subject=/CN=cbdemo-eu-central-1.crossbar.io
issuer=/C=US/O=Let's Encrypt/CN=Let's Encrypt Authority X1
---
No client certificate CA names sent
---
SSL handshake has read 3047 bytes and written 421 bytes
---
New, TLSv1/SSLv3, Cipher is ECDHE-RSA-AES128-GCM-SHA256
Server public key is 2048 bit
Secure Renegotiation IS supported
Compression: NONE
Expansion: NONE
SSL-Session:
    Protocol  : TLSv1.2
    Cipher    : ECDHE-RSA-AES128-GCM-SHA256
    Session-ID: 688D6B2F826CCFEEC48AE4E17E351D55AF2138762FCF8906E23047E97A1304B4
    Session-ID-ctx:
    Master-Key: 1BCE4C7CB9DBE234220EDF789CC07FCF9BE94B369C91AACF8C81FE7886D9C1E3E5A002BDF99A8881E5DBA09E7D80224C
    Key-Arg   : None
    PSK identity: None
    PSK identity hint: None
    SRP username: None
    Start Time: 1453186799
    Timeout   : 300 (sec)
    Verify return code: 0 (ok)
---
^C
```

---

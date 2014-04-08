## Installation

* [cryptography](https://crossbar.io.s3.amazonaws.com/download/python/cryptography-0.2.dev1.win32-py2.7.exe)
* [pyopenssl](https://crossbar.io.s3.amazonaws.com/download/python/pyOpenSSL-0.14a4.win32.exe)

### Python Cryptography package on Windows

Get and install the latest *full* OpenSSL distribution (incude development headers) from [here](http://slproweb.com/download/Win32OpenSSL-1_0_1f.exe). 

Open "Visual Studio 2008-Eingabeaufforderung" and set

	set INCLUDE=C:\OpenSSL-Win32\include;%INCLUDE%
	set LIB=C:\OpenSSL-Win32\lib;%LIB%

Clone the cryptography [repo](https://github.com/pyca/cryptography)

	git clone git@github.com:pyca/cryptography.git

and run (within the shell above)

	python setup.py install

To build a Windows installer package

	python setup.py bdist_wininst

which should produce a file

	dist\cryptography-0.2.dev1.win32-py2.7.exe

Clone the pyopenssl [repo](https://github.com/pyca/pyopenssl)

	git clone git@github.com:pyca/pyopenssl.git
	git checkout 0.14a4

and run (within the shell above)

	python setup.py install

To build a Windows installer package

	python setup.py bdist_wininst

which should produce a file

	dist\pyOpenSSL-0.14a4.win32.exe

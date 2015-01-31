# Application Templates

Crossbar.io is able to generate applications from application templates. This directory
contains these application templates.

## Licensing

The code for application templates within this folder (and folders beneath) is licensed under the [BSD 2-clause open-source license](http://opensource.org/licenses/BSD-2-Clause) or the Apache 2.0 license.

The same licenses applie to the code *generated* from the application templates here.

E.g., when you do

	crossbar init --template hello:python --appdir $HOME/hello

Crossbar.io will generate a new WAMP application in the `$HOME/hello` directory from the application template in [hello/python](hello/python). All files generated in `$HOME/hello` are licensed under above licenses.

### Template Developers

For developers of application templates for Crossbar.io, all source files must contain the following copyright header:

```python
###############################################################################
##
##  Copyright (C) 2014, Tavendo GmbH and/or collaborators. All rights reserved.
## 
##  Redistribution and use in source and binary forms, with or without
##  modification, are permitted provided that the following conditions are met:
## 
##  1. Redistributions of source code must retain the above copyright notice,
##     this list of conditions and the following disclaimer.
## 
##  2. Redistributions in binary form must reproduce the above copyright notice,
##     this list of conditions and the following disclaimer in the documentation
##     and/or other materials provided with the distribution.
## 
##  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
##  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
##  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
##  ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
##  LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
##  CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
##  SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
##  INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
##  CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
##  ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
##  POSSIBILITY OF SUCH DAMAGE.
##
###############################################################################
```

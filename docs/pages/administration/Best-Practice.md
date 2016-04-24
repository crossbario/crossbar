

Ubuntu 16.04 LTS DEVEL

https://cloud-images.ubuntu.com/locator/ec2/


https://console.aws.amazon.com/ec2/home?region=eu-central-1#launchAmi=ami-10da3f7f


t2-medium



sudo apt-get update
sudo apt-get -y dist-upgrade


sudo apt-get -y install build-essential libssl-dev libffi-dev \
   libreadline-dev libbz2-dev libsqlite3-dev libncurses5-dev


sudo apt-get install python3 python3-dev python3-pip

sudo pip3 install -U pip
sudo pip3 install setuptools virtualenv


mkdir -p ~/.svc
virtualenv ~/.svc/mysvc1
~/.svc/mysvc1/bin/pip install -r requirements.txt



README.md
requirements.txt
setup.py
example-svc
example-svc/__init__.py
example-svc/main.py
linux/example-svc.service
linux/Makefile
freebsd/run
freebsd/run-log
freebsd/Makefile
test/.crossbar
test/.crossbar/config.json
test/web
test/web/index.html


Prepare service directory

sudo mkdir /var/svc

Prepare service user

svc

0) Scaffold service

crossbar init --template service:autobahn-py-tx
crossbar init --template service:autobahn-py-aio
crossbar init --template service:autobahn-js
crossbar init --template service:autobahn-cpp

crossbar init --template autobahn-python:service
crossbar init --template autobahn-cpp:service


crossbar init --template service:python-twisted \
              --param target=linux-systemd \
              --param router=unix:/tmp/cb.sock \
              --param name=myservice1 \
              --param parallel=8

crossbar init --template service:pyaio
crossbar init --template service:js
crossbar init --template service:cpp


service:autobahn-python-twisted:freebsd-daemontools
service:autobahn-python-twisted:linux-systemd


1) Create new virtualenv

sudo virtualenv /var/svc/example-svc

2) Install dependencies

sudo /var/svc/example-svc/bin/pip install -r requirements.txt

3) Install service package

sudo /var/svc/example-svc/bin/pip install .

4) Setup and start service

sudo cp example-svc.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start example-svc

all:
	@echo "Targets:"
	@echo "install:  Install PHP dependencies"
	@echo "start:    Run Crossbar.io"

install:
	composer require "ratchet/pawl":"dev-master"
	composer require "voryx/thruway":"dev-master"

start:
	crossbar start

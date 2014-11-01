all:
	@echo "Targets:"
	@echo ""
	@echo "   create_users		Create the Crossbar.io Oracle database integration users/schemas"
	@echo "   install 			Install the Crossbar.io Oracle database integration"
	@echo "   uninstall 			Uninstalls the Crossbar.io Oracle database integration"
	@echo "   remove_users 		Removes the Crossbar.io Oracle database integration users/schemas"
	@echo ""
	@echo "Hint: First do 'make create_users', then 'make install'."
	@echo "The default target Oracle database is ORCL on localhost:1521. You need to adjust the Makefile if your Oracle instance resides somewhere else."
	@echo ""

users:
	@echo "Installing Crossbar.io database integration users/schemas CDDB and CBADAPTER"
	@echo "Hint: The default password for SYS is 'oracle' .."
	sqlplus sys@\"localhost:1521/orcl\" as sysdba @create_users.sql

install:
	@echo "Installing Crossbar.io database integration under schema CDDB"
	@echo "Hint: The default password for CBDB is 'crossbar' .."
	sqlplus cbdb@\"localhost:1521/orcl\" @install.sql

uninstall:
	@echo "Uninstalling Crossbar.io database integration from schema CDDB"
	@echo "Hint: The default password for CBDB is 'crossbar' .."
	sqlplus cbdb@\"localhost:1521/orcl\" @uninstall.sql

remove_users:
	@echo "Removing Crossbar.io database integration users/schemas CDDB and CBADAPTER"
	@echo "Hint: The default password for SYS is 'oracle' .."
	sqlplus sys@\"localhost:1521/orcl\" as sysdba @remove_users.sql

.PHONY: clean html publish

help:
	@echo "Targets:"
	@echo "  clean      clean everything"
	@echo "  html       to make standalone HTML files"
	@echo "  publish    to publish the documentation to http://crossbar.io"

clean:
	rm -rf ./_build

html:
	sphinx-build -b html -d _build/doctrees . _build/html

publish: html
	s3cmd sync -P --delete-removed ./_build/html/ s3://crossbar.io/management-api/

help:
	@echo "Please use 'make <target>' where <target> is one of"
	@echo "  clean           remove temporary files created by build tools"
	@echo "  cleanall        all the above + tmp files from development tools"
	@echo "  test            run test suite"
	@echo "  sdist           make a source distribution"
	@echo "  bdist           make an egg distribution"
	@echo "  install         install package"

clean:
	-rm -f MANIFEST
	-rm -rf dist/
	-rm -rf build/
	-rm -rf redis_cluster.egg-info/

cleanall: clean cleancoverage
	-find . -type f -name "*~" -exec rm -f "{}" \;
	-find . -type f -name "*.orig" -exec rm -f "{}" \;
	-find . -type f -name "*.rej" -exec rm -f "{}" \;
	-find . -type f -name "*.pyc" -exec rm -f "{}" \;
	-find . -type f -name "*.parse-index" -exec rm -f "{}" \;

test:
	python runtests.py
	pep8 --ignore=E501,E241 --show-source --exclude=.vev,.tox,dist,doc,build,*.egg .

sdist:
	python setup.py sdist

bdist:
	python setup.py bdist_egg

install:
	python setup.py install

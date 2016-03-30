# Tox - Multi environment testing

Tox is the easiest way to run all tests because it will manage all dependencies and run the correct test command for you.

TravisCI will use tox to run tests on all supported python & hiredis versions.

Install tox with `pip install tox`

To run all environments you need all supported python versions installed on your machine. (See supported python versions list) and you also need the python-dev package for all python versions to build hiredis.

To run a specific python version use either `tox -e py27` or `tox -e py34`

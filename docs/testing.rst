Testing
=======

All tests are currently built around a 6 redis server cluster setup (3 masters + 3 slaves). One server must be using port 7000 for redis cluster discovery.

The easiest way to setup a cluster is to use either a Docker or Vagrant. They are both described in [Setup a redis cluster. Manually, Docker & Vagrant](docs/Cluster_Setup.md).



Tox - Multi environment testing
-------------------------------

To run all tests in all supported environments with `tox` read this [Tox multienv testing](docs/Tox.md)

Tox is the easiest way to run all tests because it will manage all dependencies and run the correct test command for you.

TravisCI will use tox to run tests on all supported python & hiredis versions.

Install tox with `pip install tox`

To run all environments you need all supported python versions installed on your machine. (See supported python versions list) and you also need the python-dev package for all python versions to build hiredis.

To run a specific python version use either `tox -e py27` or `tox -e py34`

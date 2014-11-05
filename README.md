# redis-py-cluster

Redis cluster client in python for the official cluster support targeted for redis 3.0.

This project is a port of `redis-rb-cluster` by antirez, with alot of added functionality. The original source can be found at https://github.com/antirez/redis-rb-cluster

[![Build Status](https://travis-ci.org/Grokzen/redis-py-cluster.svg?branch=master)](https://travis-ci.org/Grokzen+/redis-py-cluster) [![Coverage Status](https://coveralls.io/repos/Grokzen/redis-py-cluster/badge.png)](https://coveralls.io/r/Grokzen/redis-py-cluster) [![Latest Version](https://pypip.in/version/redis-py-cluster/badge.svg)](https://pypi.python.org/pypi/redis-py-cluster/) [![Downloads](https://pypip.in/download/redis-py-cluster/badge.svg)](https://pypi.python.org/pypi/redis-py-cluster/) [![Supported Python versions](https://pypip.in/py_versions/redis-py-cluster/badge.svg)](https://pypi.python.org/pypi/redis-py-cluster/) [![License](https://pypip.in/license/redis-py-cluster/badge.svg)](https://pypi.python.org/pypi/redis-py-cluster/) [![Gitter](https://badges.gitter.im/Join Chat.svg)](https://gitter.im/Grokzen/redis-py-cluster?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)



## Dependencies & supported python versions

- redis >= 2.9.1
- Cluster enabled redis servers. Only Redis 3.0 beta.7 and above is supported because of CLUSTER SLOTS command was introduced in that release.

Current python support is

- 2.7 + hiredis
- 3.2 + hiredis
- 3.3 + hiredis
- 3.4 + hiredis



## Installation

Latest stable release from pypi

```
$ pip install redis-py-cluster
```

or from source

```
$ python setup.py install
```



## Usage example

Small sample script that show how to get started with RedisCluster. `decode_responses=True` is required to have when running on python3.

```python
>>> from rediscluster import RedisCluster
>>> startup_nodes = [{"host": "127.0.0.1", "port": "7000"}]
>>> rc = RedisCluster(startup_nodes=startup_nodes, decode_responses=True)
>>> rc.set("foo", "bar")
True
>>> rc.get("foo")
'bar'
```



## Testing

All tests are currently built around a 8 redis server cluster setup (5 masters + 3 slaves). One server must be using port 7000 for redis cluster discovery, and 2 other masters must be using 7006, 7007 for testing single-server cluster.

The easiest way to setup a cluster is to use either a Docker or Vagrant. They are both described in [Setup a redis cluster. Manually, Docker & Vagrant](docs/Cluster_Setup.md).



### Tox - Multi environment testing

Tox is the easiest way to run all tests because it will manage all dependencies and run the correct test command for you.

TravisCI will use tox to run tests on all supported python & hiredis versions.

Install tox with `pip install tox`

To run all environments you need all supported python versions installed on your machine. (See supported python versions list) and you also need the python-dev package for all python versions to build hiredis.

To run a specific python version use either `tox -e py27` or `tox -e py34`



## More documentation

More detailed documentation can be found in `docs` folder.

- [Pubsub](docs/Pubsub.md)
- [Setup a redis cluster. Manually, Docker & Vagrant](docs/Cluster_Setup.md)
- [Command differences](docs/Commands.md)
- [Limitations and differences](docs/Limits_and_differences.md)
- [Redisco support (Django ORM)](docs/Redisco.md)
- [Authors](docs/Authors)



## Disclaimer

Both this client and Redis Cluster are a work in progress that is not suitable to be used in production environments. This is only my current personal opinion about both projects.



## License & Authors

MIT (See docs/License.txt file)

The license should be the same as redis-py (https://github.com/andymccurdy/redis-py)

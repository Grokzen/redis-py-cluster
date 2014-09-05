# redis-py-cluster

Python cluster client for the official cluster support targeted for redis 3.0

This project is a port of `redis-rb-cluster` by antirez, with alot of added functionality. The original source can be found at https://github.com/antirez/redis-rb-cluster

[![Build Status](https://travis-ci.org/Grokzen/redis-py-cluster.svg?branch=master)](https://travis-ci.org/Grokzen/redis-py-cluster) - [![Coverage Status](https://coveralls.io/repos/Grokzen/redis-py-cluster/badge.png)](https://coveralls.io/r/Grokzen/redis-py-cluster)



## Dependencies & supported python versions

- redis >= 2.9.1 (Python client - https://github.com/andymccurdy/redis-py - Install [pip install redis])
- Cluster enabled redis servers. Only Redis 3.0 beta.7 and above is supported because of CLUSTER SLOTS command was introduced in that release.

Current python support is

- 2.7 + hiredis
- 3.2 + hiredis
- 3.3 + hiredis
- 3.4 + hiredis



## Installation

Currently no package is available in pypi.

Currently only way to install is to clone the repo and either create a sdist with `make sdist` or install manually with `python setup.py install`.



## Usage example

Small sample script that show how to get started with RedisCluster(). 'decode_responses=True' is required to have when running on python3.

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

All tests are currently built around a 6 redis server cluster setup (3 masters + 3 slaves), but may change in the future. One server must be using port 7000 for tests.

The easiest way to setup a cluster is to use either a Docker or Vagrant machine. They are both described in [Setup a redis cluster. Manually, Docker & Vagrant](docs/Cluster_Setup.md).

All tests must pass in all environments before a code fix will be accepted.



### Tox - Multi environment testing

Tox is the easiest way to run all tests because it will manage all dependencies and run the correct test command for you.

To install tox run `pip install tox`

To run all environments you need all supported python versions installed on your machine. (See supported python versions list) and you also need the python-dev package for all python versions to build hiredis.

To run a specific python version inside tox, run either `tox -e py27` or `tox -e py34`



## More documentation

More detailed documentation can be found in `docs` folder.

- [Setup a redis cluster. Manually, Docker & Vagrant](docs/Cluster_Setup.md)
- [Command differences](docs/Commands.md)
- [Limitations and differences](docs/Limits_and_differences.md)
- [Redisco support (Django ORM)](docts/Redisco.md)



## Disclaimer

Both this client and Redis Cluster are a work in progress that is not suitable to be used in production environments. This is only my current personal opinion about both projects.



## License

MIT (See LICENSE file)

The license should be the same as redis-py library (https://github.com/andymccurdy/redis-py)

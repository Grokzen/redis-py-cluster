# redis-py-cluster

Redis cluster client in python for the official cluster support targeted for redis 3.0.

This project is a port of `redis-rb-cluster` by antirez, with alot of added functionality. The original source can be found at https://github.com/antirez/redis-rb-cluster

[![Build Status](https://travis-ci.org/Grokzen/redis-py-cluster.svg?branch=master)](https://travis-ci.org/Grokzen/redis-py-cluster) [![Coverage Status](https://coveralls.io/repos/Grokzen/redis-py-cluster/badge.png)](https://coveralls.io/r/Grokzen/redis-py-cluster) [![Latest Version](https://pypip.in/version/redis-py-cluster/badge.svg)](https://pypi.python.org/pypi/redis-py-cluster/) [![Downloads](https://pypip.in/download/redis-py-cluster/badge.svg)](https://pypi.python.org/pypi/redis-py-cluster/) [![Supported Python versions](https://pypip.in/py_versions/redis-py-cluster/badge.svg)](https://pypi.python.org/pypi/redis-py-cluster/) [![License](https://pypip.in/license/redis-py-cluster/badge.svg)](https://pypi.python.org/pypi/redis-py-cluster/) [![Gitter](https://badges.gitter.im/Join Chat.svg)](https://gitter.im/Grokzen/redis-py-cluster?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge) [![Code Health](https://landscape.io/github/Grokzen/redis-py-cluster/unstable/landscape.svg)](https://landscape.io/github/Grokzen/redis-py-cluster/unstable)



## Upgrading instructions

Please read the [following](docs/Upgrading.md) documentation that will go through all changes that is required when upgrading `redis-py-cluster` between versions.



## Dependencies & supported python versions

- redis >= 2.10.2
- Cluster enabled redis servers. Only Redis 3.0 beta.7 and above is supported because of CLUSTER SLOTS command was introduced in that release.
- Optional: hiredis >= 0.1.3

Hiredis is tested and supported on all supported python versions.

Supported python versions:

- 2.7.x
- 3.2.x
- 3.3.x
- 3.4.1+

Python 3.4.0 do not not work with pubsub because of segfault issues (Same as redis-py has). If rediscluster is runned on 3.4.0 it will raise RuntimeError exception and exit. If you get this error locally when running tox, consider using `pyenv` to fix this problem.



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
>>> from rediscluster import StrictRedisCluster
>>> startup_nodes = [{"host": "127.0.0.1", "port": "7000"}]
>>> rc = StrictRedisCluster(startup_nodes=startup_nodes, decode_responses=True)
>>> rc.set("foo", "bar")
True
>>> rc.get("foo")
'bar'
```

The following imports can be imported from `redis` package. 

- `StrictRedisCluster`
- `RedisCluster`
- `StrictClusterPipeline` 
- `ClusterPubSub` 

`StrictRedisCluster` is based on `redis.StrictRedis` and `RedisCluster` has the same functionality as `redis.Redis` even if it is not directly based on it.



## Testing

All tests are currently built around a 6 redis server cluster setup (3 masters + 3 slaves). One server must be using port 7000 for redis cluster discovery.

The easiest way to setup a cluster is to use either a Docker or Vagrant. They are both described in [Setup a redis cluster. Manually, Docker & Vagrant](docs/Cluster_Setup.md).



### Tox - Multi environment testing

Tox is the easiest way to run all tests because it will manage all dependencies and run the correct test command for you.

TravisCI will use tox to run tests on all supported python & hiredis versions.

Install tox with `pip install tox`

To run all environments you need all supported python versions installed on your machine. (See supported python versions list) and you also need the python-dev package for all python versions to build hiredis.

To run a specific python version use either `tox -e py27` or `tox -e py34`



## More documentation

More detailed documentation can be found in `docs` folder.

- [Benchmarks](docs/Benchmarks.md)
- [Pubsub](docs/Pubsub.md)
- [Setup a redis cluster. Manually, Docker & Vagrant](docs/Cluster_Setup.md)
- [Command differences](docs/Commands.md)
- [Limitations and differences](docs/Limits_and_differences.md)
- [Redisco support (Django ORM)](docs/Redisco.md)
- [Threaded Pipeline support](docs/Threads.md)
- [Authors](docs/Authors)



## Disclaimer

Both this client and Redis Cluster are a work in progress that is not suitable to be used in production environments. This is only my current personal opinion about both projects.



## License & Authors

MIT (See docs/License.txt file)

The license should be the same as redis-py (https://github.com/andymccurdy/redis-py)

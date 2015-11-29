# redis-py-cluster

This client provides a working client for redis cluster that was added in redis 3.0.

This project is a port of `redis-rb-cluster` by antirez, with alot of added functionality. The original source can be found at https://github.com/antirez/redis-rb-cluster

[![Build Status](https://travis-ci.org/Grokzen/redis-py-cluster.svg?branch=master)](https://travis-ci.org/Grokzen/redis-py-cluster) [![Coverage Status](https://coveralls.io/repos/Grokzen/redis-py-cluster/badge.png)](https://coveralls.io/r/Grokzen/redis-py-cluster) [![PyPI version](https://badge.fury.io/py/redis-py-cluster.svg)](http://badge.fury.io/py/redis-py-cluster) [![Code Health](https://landscape.io/github/Grokzen/redis-py-cluster/unstable/landscape.svg)](https://landscape.io/github/Grokzen/redis-py-cluster/unstable)



# Project status

If you have a problem with the code or general questions about this lib, you can ping me inside the gitter channel that you can find here [![Gitter](https://badges.gitter.im/Join Chat.svg)](https://gitter.im/Grokzen/redis-py-cluster?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge) and i will help you out with problems or usage of this lib.

As of release `1.0.0` this project will be considered stable and usable in production. If you are going to use redis cluster in your project, you should read up on all documentation that you can find in the bottom of this Readme file. It will contain usage examples and descriptions of what is and what is not implemented. It will also describe how and why things work the way they do in this client.

On the topic about porting/moving this code into `redis-py` there is currently work over here https://github.com/andymccurdy/redis-py/pull/604 that will bring cluster support based on this code. But my suggestion is that until that work is completed that you should use this lib.



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

Small sample script that shows how to get started with RedisCluster. It can also be found in [examples/basic.py](examples/basic.py)

```python
>>> from rediscluster import StrictRedisCluster

>>> startup_nodes = [{"host": "127.0.0.1", "port": "7000"}]

>>> # Note: decode_responses must be set to True when used with python3
>>> rc = StrictRedisCluster(startup_nodes=startup_nodes, decode_responses=True)

>>> rc.set("foo", "bar")
True
>>> print(rc.get("foo"))
'bar'
```



## Upgrading instructions

Please read the [following](docs/Upgrading.md) documentation that will go through all changes that is required when upgrading `redis-py-cluster` between versions.



## Dependencies & supported python versions

- Python: redis >= `2.10.2`, <= `2.10.5` is required.
  Older versions in the `2.10.x` series can work but using the latest one is allways recommended.
- Optional Python: hiredis >= `0.2.0`. Older versions might work but is not tested.
- A working Redis cluster based on version >= `3.0.0` is required. Only `3.0.x` releases is supported.

Latest release of `Hiredis` is tested on all supported python versions.

List of all supported python versions.

- 2.7
- 3.3
- 3.4.1+
- 3.5

Experimental:

- Python 3.6.0a0


### Python 3.4.0

A segfault was found when running `redis-py` in python `3.4.0` that was introduced into the codebase in python `3.4.0`. Because of this both `redis-py` and `redis-py-cluster` will not work when running with `3.4.0`. This lib has decided to block the lib from execution on `3.4.0` and you will get a exception when trying to import the code. The only solution is to use python `3.4.1` or some other higher minor version in the `3.4` series.



## Testing

All tests are currently built around a 6 redis server cluster setup (3 masters + 3 slaves). One server must be using port 7000 for redis cluster discovery.

The easiest way to setup a cluster is to use either a Docker or Vagrant. They are both described in [Setup a redis cluster. Manually, Docker & Vagrant](docs/Cluster_Setup.md).

To run all tests in all supported environments with `tox` read this [Tox multienv testing](docs/Tox.md)



## More documentation

More detailed documentation can be found in `docs` folder.

- [Authors](docs/Authors)
- [Benchmarks](docs/Benchmarks.md)
- [Cluster Management class](docs/ClusterMgt.md)
- [Command differences](docs/Commands.md)
- [Limitations and differences](docs/Limits_and_differences.md)
- [Pipelines](docs/Pipelines.md)
- [Pubsub](docs/Pubsub.md)
- [READONLY mode](docs/Readonly_mode.md)
- [Redisco support (Django ORM)](docs/Redisco.md)
- [Setup a redis cluster. Manually, Docker & Vagrant](docs/Cluster_Setup.md)
- [Threaded Pipeline support](docs/Threads.md)



## Disclaimer

Both Redis cluster and redis-py-cluster is considered stable and production ready.

But this depends on what you are going to use clustering for. In the simple use cases with SET/GET and other single key functions there is not issues. If you require multi key functinoality or pipelines then you must be very careful when developing because they work slightly different from the normal redis server.

If you require advance features like pubsub or scripting, this lib and redis do not handle that kind of use-cases very well. You either need to develop a custom solution yourself or use a non clustered redis server for that.

Finally, this lib itself is very stable and i know of atleast 2 companies that use this in production with high loads and big cluster sizes.



## License & Authors

MIT (See docs/License.txt file)

The license should be the same as redis-py (https://github.com/andymccurdy/redis-py)

# redis-py-cluster

Redis cluster client in python for the official cluster support targeted for redis 3.0.

This project is a port of `redis-rb-cluster` by antirez, with alot of added functionality. The original source can be found at https://github.com/antirez/redis-rb-cluster

[![Build Status](https://travis-ci.org/Grokzen/redis-py-cluster.svg?branch=master)](https://travis-ci.org/Grokzen/redis-py-cluster) [![Coverage Status](https://coveralls.io/repos/Grokzen/redis-py-cluster/badge.png)](https://coveralls.io/r/Grokzen/redis-py-cluster) [![PyPI version](https://badge.fury.io/py/pykwalify.svg)](http://badge.fury.io/py/pykwalify) [![Gitter](https://badges.gitter.im/Join Chat.svg)](https://gitter.im/Grokzen/redis-py-cluster?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge) [![Code Health](https://landscape.io/github/Grokzen/redis-py-cluster/unstable/landscape.svg)](https://landscape.io/github/Grokzen/redis-py-cluster/unstable)



# Project status

The project is not dead but not much new development is done right now. I do awnser issue reports and pull requests as soon as possible and if you have a problem you can ping me inside the gitter channel that you can find here [![Gitter](https://badges.gitter.im/Join Chat.svg)](https://gitter.im/Grokzen/redis-py-cluster?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge) and i will help you out with problems or usage of this lib.

As of release `0.3.0` this project will be considered stable and usable in production. Just remember that if you are going to use redis cluster to please reda up on the documentation that you can find in the bottom of this Readme. It will contain usage examples and descriptions of what is implemented and what is not implemented and why things are the way they are.

On the topic about porting/moving this code into `redis-py` there is currently work over here https://github.com/andymccurdy/redis-py/pull/604 that will bring cluster uspport based on this code. But my suggestion is that until that work is completed that you should use this lib.



## Upgrading instructions

Please read the [following](docs/Upgrading.md) documentation that will go through all changes that is required when upgrading `redis-py-cluster` between versions.



## Dependencies & supported python versions

- Python: redis >= `2.10.2` is required
- Redis server >= `3.0.0` is required
- Optional Python: hiredis >= `0.1.3`

Hiredis is tested and supported on all supported python versions.

Supported python versions, all minor releases in each major version should be supported unless otherwise stated here:

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

To run all tests in all supported environments with `tox` read this [Tox multienv testing](docs/Tox.md)



## More documentation

More detailed documentation can be found in `docs` folder.

- [Benchmarks](docs/Benchmarks.md)
- [Pubsub](docs/Pubsub.md)
- [Setup a redis cluster. Manually, Docker & Vagrant](docs/Cluster_Setup.md)
- [Command differences](docs/Commands.md)
- [Limitations and differences](docs/Limits_and_differences.md)
- [Redisco support (Django ORM)](docs/Redisco.md)
- [Pipelines](docs/Pipelines.md)
- [Threaded Pipeline support](docs/Threads.md)
- [Cluster Management class](docs/ClusterMgt.md)
- [Authors](docs/Authors)



## Disclaimer

Both Redis cluster and redis-py-cluster is considered stable and production ready.

But this depends on what you are going to use clustering for. In the simple use cases with SET/GET and other single key functions there is not issues. If you require multi key functinoality or pipelines then you must be very carefull when developing because they work slightly different from the normal redis server.

If you require advance features like pubsub or scripting, this lib and redis do not handle that kind of use-cases very well. You either need to develop a custom solution yourself or use a non clustered redis server for that.

Finally, this lib itself is very stable and i know of atleast 2 companies that use this in production with high loads and big cluster sizes.



## License & Authors

MIT (See docs/License.txt file)

The license should be the same as redis-py (https://github.com/andymccurdy/redis-py)

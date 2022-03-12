# redis-py-cluster EOL

In the upstream package *redis-py* that this librar extends, they have since version `* 4.1.0 (Dec 26, 2021)` ported in this code base into the main branch. That basically ends the need for this package if you are using any version after that release as it is natively supported there. If you are upgrading your redis-py version you should plan in time to migrate out from this package into their package. The move into the first released version should be seamless with very few and small changes required. This means that the release `2.1.x` is the very last major release of this package. This do not mean that there might be some small support version if that is needed to sort out some critical issue here. This is not expected as the development time spent on this package in the last few years have been very low. This repo will not be put into a real github Archive mode but this repo should be considered in archive state.

I want to give a few big thanks to some of the people that has provided many contributions, work, time and effort into making this project into what it is today. First is one of the main contributors 72Squared and his team who helped to build many of the core features and trying out new and untested code and provided many optimizations. The team over at AWS for putting in the time and effort and skill into porting over this to `redis-py`. The team at RedisLabs for all of their support and time in creating a fantastic redis community the last few years. Antirez for making the reference client which this repo was written and based on and for making one of my favorite databases in the ecosystem. And last all the contributions and use of this repo by the entire community.


# redis-py-cluster

This client provides a client for redis cluster that was added in redis 3.0.

This project is a port of `redis-rb-cluster` by antirez, with a lot of added functionality. The original source can be found at https://github.com/antirez/redis-rb-cluster

[![Build Status](https://travis-ci.org/Grokzen/redis-py-cluster.svg?branch=master)](https://travis-ci.org/Grokzen/redis-py-cluster) [![Coverage Status](https://coveralls.io/repos/Grokzen/redis-py-cluster/badge.png)](https://coveralls.io/r/Grokzen/redis-py-cluster) [![PyPI version](https://badge.fury.io/py/redis-py-cluster.svg)](http://badge.fury.io/py/redis-py-cluster)

The branch `master` will always contain the latest unstable/development code that has been merged from Pull Requests. Use the latest commit from master branch on your own risk, there is no guarantees of compatibility or stability of non tagged commits on the master branch. Only tagged releases on the `master` branch is considered stable for use.


# Python 2 Compatibility Note

This library follows the announced change from our upstream package redis-py. Due to this,
we will follow the same python 2.7 deprecation timeline as stated in there.

redis-py-cluster 2.1.x will be the last major version release that supports Python 2.7.
The 2.1.x line will continue to get bug fixes and security patches that
support Python 2 until August 1, 2020. redis-py-cluster 3.0.x will be the next major
version and will require Python 3.5+.


# Documentation

All documentation can be found at https://redis-py-cluster.readthedocs.io/en/master

This Readme contains a reduced version of the full documentation.

Upgrading instructions between each released version can be found [here](docs/upgrading.rst)

Changelog for next release and all older releases can be found [here](docs/release-notes.rst)



## Installation

Latest stable release from pypi

```
$ pip install redis-py-cluster
```

This major version of `redis-py-cluster` supports `redis-py >=3.0.0, <4.0.0`.



## Usage example

Small sample script that shows how to get started with RedisCluster. It can also be found in [examples/basic.py](examples/basic.py)

```python
>>> from rediscluster import RedisCluster

>>> # Requires at least one node for cluster discovery. Multiple nodes is recommended.
>>> startup_nodes = [{"host": "127.0.0.1", "port": "7000"}, {"host": "127.0.0.1", "port": "7001"}]
>>> rc = RedisCluster(startup_nodes=startup_nodes, decode_responses=True)

# Or you can use the simpler format of providing one node same way as with a Redis() instance
<<< rc = RedisCluster(host="127.0.0.1", port=7000, decode_responses=True)

>>> rc.set("foo", "bar")
True
>>> print(rc.get("foo"))
'bar'
```



## License & Authors

Copyright (c) 2013-2021 Johan Andersson

MIT (See docs/License.txt file)

The license should be the same as redis-py (https://github.com/andymccurdy/redis-py)

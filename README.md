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
>>> startup_nodes = [{"host": "127.0.0.1", "port": "7000"}]

>>> rc = RedisCluster(startup_nodes=startup_nodes, decode_responses=True)

>>> rc.set("foo", "bar")
True
>>> print(rc.get("foo"))
'bar'
```



## License & Authors

Copyright (c) 2013-2021 Johan Andersson

MIT (See docs/License.txt file)

The license should be the same as redis-py (https://github.com/andymccurdy/redis-py)

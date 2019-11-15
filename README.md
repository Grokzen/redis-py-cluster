# redis-py-cluster

This client provides a client for redis cluster that was added in redis 3.0.

This project is a port of `redis-rb-cluster` by antirez, with a lot of added functionality. The original source can be found at https://github.com/antirez/redis-rb-cluster

[![Build Status](https://travis-ci.org/Grokzen/redis-py-cluster.svg?branch=master)](https://travis-ci.org/Grokzen/redis-py-cluster) [![Coverage Status](https://coveralls.io/repos/Grokzen/redis-py-cluster/badge.png)](https://coveralls.io/r/Grokzen/redis-py-cluster) [![PyPI version](https://badge.fury.io/py/redis-py-cluster.svg)](http://badge.fury.io/py/redis-py-cluster)



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

This major version of `redis-py-cluster` supports `redis-py>=3.0.0,<3.1.0`.



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

Copyright (c) 2013-2019 Johan Andersson

MIT (See docs/License.txt file)

The license should be the same as redis-py (https://github.com/andymccurdy/redis-py)

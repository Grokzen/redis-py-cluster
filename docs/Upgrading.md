# Upgrading redis-py-cluster

This document will describe what must be done when upgrading between different versions to ensure that code still works.


## 0.2.0 --> 0.3.0

In `0.3.0` release the name of the client class was changed from `RedisCluster` to `StrictRedisCluster` and a new implementation of `RedisCluster` was added that is based on `redis.Redis` class. This was done to enable implementation a cluster enabled version of `redis.Redis` class.

Because of this all imports and usage of `RedisCluster` must be changed to `StrictRedisCluster` so that existing code will remain working. If this is not done some issues could arise in existing code.



## 0.1.0 --> 0.2.0

No major changes was done.

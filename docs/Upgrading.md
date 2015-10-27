# Upgrading redis-py-cluster

This document will describe what must be done when upgrading between different versions to ensure that code still works.


## 1.0.0 --> Next release

The following exceptions have been changed/added and code that use this client might have to be updated to handle the new classes.

`raise RedisClusterException("Too many Cluster redirections")` have been changed to `raise ClusterError('TTL exhausted.')`

`ClusterDownException` have been replaced with `ClusterDownError`

Added new `AskError` exception class.

Added new `TryAgainError` exception class.

Added new `MovedError` exception class.

Added new `ClusterCrossSlotError` exception class.

Added optional `max_connections_per_node` parameter to `ClusterConnectionPool` which changes behavior of `max_connections` so that it applies per-node rather than across the whole cluster. The new feature is opt-in, and the existing default behavior is unchanged. Users are recommended to opt-in as the feature fixes two important problems. First is that some nodes could be starved for connections after max_connections is used up by connecting to other nodes. Second is that the asymmetric number of connections across nodes makes it challenging to configure file descriptor and redis max client settings.

Reinitialize on `MOVED` errors will not run on every error but instead on every
25 error to avoid excessive cluster reinitialize when used in multiple threads and resharding at the same time. If you want to go back to the old behaviour with reinitialize on every error you should pass in `reinitialize_steps=1` to the client constructor. If you want to increase or decrease the intervall of this new behaviour you should set `reinitialize_steps` in the client constructor to a value that you want.

Pipelines in general have recieved alot of attention so if you are using pipelines in your code, ensure that you test the new code out alot before using it to make sure it still works as you expect.

The entire client code should now be safer to use in a threaded environment. Some race conditions was found and have now been fixed and it should prevent the code from behaving wierd during reshard operations.



## 0.2.0 --> 0.3.0

In `0.3.0` release the name of the client class was changed from `RedisCluster` to `StrictRedisCluster` and a new implementation of `RedisCluster` was added that is based on `redis.Redis` class. This was done to enable implementation a cluster enabled version of `redis.Redis` class.

Because of this all imports and usage of `RedisCluster` must be changed to `StrictRedisCluster` so that existing code will remain working. If this is not done some issues could arise in existing code.



## 0.1.0 --> 0.2.0

No major changes was done.

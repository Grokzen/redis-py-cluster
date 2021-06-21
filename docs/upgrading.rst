Upgrading redis-py-cluster
==========================

This document describes what must be done when upgrading between different versions to ensure that code still works.

2.0.0 --> 2.1.0
---------------

Python3 version must now be one of 3.5, 3.6, 3.7, 3.8

The following exception example has now a new more specific exception class that will be attempted to be caught and the client to resolve the cluster layout. If enough attempts has been made then SlotNotCoveredError will be raised with the same message as before. If you have catch for RedisClusterException you either remove it and let the client try to resolve the cluster layout itself, or start to catch SlotNotCoveredError. This error usually happens during failover if you run skip_full_coverage_check=True when running on AWS ElasticCache for example.

	## Example exception
	rediscluster.exceptions.RedisClusterException: Slot "6986" not covered by the cluster. "skip_full_coverage_check=True"


1.3.x --> 2.0.0
---------------

Redis-py upstream package dependency has now been updated to be any of the releases in the major version line 3.0.x. This means that you must upgrade your dependency from 2.10.6 to the latest version. Several internal components have been updated to reflect the code from 3.0.x.

Class StrictRedisCluster was renamed to RedisCluster. All usages of this class must be updated.

Class StrictRedis has been removed to mirror upstream class structure.

Class StrictClusterPipeline was renamed to ClusterPipeline.

Method SORT has been changed back to only allow execution if keys are in the same slot. No more client side parsing and handling of the keys and values.


1.3.2 --> Next Release
----------------------

If you created the `StrictRedisCluster` (or `RedisCluster`) instance via the `from_url` method and were passing `readonly_mode` to it, the connection pool created will now properly allow selecting read-only slaves from the pool. Previously it always used master nodes only, even in the case of `readonly_mode=True`. Make sure your code don't attempt any write commands over connections with `readonly_mode=True`.


1.3.1 --> 1.3.2
---------------

If your redis instance is configured to not have the `CONFIG ...` commands enabled due to security reasons you need to pass this into the client object `skip_full_coverage_check=True`. Benefits are that the client class no longer requires the `CONFIG ...` commands to be enabled on the server. A downside is that you can't use the option in your redis server and still use the same feature in this client.



1.3.0 --> 1.3.1
---------------

Method `scan_iter` was rebuilt because it was broken and did not perform as expected. If you are using this method you should be careful with this new implementation and test it through before using it. The expanded testing for that method indicates it should work without problems. If you find any issues with the new method please open a issue on github.

A major refactoring was performed in the pipeline system that improved error handling and reliability of execution. It also simplified the code, making it easier to understand and to continue development in the future. Because of this major refactoring you should thoroughly test your pipeline code to ensure that none of your code is broken.



1.2.0 --> Next release
----------------------

Class RedisClusterMgt has been removed. You should use the `CLUSTER ...` methods that exist in the `StrictRedisCluster` client class.

Method `cluster_delslots` changed argument specification from `self, node_id, *slots` to `self, *slots` and changed the behaviour of the method to now automatically determine the slot_id based on the current cluster structure and where each slot that you want to delete is loaded.

Method pfcount no longer has custom logic and exceptions to prevent CROSSSLOT errors. If method is used with different slots then a regular CROSSSLOT error (rediscluster.exceptions.ClusterCrossSlotError) will be returned.



1.1.0 --> 1.2.0
--------------

Discontinue passing `pipeline_use_threads` flag to `rediscluster.StrictRedisCluster` or `rediscluster.RedisCluster`.

Also discontinue passing `use_threads` flag to the pipeline() method.

In 1.1.0 and prior, you could use `pipeline_use_threads` flag to tell the client to perform queries to the different nodes in parallel via threads. We exposed this as a flag because using threads might have been risky and we wanted people to be able to disable it if needed.

With this release we figured out how parallelize commands without the need for threads. We write to all the nodes before reading from them, essentially multiplexing the connections (but without the need for complicated socket multiplexing). We found this approach to be faster and more scalable as more nodes are added to the cluster.

That means we don't need the `pipeline_use_threads` flag anymore, or the `use_threads` flag that could be passed into the instantiation of the pipeline object itself.

The logic is greatly simplified and the default behavior will now come with a performance boost and no need to use threads.

Publish and subscribe no longer connects to a single instance. It now hashes the channel name and uses that to determine what node to connect to. More work will be done in the future when `redis-server` improves the pubsub implementation. Please read up on the documentation about pubsub in the `docs/pubsub.md` file about the problems and limitations on using a pubsub in a cluster.

Commands Publish and Subscribe now uses the same connections as any other commands. If you are using any pubsub commands you need to test it through thoroughly to ensure that your implementation still works.

To use less strict cluster slots discovery you can add the following config to your redis-server config file "cluster-require-full-coverage=no" and this client will honour that setting and not fail if not all slots is covered.

A bug was fixed in 'sdiffstore', if you are using this, verify that your code still works as expected.

Class RedisClusterMgt is now deprecated and will be removed in next release in favor of all cluster commands implemented in the client in this release.



1.0.0 --> 1.1.0
---------------

The following exceptions have been changed/added and code that use this client might have to be updated to handle the new classes.

`raise RedisClusterException("Too many Cluster redirections")` have been changed to `raise ClusterError('TTL exhausted.')`

`ClusterDownException` have been replaced with `ClusterDownError`

Added new `AskError` exception class.

Added new `TryAgainError` exception class.

Added new `MovedError` exception class.

Added new `ClusterCrossSlotError` exception class.

Added optional `max_connections_per_node` parameter to `ClusterConnectionPool` which changes behavior of `max_connections` so that it applies per-node rather than across the whole cluster. The new feature is opt-in, and the existing default behavior is unchanged. Users are recommended to opt-in as the feature fixes two important problems. First is that some nodes could be starved for connections after max_connections is used up by connecting to other nodes. Second is that the asymmetric number of connections across nodes makes it challenging to configure file descriptor and redis max client settings.

Reinitialize on `MOVED` errors will not run on every error but instead on every
25 error to avoid excessive cluster reinitialize when used in multiple threads and resharding at the same time. If you want to go back to the old behaviour with reinitialize on every error you should pass in `reinitialize_steps=1` to the client constructor. If you want to increase or decrease the interval of this new behaviour you should set `reinitialize_steps` in the client constructor to a value that you want.

Pipelines in general have received a lot of attention so if you are using pipelines in your code, ensure that you test the new code out a lot before using it to make sure it still works as you expect.

The entire client code should now be safer to use in a threaded environment. Some race conditions was found and have now been fixed and it should prevent the code from behaving weird during reshard operations.



0.2.0 --> 0.3.0
---------------

In `0.3.0` release the name of the client class was changed from `RedisCluster` to `StrictRedisCluster` and a new implementation of `RedisCluster` was added that is based on `redis.Redis` class. This was done to enable implementation a cluster enabled version of `redis.Redis` class.

Because of this all imports and usage of `RedisCluster` must be changed to `StrictRedisCluster` so that existing code will remain working. If this is not done some issues could arise in existing code.



0.1.0 --> 0.2.0
---------------

No major changes was done.

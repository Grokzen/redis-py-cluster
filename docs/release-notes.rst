Release Notes
=============

Future Release
--------------

    * Add Redis 4 compatability fix to CLUSTER NODES command (See issue #217)
    * Fixed bug with command "CLUSTER GETKEYSINSLOT" that was throwing exceptions
    * Added new methods cluster_get_keys_in_slot() to client
    * Fixed bug with `StrictRedisCluster.from_url` that was ignoring the `readonly_mode` parameter

1.3.4 (Mar 5, 2017)
-------------------

    * Package is now built as a wheel and source package when releases is built.
    * Fixed issues with some key types in `NodeManager.keyslot()`.
    * Add support for `PUBSUB` subcommands `CHANNELS`, `NUMSUB [arg] [args...]` and `NUMPAT`.
    * Add method `set_result_callback(command, callback)` allowing the default reply callbacks to be changed, in the same way `set_response_callback(command, callback)` inherited from Redis-Py does for responses.
    * Node manager now honors defined max_connections variable so connections that is emited from that class uses the same variable.
    * Fixed a bug in cluster detection when running on python 3.x and decode_responses=False was used.
      Data back from redis for cluster structure is now converted no matter what the data you want to set/get later is using.
    * Add SSLClusterConnection for connecting over TLS/SSL to Redis Cluster
    * Add new option to make the nodemanager to follow the cluster when nodes move around by avoiding to query the original list of startup nodes that was provided
      when the client object was first created. This could make the client handle drifting clusters on for example AWS easier but there is a higher risk of the client talking to
      the wrong group of nodes during split-brain event if the cluster is not consistent. This feature is EXPERIMENTAL and use it with care.

1.3.3 (Dec 15, 2016)
--------------------

    * Remove print statement that was faulty commited into release 1.3.2 that case logs to fill up with unwanted data.

1.3.2 (Nov 27, 2016)
--------------------

    * Fix a bug where from_url was not possible to use without passing in additional variables. Now it works as the same method from redis-py.
      Note that the same rules that is currently in place for passing ip addresses/dns names into startup_nodes variable apply the same way through
      the from_url method.
    * Added options to skip full coverage check. This flag is useful when the CONFIG redis command is disabled by the server.
    * Fixed a bug where method *CLUSTER SLOTS* would break in newer redis versions where node id is included in the reponse. Method is not compatible with both old and new redis versions.


1.3.1 (Oct 13, 2016)
--------------------

    * Rebuilt broken method scan_iter. Previous tests was to small to detect the problem but is not corrected to work on a bigger dataset during the test of that method. (korvus81, Grokzen, RedWhiteMiko)
    * Errors in pipeline that should be retried, like connection errors, moved, errors and ask errors now fall back to single operation logic in StrictRedisCluster.execute_command. (72squared).
    * Moved reinitialize_steps and counter into nodemanager so it can be correctly counted across pipeline operations (72squared).


1.3.0 (Sep 11, 2016)
--------------------

    * Removed RedisClusterMgt class and file
    * Fixed a bug when using pipelines with RedisCluster class (Ozahata)
    * Bump redis-server during travis tests to 3.0.7
    * Added docs about same module name in another python redis cluster project.
    * Fix a bug when a connection was to be tracked for a node but the node either do not yet exists or
      was removed because of resharding was done in another thread. (ashishbaghudana)
    * Fixed a bug with "CLUSTER ..." commands when a node_id argument was needed and the return type
      was supposed to be converted to bool with bool_ok in redis._compat.
    * Add back gitter chat room link
    * Add new client commands
      - cluster_reset_all_nodes
    * Command cluster_delslots now determines what cluster shard each slot is on and sends each slot deletion
      command to the correct node. Command have changed argument spec (Read Upgrading.rst for details)
    * Fixed a bug when hashing the key it if was a python 3 byte string and it would cause it to route to wrong slot in the cluster (fossilet, Grokzen)
    * Fixed a bug when reinitialize the nodemanager it would use the old nodes_cache instead of the new one that was just parsed (monklof)


1.2.0 (Apr 09, 2016)
--------------------

    * Drop maintained support for python 3.2.
    * Remove Vagrant file in favor for repo maintained by 72squared
    * Add Support for password protected cluster (etng)
    * Removed assertion from code (gmolight)
    * Fixed a bug where a regular connection pool was allocated with each StrictRedisCluster instance.
    * Rework pfcount to now work as expected when all arguments points to same hashslot
    * New code and important changes from redis-py 2.10.5 have been added to the codebase.
    * Removed the need for threads inside of pipeline. We write the packed commands all nodes before reading the responses which gives us even better performance than threads, especially as we add more nodes to the cluster.
    * Allow passing in a custom connection pool
    * Provide default max_connections value for ClusterConnectionPool *(2**31)*
    * Travis now tests both redis 3.0.x and 3.2.x
    * Add simple ptpdb debug script to make it easier to test the client
    * Fix a bug in sdiffstore (mt3925)
    * Fix a bug with scan_iter where duplicate keys would be returned during itteration
    * Implement all "CLUSTER ..." commands as methods in the client class
    * Client now follows the service side setting 'cluster-require-full-coverage=yes/no' (baranbartu)
    * Change the pubsub implementation (PUBLISH/SUBSCRIBE commands) from using one single node to now determine the hashslot for the channel name and use that to connect to
      a node in the cluster. Other clients that do not use this pattern will not be fully compatible with this client. Known limitations is pattern
      subscription that do not work properly because a pattern can't know all the possible channel names in advance.
    * Convert all docs to ReadTheDocs
    * Rework connection pool logic to be more similar to redis-py. This also fixes an issue with pubsub and that connections
      was never release back to the pool of available connections.

1.1.0 (Oct 27, 2015)
-------------------

    * Refactored exception handling and exception classes.
    * Added READONLY mode support, scales reads using slave nodes.
    * Fix __repr__ for ClusterConnectionPool and ClusterReadOnlyConnectionPool
    * Add max_connections_per_node parameter to ClusterConnectionPool so that max_connections parameter is calculated per-node rather than across the whole cluster.
    * Improve thread safty of get_connection_by_slot and get_connection_by_node methods (iandyh)
    * Improved error handling when sending commands to all nodes, e.g. info. Now the connection takes retry_on_timeout as an option and retry once when there is a timeout. (iandyh)
    * Added support for SCRIPT LOAD, SCRIPT FLUSH, SCRIPT EXISTS and EVALSHA commands. (alisaifee)
    * Improve thread safety to avoid exceptions when running one client object inside multiple threads and doing resharding of the
      cluster at the same time.
    * Fix ASKING error handling so now it really sends ASKING to next node during a reshard operation. This improvement was also made to pipelined commands.
    * Improved thread safety in pipelined commands, along better explanation of the logic inside pipelining with code comments.

1.0.0 (Jun 10, 2015)
-------------------

    * No change to anything just a bump to 1.0.0 because the lib is now considered stable/production ready.

0.3.0 (Jun 9, 2015)
-------------------

    * simple benchmark now uses docopt for cli parsing
    * New make target to run some benchmarks 'make benchmark'
    * simple benchmark now support pipelines tests
    * Renamed RedisCluster --> StrictRedisCluster
    * Implement backwards compatible redis.Redis class in cluster mode. It was named RedisCluster and everyone updating from 0.2.0 to 0.3.0 should consult docs/Upgrading.md for instructions how to change your code.
    * Added comprehensive documentation regarding pipelines
    * Meta retrieval commands(slots, nodes, info) for Redis Cluster. (iandyh)

0.2.0 (Dec 26, 2014)
-------------------

    * Moved pipeline code into new file.
    * Code now uses a proper cluster connection pool class that handles
      all nodes and connections similar to how redis-py do.
    * Better support for pubsub. All clients will now talk to the same server because
      pubsub commands do not work reliably if it talks to a random server in the cluster.
    * Better result callbacks and node routing support. No more ugly decorators.
    * Fix keyslot command when using non ascii characters.
    * Add bitpos support, redis-py 2.10.2 or higher required.
    * Fixed a bug where vagrant users could not build the package via shared folder.
    * Better support for CLUSTERDOWN error. (Neuront)
    * Parallel pipeline execution using threads. (72squared)
    * Added vagrant support for testing and development. (72squared)
    * Improve stability of client during resharding operations (72squared)

0.1.0 (Sep 29, 2014)
-------------------

    * Initial release
    * First release uploaded to pypi

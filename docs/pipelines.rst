Pipelines
=========


How pipelining works
--------------------

In redis-py-cluster, pipelining is all about trying to achieve greater network efficiency. Transaction support is disabled in redis-py-cluster. Use pipelines to avoid extra network round-trips, not to ensure atomicity.

Just like in `redis-py`, `redis-py-cluster` queues up all the commands inside the client until execute is called. But, once execute is called, `redis-py-cluster` internals work slightly differently. It still packs the commands to efficiently transmit multiple commands across the network. But since different keys may be mapped to different nodes, redis-py-cluster must first map each key to the expected node. It then packs all the commands destined for each node in the cluster into its own packed sequence of commands. It uses the redis-py library to communicate with each node in the cluster.

Ideally all the commands should be sent to each node in the cluster in parallel so that all the commands can be processed as fast as possible. We do this by first writing all of the commands to the sockets sequentially before reading any of the responses. This allows us to parallelize the network i/o without the overhead of managing python threads.

In previous versions of the library there were some bugs associated with pipelining operations. In an effort to simplify the logic and lessen the likelihood of bugs, if we get back connection errors, MOVED errors, ASK errors or any other error that can safely be retried, we fall back to sending these remaining commands sequentially to each individual node just as we would in a normal redis call. We still buffer the results inside the pipeline response so there will be no change in client behavior. During normal cluster operations, pipelined commands should work nearly efficiently as pipelined commands to a single instance redis. When there is a disruption to the cluster topography, like when keys are being resharded, or when a slave takes over for a master, there will be a slight loss of network efficiency. Commands that are rejected by the server are tried one at a time as we rebuild the slot mappings. Once the slots table is rebuilt correctly (usually in a second or so), the client resumes efficient networking behavior. We felt it was more important to prioritize correctness of behavior and reliable error handling over networking efficiency for the rare cases where the cluster topography is in flux.



Connection Error handling
-------------------------

The other way pipelines differ in `redis-py-cluster` from `redis-py` is in error handling and retries. With the normal `redis-py` client, if you hit a connection error during a pipeline command it raises the error right there. But we expect redis-cluster to be more resilient to failures.

If you hit a connection problem with one of the nodes in the cluster, most likely a stand-by slave will take over for the down master pretty quickly. In this case, we try the commands bound for that particular node to another random node. The other random node will not just blindly accept these commands. It only accepts them if the keys referenced in those commands actually map to that node in the cluster configuration.

Most likely it will respond with a `MOVED` error telling the client the new master for those commands. Our code handles these `MOVED` commands according to the redis cluster specification and re-issues the commands to the correct server transparently inside of `pipeline.execute()` method. You can disable this behavior if you'd like as well.


# ASKED and MOVED errors

The other tricky part of the redis-cluster specification is that if any command response comes back with an `ASK` or `MOVED` error, the command is to be retried against the specified node.

In previous versions of `redis-py-cluster` treated `ASKED` and `MOVED` errors the same, but they really need to be handled differently. `MOVED` error means that the client can safely update its own representation of the slots table to point to a new node for all future commands bound for that slot.

An `ASK` error means the slot is only partially migrated and that the client can only successfully issue that command to the new server if it prefixes the request with an `ASKING¨ ` command first. This lets the new node taking over that slot know that the original server said it was okay to run that command for the given key against the new node even though the slot is not yet completely migrated. Our current implementation now handles this case correctly.



The philosophy on pipelines
---------------------------

After playing around with pipelines and thinking about possible solutions that could be used in a cluster setting this document will describe how pipelines work, strengths and weaknesses of the implementation that was chosen.

Why can't we reuse the pipeline code in `redis-py`? In short it is almost the same reason why code from the normal redis client can't be reused in a cluster environment and that is because of the slots system. Redis cluster consist of a number of slots that is distributed across a number of servers and each key belongs in one of these slots.

In the normal pipeline implementation in `redis-py` we can batch send all the commands and send them to the server at once, thus speeding up the code by not issuing many requests one after another. We can say that we have defined and guaranteed execution order because of this.

One problem that appears when you want to do pipelines in a cluster environment is that you can't have guaranteed execution order in the same way as a single server pipeline. The problem is that because you can queue a command to any key, we will end up in most of the cases having to talk to 2 or more nodes in the cluster to execute the pipeline. The problem with that is that there is no single place/node/way to send the pipeline and redis will sort everything out by itself via some internal mechanisms. Because of that when we build a pipeline for a cluster we have to build several smaller pipelines that we each send to the designated node in the cluster.

When the pipeline is executed in the client each key is checked to what slot it should be sent to and the pipeline is built up based on that information. One thing to note here is that there will be partial correct execution order if you look over the entire cluster because for each pipeline the ordering will be correct. It can also be argued that the correct execution order is applied/valid for each slot in the cluster.

The next thing to take into consideration is what commands should be available and which should be blocked/locked.

In most cases and in almost all solutions multi key commands have to be blocked hard from being executed inside a pipeline. This would only be possible in the case you have a pipeline implementation that always executes immediately each command is queued up. That solution would only give the interface of working like a pipeline to ensure old code will still work, but it would not give any benefits or advantages other than all commands would work and old code would work.

In the solution for this lib multikey commands are blocked hard and will probably not be enabled in pipelines. If you really need to use them you need to execute them through the normal cluster client if they are implemented and work in there. Why can't multi key commands work? In short again it is because the keys can live in different slots on different nodes in the cluster. It is possible in theory to have any command work in a cluster, but only if the keys operated on belong to the same cluster slot. This lib have decided that currently no serious support for that will be attempted.

Examples on commands that do not work is `MGET`, `MSET`, `MOVE`.

One good thing that comes out of blocking multi key commands is that correct execution order is less of a problem and as long as it applies to each slot in the cluster we should be fine.

Consider the following example. Create a pipeline and issue 6 commands `A`, `B`, `C`, `D`, `E`, `F` and then execute it. The pipeline is calculated and 2 sub pipelines is created with `A`, `C`, `D`, `F` in the first and `B`, `E` in the second. Both pipelines are then sent to each node in the cluster and a response is sent back. For the first node `[True, MovedException(12345), MovedException(12345), True]` and from the second node [`True`, `True`]. After this response is parsed we see that 2 commands in the first pipeline did not work and must be sent to another node. This case happens if the client slots cache is wrong because a slot was migrated to another node in the cluster. After parsing the response we then build a third pipeline object with commands [`C`, `D`] to the second node. The third object is executed and passes and from the client perspective the entire pipeline was executed.

If we look back at the order we executed the commands we get `[A, F]` for the first node and `[B, E, C, D]` for the second node. At first glance this looks like it is out of order because command `E` is executed before `C` & `D`. Why is this not matter? Because no multi key operations can be done in a pipeline, we only have to care the execution order is correct for each slot and in this case it was because `B` & `E` belongs to the same slot and `C` & `D` belongs to the same slot. There should be no possible way to corrupt any data between slots if multi key commands are blocked by the code.

What is good with this pipeline solution? First we can actually have a pipeline solution that will work in most cases with few commands blocked (only multi key commands). Secondly we can run it in parallel to increase the performance of the pipeline even further, making the benefits even greater.


Packing Commands
----------------

When issuing only a single command, there is only one network round trip to be made. But what if you issue 100 pipelined commands? In a single-instance redis configuration, you still only need to make one network hop. The commands are packed into a single request and the server responds with all the data for those requests in a single response. But with redis cluster, those keys could be spread out over many different nodes. 

The client is responsible for figuring out which commands map to which nodes. Let's say for example that your 100 pipelined commands need to route to 3 different nodes? The first thing the client does is break out the commands that go to each node, so it only has 3 network requests to make instead of 100.


Parallel execution of pipeline
------------------------------

In older version of `redis-py-cluster`, there was a thread implementation that helped to increase the performance of running pipelines by running the connections and execution of all commands to all nodes in the pipeline in parallel. This implementation was later removed in favor of a much simpler and faster implementation.

In this new implementation we execute everything in the same thread, but we do all the writing to all sockets in order to each different server and then start to wait for them in sequence until all of them is complete. There is no real need to run them in parallel since we still have to wait for a thread join of all parallel executions before the code can continue, so we can wait in sequence for all of them to complete. This is not the absolute fastest implementation, but it much simpler to implement and maintain and cause less issues because there is no threads or other parallel implementation that will use some overhead and add complexity to the method.

This feature is implemented by default and will be used in all pipeline requests.



Transactions and WATCH
----------------------

Support for transactions and WATCH:es in pipelines. If we look on the entire pipeline across all nodes in the cluster there is no possible way to have a complete transaction across all nodes because if we need to issue commands to 3 servers, each server is handled by its own and there is no way to tell other nodes to abort a transaction if only one of the nodes fail but not the others. A possible solution for that could be to implement a 2 step commit process. The 2 steps would consist of building 2 batches of commands for each node where the first batch would consist of validating the state of each slot that the pipeline wants to operate on. If any of the slots is migrating or moved then the client can correct its slots cache and issue a more correct pipeline batch. The second step would be to issue the actual commands and the data would be committed to redis. The big problem with this is that 99% of the time this would work really well if you have a very stable cluster with no migrations/resharding/servers down. But there can be times where a slot has begun migration in between the 2 steps of the pipeline and that would cause a race condition where the client thinks it has corrected the pipeline and wants to commit the data but when it does it will still fail.

Why `MULTI/EXEC` support won't work in a cluster environment. There is some test code in the second `MULTI/EXEC cluster test code` of this document that tests if `MULTI/EXEC` is possible to use in a cluster pipeline. The test shows a huge problem when errors occur. If we wrap `MULTI/EXEC` in a packed set of commands then if a slot is migrating we will not get a good error we can parse and use. Currently it will only report `True` or `False` so we can narrow down what command failed but not why it failed. This might work really well if used on a non clustered node because it does not have to take care of `ASK` or `MOVED` errors. But for a cluster we need to know what cluster error occurred so the correct action to fix the problem can be taken. Since there is more then 1 error to take care of it is not possible to take action based on just `True` or `False`.

Because of this problem with error handling `MULTI/EXEC` is blocked hard in the code from being used in a pipeline because the current implementation can't handle the errors.

In theory it could be possible to design a pipeline implementation that can handle this case by trying to determine by itself what it should do with the error by either asking the cluster after a `False` value was found in the response about the current state of the slot or just default to `MOVED` error handling and hope for the best. The problem is that this is not 100% guaranteed to work and can easily cause problems when wrong action was taken on the response.

Currently `WATCH` requires more studying is it possible to use or not, but since it is tied into `MULTI/EXEC` pattern it probably will not be supported for now.



MULTI/EXEC cluster test code
----------------------------

This code does NOT wrap `MULTI/EXEC` around the commands when packed

.. code-block:: python

    >>> from rediscluster import RedisCluster as s
    >>> r = s(startup_nodes=[{"host": "127.0.0.1", "port": "7002"}])
    >>> # Simulate that a slot is migrating to another node
    >>> r.connection_pool.nodes.slots[14226] = {'host': '127.0.0.1', 'server_type': 'master', 'port': 7001, 'name': '127.0.0.1:7001'}
    >>> p = r.pipeline()
    >>> p.command_stack = []
    >>> p.command_stack.append((["SET", "ert", "tre"], {}))
    >>> p.command_stack.append((["SET", "wer", "rew"], {}))
    >>> p.execute()

    ClusterConnection<host=127.0.0.1,port=7001>
    [True, ResponseError('MOVED 14226 127.0.0.1:7002',)]
    ClusterConnection<host=127.0.0.1,port=7002>
    [True]

This code DO wrap MULTI/EXEC around the commands when packed

.. code-block:: python

    >>> from rediscluster import RedisCluster as s
    >>> r = s(startup_nodes=[{"host": "127.0.0.1", "port": "7002"}])
    >>> # Simulate that a slot is migrating to another node
    >>> r.connection_pool.nodes.slots[14226] = {'host': '127.0.0.1', 'server_type': 'master', 'port': 7001, 'name': '127.0.0.1:7001'}
    >>> p = r.pipeline()
    >>> p.command_stack = []
    >>> p.command_stack.append((["SET", "ert", "tre"], {}))
    >>> p.command_stack.append((["SET", "wer", "rew"], {}))
    >>> p.execute()
    ClusterConnection<host=127.0.0.1,port=7001>
    [True, False]



Different pipeline solutions
----------------------------

This section will describe different types of pipeline solutions. It will list their main benefits and weaknesses.

.. note:: 

    This section is mostly random notes and thoughts and not that well written and cleaned up right now. It will be done at some point in the future.



Suggestion one
**************

Simple but yet sequential pipeline. This solution acts more like an interface for the already existing pipeline implementation and only provides a simple backwards compatible interface to ensure that code that exists still will work without any major modifications. This is good because, with this implementation, all commands are run in sequence and it will handle `MOVED` or `ASK` redirections very well and without any problems. The major downside to this solution is that no command is ever batched and run in parallel and thus you do not get any major performance boost from this approach. Another plus is that execution order is preserved across the entire cluster but a major downside is that the commands are no longer atomic on the cluster scale because they are sent in multiple commands to different nodes.

**Good**

 - Sequential execution of the entire pipeline
 - Easy `ASK` or `MOVED` handling

**Bad**

 - No batching of commands aka. no execution speedup



Suggestion two
**************

Current pipeline implementation. This implementation is rather good and works well because it combines the existing pipeline interface and functionality and it also provides a basic handling of `ASK` or `MOVED` errors inside the client. One major downside to this is that execution order is not preserved across the cluster. Although the execution order is somewhat broken if you look at the entire cluster level because commands can be split so that cmd1, cmd3, cmd5 get sent to one server and cmd2, cmd4 gets sent to another server. The order is then broken globally but locally for each server it is preserved and maintained correctly. On the other hand I guess that there can't be any commands that can affect different hashslots within the same command so maybe it really doesn't matter if the execution order is not correct because for each slot/key the order is valid.
There might be some issues with rebuilding the correct response ordering from the scattered data because each command might be in different sub pipelines. But I think that our current code still handles this correctly. I think I have to figure out some weird case where the execution order actually matters. There might be some issues with the nonsupported mget/mset commands that actually performs different sub commands then it currently supports.

**Good**

 - Sequential execution per node

**Bad**

 - Non sequential execution on the entire pipeline
 - Medium difficult `ASK` or `MOVED` handling



Suggestion three
****************

There is a even simpler form of pipelines that can be made where all commands is supported as long as they conform to the same hashslot because REDIS supports that mode of operation. The good thing with this is that since all keys must belong to the same slot there can't be very few `ASK` or `MOVED` errors that happens and if they happen they will be very easy to handle because the entire pipeline is kinda atomic because you talk to the same server and only 1 server. There can't be any multiple server communication happening.

**Good**

 - Super simple `ASK` or `MOVED` handling
 - Sequential execution per slot and through the entire pipeline

**Bad**

 - Single slot per pipeline



Suggestion four
**************

One other solution is the 2 step commit solution where you send for each server 2 batches of commands. The first command should somehow establish that each keyslot is in the correct state and able to handle the data. After the client have received OK from all nodes that all data slots is good to use then it will actually send the real pipeline with all data and commands. The big problem with this approach is that there is a gap between the checking of the slots and the actual sending of the data where things can happen to the already established slots setup. But at the same time there is no possibility of merging these 2 steps because if step 2 is automatically run if step 1 is Ok then the pipeline for the first node that will fail will fail but for the other nodes it will succeed but when it should not because if one command gets `ASK` or `MOVED` redirection then all pipeline objects must be rebuilt to match the new specs/setup and then reissued by the client. The major advantage of this solution is that if you have total control of the redis server and do controlled upgrades when no clients is talking to the server then it can actually work really well because there is no possibility that `ASK` or `MOVED` will triggered by migrations in between the 2 batches.

**Good**

 - Still rather safe because of the 2 step commit solution
 - Handles `ASK` or `MOVED` before committing the data

**Bad**

 - Big possibility of race conditions that can cause problems

# The philosophy on pipelines

After playing around with pipelines and thinking about possible solutions that could be used in a cluster setting this document will describe how pipelines work, strengths and weaknesses with the implementation that was chosen.

Why can't we reuse the pipeline code in `redis-py`? In short it is almost the same reason why code from the normal redis client can't be reused in a cluster environment and that is because of the slots system. Redis cluster consist of a number of slots that is distributed across a number of servers and each key belongs in one of these slots.

In the normal pipeline implementation in `redis-py` we can batch send all the commands and send them to the server at once, thus speeding up the code by not issuing many requests one after another. We can say that we have defined and guaranteed execution order becuase of this.

One problem that appears when you want to do pipelines in a cluster environment is that you can't have guaranteed execution order in the same way as a single server pipeline. The problem is that because you can queue an command to any key, we will end up in most of the cases having to talk to 2 or more nodes in the cluster to execute the pipeline. The problem with that is that there is no single place/node/way to send the pipeline and redis will sort everything out by itself via some internal mechanisms. Because of that when we build a pipeline for a cluster we have to build several smaller pipelines that we each send to the desegnated node in the cluster.

When the pipeline is executed in the client each key is checked to what slot it shold be sent to and the pipelines is built up based on that information. One thing to note here is that there will be partial correct execution order if you look over the entire cluster because for each pipeline the ordering will be correct. It can also be argued that the correct execution order is applied/valid for each slot in the cluster.

The next thing to take into consideration is what commands should be available and which should be blocked/locked.

In most cases and in almost all solutions multi key commands have to be blocked hard from beeing execute inside a pipeline. This would only be possible in the case you have a pipeline implementation that allways executes immeditally each command is queued up. That solution would only give the interface of working like a pipeline to ensure old code will still work, but it would not give any benefits or advantages other than all commands would work and old code would work.

In the solution for this lib multikey commands is blocked hard and will probably not be enabled in pipelines. If you really need to use them you need to execute them through the normal cluster client if they are implemented and works in there. Why can't multi key commands work? In short again it is because they keys can live in different slots on different nodes in the cluster. It is possible in theory to have any command work in a cluster, but only if the keys operated on belongs to the same cluster slot. This lib have decided that currently no serious support for that will be attempted. 

Examples on commands that do not work is MGET, MSET, MOVE.

One good thing that comes out of blocking multi key commands is that correct execution order is less of a problem and as long as it applies to each slot in the cluster we shold be fine.

Consider the following example. Create a pipeline and issue 6 commands A, B, C, D, E, F and then execute it. The pipeline is calculated and 2 sub pipelines is created with A, C, D, F in the first and B, E in the second. Both pipelines is then sent to each node in the cluster and a response is sent back. For the first node [True, MovedException(12345), MovedException(12345), True] and from the second node [True, True]. After this response is parsed we see that 2 commands in the first pipeline did not work and must be sent to another node. This case happens if the client slots cache is wrong because a slot was migrated to another node in the cluster. After parsing the response we then build a third pipeline object with commands [C, D] to the second node. The third object is executed and passes and from the client perspective the entire pipeline was executed.

If we look back at the order we executed the commands we get [A, F] for the first node and [B, E, C, D] for the second node. At first glance this looks like it is out of order because command E is executed before C & D. Why do this not matter? Because no multi key operations can be done in a pipeline we only have to care the execution order is correct for each slot and in this case it was because B & E belongs to the same slot and C & D belongs to the same slot. There should be no possible way to corrupt any data between slots if multi key commands is blocked by the code.

What is good with this pipeline solution? First we can acctually have a pipeline solution that will work in most cases with few commands blocked (only multi key commands). Secondly we can run it in parralell with threads or gevent to increase the performance of the pipeline even further, making the benefits even greater. 



## Transactions and WATCH

Support for transactions and WATCH:es in pipelines. If we look on the entire pipeline across all nodes in the cluster there is no possible way to have a complete transaction across all nodes because if we need to issue commands to 3 servers, each server is handled by its own and there is no way to tell other nodes to abort a transaction if only one of the nodes fail but not the others. A possible solution for that could be to implement a 2 step commit process. The 2 steps would consist of building 2 batches of commands for each node where the first batch would consist of validating the state of each slot that the pipeline wants to operate on. If any of the slots is migrating or moved then the client can correct its slots cache and issue a more correct pipeline batch. The second step would be to issue the acctuall commands and the data would be commited to redis. The big problem with this is that 99% of the time this would work really well if you have a very stable cluster with no migrations/resharding/servers down. But there can be times where a slot has begun migration in between the 2 steps of the pipeline and that would cause a race condition where the client thinks it has corrected the pipeline and wants to commit the data but when it does it will still fail.

Why `MULTI/EXEC` support won't work in a cluster environment. There is some test code in the second `MULTI/EXEC cluster test code` of this document that tests is `MULTI/EXEC` is possible to use in a cluster pipeline. The tests shows a huge problem when errors occus. If we wrap `MULTI/EXEC` in a packed set of commands then if a slot is migrating we will not get a good error we can parse and use. Currently it will only report `True` or `False` so we can narrow down what command failed but not why it failed. This might work really well if used on a non clustered node becuase it do not have to take care of ASK/MOVED errors. But for a cluster we need to know what cluster error occured so the correct action to fix the problem can be taken. Sinc there is more then 1 error to take care of it is not possible to take action based on just `True` or `False`.

Because of this problem with error handling `MULTI/EXEC` is blocked hard in the code from beeing used in a pipeline because the current implementation can't handle the errors.

In theory it could be possible to design a pipeline implementation that can handle this case by trying to determined by itself what it should do with the error by either asking the cluster after a `False` value was found in the response about the current state of the slot or just default to `MOVED` error handling and hope for the best. The problem is that this is not 100% guaranteed to work and can easily cause problems when wrong action was taken on the response.

Currently `WATCH` requires more studying if it possible to use or not, but sinc it is tied into `MULTI/EXEC` pattern it probably will not be supported for now.



## MULTI/EXEC cluster test code

This code do NOT wrap MULTI/EXEC around the commands when packed

>>> from rediscluster import StrictRedisCluster as s
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
>>> 



This code DO wrap MULTI/EXEC around the commands when packed

>>> from rediscluster import StrictRedisCluster as s
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
>>> 



## Different pipeline solutions

This section will describe different types of pipeline solutions. It will list their main benefits and weaknesses. 

Note: This section is mostly random notes and thoughts and not that well written and cleaned up right now. It will be done at some point in the future.


Simple but yet sequential pipeline. This solution acts more like an interface for the already existing pipeline implementation and only provides a simple backwards compatible interface to ensure that code that sexists still will work withouth any major modifications. The good this with this implementation is that because all commands is runned in sequence it will handle MOVED/ASK redirections very good and withouth any problems. The major downside to this solution is that no commands is ever batched and runned in parralell and thus you do not get any major performance boost from this approach. Other plus is that execution order is preserved across the entire cluster but a major downside is that thte commands is no longer atomic on the cluster scale because they are sent in multiple commands to different nodes.

+ Sequential execution of the entire pipeline
- No batching of commands aka. no execution speedup
+ Easy ASK/MOVED handling




Current pipeline implementation. This implementation is rather good and works well because it combines the existing pipeline interface and functionality and it also provides a basic handling of ASK/MOVED errors inside the client. One major downside to this is that execution order is not preserved across the cluster. Altho the execution order is somewhat broken if you look at the entire cluster level becuase commands can be splitted so that cmd1, cmd3, cmd5 get sent to one server and cmd2, cmd4 gets sent to another server. The order is then broken globally but locally for each server it is preserved and maintained correctly. On the other hand i guess that there can't be any commands that can affect different hashslots within the same command so it maybe do not really matter if the execution order is not correct because for each slot/key the order is valid.
There might be some issues with rebuilding the correct response ordering from the scattered data because each command might be in different sub pipelines. But i think that our current code still handles this correctly. I think i have to figure out some wierd case where the execution order acctually matters. There might be some issues with the nonsupported mget/mset commands that acctually performs different sub commands then it currently supports.

+ Sequential execution per node
- Not sequential execution on the entire pipeline
- Medium difficult ASK/MOVED handling




There is a even simpler form of pipelines that can be made where all commands is supported as long as they conform to the same hashslot because redis supports that mode of operation. The good thing with this is that sinc all keys must belong to the same slot there can't be very few ASK/MOVED errors that happens and if they happen they will be very easy to handle because the entire pipeline is kinda atomic because you talk to the same server and only 1 server. There can't be any multiple server communication happening.

+ Super simple ASK/MOVED handling
+ Sequential execution per slot and through the entire pipeline
- Single slot per pipeline




One other solution is the 2 step commit solution where you send for each server 2 batches of commands. The first command should somehow establish that each keyslot is in the correct state and able to handle the data. After the client have recieved OK from all nodes that all data slots is good to use then it will acctually send the real pipeline with all data and commands. The big problem with this approach is that ther eis a gap between the checking of the slots and the acctual sending of the data where things can happen to the already established slots setup. But at the same time there is no possibility of merging these 2 steps because if step 2 is automatically runned if step 1 is Ok then the pipeline for the first node that will fail will fail but for the other nodes it will suceed but when it should not because if one command gets ASK/MOVED redirection then all pipeline objects must be rebuilt to match the new specs/setup and then reissued by the client. The major advantage of this solution is that if you have total controll of the redis server and do controlled upgrades when no clients is talking to the server then it can acctually work really well because there is no possibility that ASK/MOVED will triggered by migrations in between the 2 batches.

- Big possibility of race conditions that can cause problems
+ Still rather safe because of the 2 step commit solution
+ Handles ASK/MOVED before commiting the data

Pubsub
======

After testing pubsub in cluster mode one big problem was discovered with the `PUBLISH` command.

According to the current official redis documentation on `PUBLISH`::

    Integer reply: the number of clients that received the message.

It was initially assumed that if we had clients connected to different nodes in the cluster it would still report back the correct number of clients that recieved the message.

However after some testing of this command it was discovered that it would only report the number of clients that have subscribed on the same server the `PUBLISH` command was executed on.

Because of this, if there is some functionality that relies on an exact and correct number of clients that listen/subscribed to a specific channel it will be broken or behave wrong.

Currently the only known workarounds is to:

- Ignore the returned value
- All clients talk to the same server
- Use a non clustered redis server for pubsub operations

Discussion on this topic can be found here: https://groups.google.com/forum/?hl=sv#!topic/redis-db/BlwSOYNBUl8



Scalability issues
------------------

The following part is from this discussion https://groups.google.com/forum/?hl=sv#!topic/redis-db/B0_fvfDWLGM and it describes the scalability issue that pubsub has and the performance that goes with it when used in a cluster environment.

    according to [1] and [2] PubSub works by broadcasting every publish to every other
    Redis Cluster node. This limits the PubSub throughput to the bisection bandwidth
    of the underlying network infrastructure divided by the number of nodes times
    message size. So if a typical message has 1KB, the cluster has 10 nodes and
    bandwidth is 1 GBit/s, throughput is already limited to 12.5K RPS. If we increase
    the message size to 5 KB and the number of nodes to 50, we only get 500 RPS
    much less than a single Redis instance could service (>100K RPS), while putting
    maximum pressure on the network. PubSub thus scales linearly wrt. to the cluster size,
    but in the the negative direction!



How pubsub works in StrictRedisCluster
--------------------------------------

In release `1.2.0` the pubsub was code was reworked to now work like this.

For `PUBLISH` and `SUBSCRIBE` commands:

 - The channel name is hashed and the keyslot is determined.
 - Determine the node that handles the keyslot.
 - Send the command to the node.

The old solution was that all pubsub connections would talk to the same node all the time. This would ensure that the commands would work.

This new solution is probably future safe and it will probably be a similar solution when `redis` fixes the scalability issues.



Known limitations with pubsub
-----------------------------

Pattern subscribe and publish do not work properly because if we hash a pattern like `fo*` we will get a keyslot for that string but there is a endless posiblity of channel names based on that pattern that we can't know in advance. This feature is not limited but the commands is not recommended to use right now.

The implemented solution will only work if other clients use/adopt the same behaviour. If some other client behaves differently, there might be problems with `PUBLISH` and `SUBSCRIBE` commands behaving wrong.



Other solutions
---------------

The simplest solution is to have a seperate non clustered redis instance that you have a regular `StrictRedis` instance that works with your pubsub code. It is not recommended to use pubsub until `redis` fixes the implementation in the server itself.

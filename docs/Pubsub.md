# Pubsub

After testing pubsub in cluster mode one big problem was discovered with the `PUBLISH` command.

According to the current official redis documentation on `PUBLISH` "Integer reply: the number of clients that received the message." it was initially assumed that if we had clients connected to different nodes in the cluster it would still report back the correct number of clients that recieved the message.

However after some testing of this command it was discovered that it would only report the number of clients that have subscribed on the same server the `PUBLISH` command was executed on.

Because of this, if there is some functionality that relies on an exact and correct number of clients that listen/subscribed to a specific channel it will be broken or behave wrong.

Currently the only known workarounds is to:

- Ignore the returned value
- All clients talk to the same server
- Use a non clustered redis server for pubsub operations

Discussion on this topic can be found here: https://groups.google.com/forum/?hl=sv#!topic/redis-db/BlwSOYNBUl8



# Scalability issues

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



# How pubsub works in StrictRedisCluster

In release `1.2.0` the `pubsub` implementation was removed because of the scalability issue that was described above. Until `redis` fixes these issues and implements a solution that will work well in a cluster environment, the code will be added back.



# Known solutions instead of using StrictredisCluster

The simplest solution is to have a seperate non clustered redis instance that you have a regular `StrictRedis` instance that works with your pubsub code.

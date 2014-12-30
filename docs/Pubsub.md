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



# How pubsub works in StrictRedisCluster

In `0.2.0` a first solution to pubsub problem was implemented, but it contains some limitations.

When a new `StrictRedisCluster` instance is created it will now just after all slots is initialized determine what one node will be the pubsub node. Currently it will use the node with the highest port number.

With this solution, pubsub will work in a cluster without any other major workarounds.

All pubsub tests pass with this setup.

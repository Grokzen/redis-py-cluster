# Pubsub

After testing pubsub in cluster mode one big problem was discovered with the `PUBLISH` command.

According to the current official redis documentation on `PUBLISH` "Integer reply: the number of clients that received the message." it was initially assumed that if we had clients connected to different nodes in the cluster it would still report back the correct number of clients that recieved the message. 

However after some testing of this command it was discovered that it would only report the number of clients that have subscribed on the same server the `PUBLISH` command was executed on.

Because of this, if there is some functionality that relies on an exact and correct number of clients that listen/subscribed to a specific channel it will be broken or behave wrong.

Currently the only known workarounds is to:

- Ignore the returned value or t
- All clients talk to the same server in pubsub mode
- Use a non clustered redis server for pubsub operations

Discussion on this topic can be found here: https://groups.google.com/forum/?hl=sv#!topic/redis-db/BlwSOYNBUl8



## How this lib handels this problem

Currently there is no special logic running on pubsub commands.

All tests have been adapted to run on just 1 server to verify that the pubsub functionality still works. In some situations like `PUBLISH` command, tests will be done to verify it works across the cluster but it will ignore returned value because of reasons described in this document.

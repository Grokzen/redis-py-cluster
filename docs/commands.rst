Implemented redis commands in RedisCluster
==========================================

This document will enumerate and describe all implemented redis commands and if there is any cluster specific customization/changes done to the command to make them work for a cluster workload.

If a command is specified here but there is no comments on it, then you can assume it will work and behave the same way as when using it from `redis-py`.

If a new command has been added to redis-server and it is not documented here then please open a issue on github telling that it is missing and needs to be added to this documentation.

.. danger::

    If a command below begins with `[NYV] / Not Yet Verified` it means that the command is documented here but it is not yet verified that it works or is properly implemented or decided what implementation to use in a clustered environment.


Cluster
-------

https://redis.io/commands#cluster

- CLUSTER ADDSLOTS slot [slot ...]

 .. note::
 
     Client has custom implementation where the user has to route the command to the correct node manually.

- **[NYV]** - CLUSTER BUMPEPOCH
- CLUSTER COUNT_FAILURE-REPORTS node-id

 .. note::
 
     Client has custom implementation where the user has to route the command to the correct node manually.

- CLUSTER COUNTKEYSINSLOT slot

 .. note::

    Client will route command to node that owns the slot

- CLUSTER DELSLOTS slot [slot ...]

 .. note::
 
     Client has custom implementation where the user has to route the command to the correct node manually.

- CLUSTER FAILOVER [FORCE|TAKEOVER]

 .. note::
 
     Client has custom implementation where the user has to route the command to the correct node manually.

- **[NYV]** - CLUSTER FLUSHSLOTS
- **[NYV]** - CLUSTER FORGET node-id
- CLUSTER GETKEYSINSLOT slot count

 .. note::

    Client will route command to node that owns the slot

- CLUSTER INFO

 .. note::
 
    Command is sent to all nodes in the cluster.

    Result is merged into a single dict with node as key.

- CLUSTER KEYSLOT key

 .. note::
 
     Client has custom implementation where the user has to route the command to the correct node manually.

- CLUSTER MEET ip port

 .. note::
 
     Client has custom implementation where the user has to route the command to the correct node manually.

- **[NYV]** - CLUSTER MYID
- CLUSTER NODES

 .. note::

    Command will be sent to random node in the cluster as the data should be the same on all nodes in a stable/working cluster

- CLUSTER REPLICATE node-id

 .. note::
 
     Client has custom implementation where the user has to route the command to the correct node manually.

- CLUSTER RESET [HARD|SOFT]

 .. note::
 
     Client has custom implementation where the user has to route the command to the correct node manually.

- CLUSTER SAVECONFIG

 .. note::
 
     Client has custom implementation where the user has to route the command to the correct node manually.

- CLUSTER SET-CONFIG-EPOCH config-epoch

 .. note::
 
     Client has custom implementation where the user has to route the command to the correct node manually.

- CLUSTER SETSLOT slot IMPORTING|MIGRATING|STABLE|NODE [node-id]

 .. note::
 
     Client has custom implementation where the user has to route the command to the correct node manually.

- CLUSTER SLAVES node-id

 .. note::
 
     Client has custom implementation where the user has to route the command to the correct node manually.

- **[NYV]** - CLUSTER REPLICAS node-id
- CLUSTER SLOTS

 .. note::

    Command will be sent to random node in the cluster as the data should be the same on all nodes in a stable/working cluster

- **[NYV]** - READONLY
- **[NYV]** - READWRITE


Connection
----------

https://redis.io/commands#connection

- **[NYV]** - AUTH [username] password
- **[NYV]** - CLIENT CACHING YES|NO
- CLIENT ID

 .. warning::
 
     Command is sent to all nodes in the cluster.
 
     Result from each node will be aggregated into a dict where the key will be the internal node name.

- CLIENT KILL [ip:port] [ID client-id] [TYPE normal|master|slave|pubsub] [USER username] [ADDR ip:port] [SKIPME yes/no]

 .. warning::
 
     Command is sent to all nodes in the cluster.
 
     Result from each node will be aggregated into a dict where the key will be the internal node name.

- CLIENT LIST [TYPE normal|master|replica|pubsub]

 .. warning::
 
     Command is sent to all nodes in the cluster.
 
     Result from each node will be aggregated into a dict where the key will be the internal node name.

- CLIENT GETNAME

 .. warning::
 
     Command is sent to all nodes in the cluster.
 
     Result from each node will be aggregated into a dict where the key will be the internal node name.

- **[NYV]** - CLIENT GETREDIR
- **[NYV]** - CLIENT PAUSE timeout
- **[NYV]** - CLIENT REPLY ON|OFF|SKIP
- **[NYV]** - CLIENT SETNAME connection-name
- **[NYV]** - CLIENT TRACKING ON|OFF [REDIRECT client-id] [PREFIX prefix [PREFIX prefix ...]] [BCAST] [OPTIN] [OPTOUT] [NOLOOP]
- **[NYV]** - CLIENT UNBLOCK client-id [TIMEOUT|ERROR]
- ECHO message

 .. warning::
 
     Command is sent to all nodes in the cluster.
 
     Result from each node will be aggregated into a dict where the key will be the internal node name.

- **[NYV]** - HELLO protover [AUTH username password] [SETNAME clientname]
- PING [message]

 .. warning::
 
     Command is sent to all nodes in the cluster.
 
     Result from each node will be aggregated into a dict where the key will be the internal node name.

- **[NYV]** - QUIT
- **[NYV]** - SELECT index


Geo
---

https://redis.io/commands#geo

- **[NYV]** - GEOADD key longitude latitude member [longitude latitude member ...]
- **[NYV]** - GEOHASH key member [member ...]
- **[NYV]** - GEOPOS key member [member ...]
- **[NYV]** - GEODIST key member1 member2 [m|km|ft|mi]
- **[NYV]** - GEORADIUS key longitude latitude radius m|km|ft|mi [WITHCOORD] [WITHDIST] [WITHHASH] [COUNT count] [ASC|DESC] [STORE key] [STOREDIST key]
- **[NYV]** - GEORADIUSBYMEMBER key member radius m|km|ft|mi [WITHCOORD] [WITHDIST] [WITHHASH] [COUNT count] [ASC|DESC] [STORE key] [STOREDIST key]


Hashes
------

https://redis.io/commands#hash

- HDEL key field [field ...]
- HEXISTS key field
- HGET key field
- HGETALL key
- HINCRBY key field increment
- HINCRBYFLOAT key field increment
- HKEYS key
- HLEN key
- HMGET key field [field ...]
- HMSET key field value [field value ...]
- HSET key field value [field value ...]
- HSETNX key field value
- HSTRLEN key field
- HVALS key
- HSCAN key cursor [MATCH pattern] [COUNT count]

 .. note::

     HSCAN command has currently a buggy client side implementation.

     It is not recommended to use any *SCAN methods.


Hyperloglog
-----------

https://redis.io/commands#hyperloglog

- **[NYV]** - PFADD key element [element ...]
- **[NYV]** - PFCOUNT key [key ...]
- **[NYV]** - PFMERGE destkey sourcekey [sourcekey ...]


Keys/Generic
------------

https://redis.io/commands#generic

- DEL key [key ...]

 .. note::

    Method has a custom client side implementation.

    Command is no longer atomic.

    DEL command is sent for each individual key to redis-server.

- DUMP key
- **[NYV]** - EXISTS key [key ...]
- EXPIRE key seconds
- EXPIREAT key timestamp
- **[NYV]** - KEYS pattern
- **[NYV]** - MIGRATE host port key|"" destination-db timeout [COPY] [REPLACE] [AUTH password] [AUTH2 username password] [KEYS key [key ...]]
- MOVE key db

 .. note::
 
     Concept of databases do not exists in a cluter

- OBJECT subcommand [arguments [arguments ...]]

 .. note::

     Command is blocked from executing in the client.

- PERSIST key
- PEXPIRE key milliseconds
- PEXPIREAT key milliseconds-timestamp
- PTTL key
- RANDOMKEY
- RENAME key newkey

 .. note::

    Method has a custom client side implementation.

    Command is no longer atomic.

    If the slots is the same RENAME will be sent to that shard.
    If the source and destination keys have different slots then a dump (old key/slot) -> restore (new key/slot) -> delete (old key) will be performed.

- RENAMENX key newkey

 .. note::

    Method has a custom client side implementation.

    Command is no longer atomic.

    Method will check if key exists and if it does it uses the custom RENAME implementation mentioned above.

- **[NYV]** - RESTORE key ttl serialized-value [REPLACE] [ABSTTL] [IDLETIME seconds] [FREQ frequency]
- SORT key [BY pattern] [LIMIT offset count] [GET pattern [GET pattern ...]] [ASC|DESC] [ALPHA] [STORE destination]

 .. note::

     SORT command will only work on the most basic sorting of lists.

     Any additional arguments or more complex sorts can't get guaranteed to work if working with cross slots.

     Command works if all used keys is in same slot.

- **[NYV]** - TOUCH key [key ...]
- TTL key
- TYPE key
- **[NYV]** - UNLINK key [key ...]
- **[NYV]** - WAIT numreplicas timeout
- **[NYV]** - SCAN cursor [MATCH pattern] [COUNT count] [TYPE type]

 .. note::

     SCAN command has currently a buggy client side implementation.

     It is not recommended to use any *SCAN methods.


Lists
-----

https://redis.io/commands#list

- **[NYV]** - BLPOP key [key ...] timeout
- **[NYV]** - BRPOP key [key ...] timeout
- **[NYV]** - BRPOPLPUSH source destination timeout
- **[NYV]** - LINDEX key index
- **[NYV]** - LINSERT key BEFORE|AFTER pivot element
- **[NYV]** - LLEN key
- **[NYV]** - LPOP key
- **[NYV]** - LPOS key element [RANK rank] [COUNT num-matches] [MAXLEN len]
- **[NYV]** - LPUSH key element [element ...]
- **[NYV]** - LPUSHX key element [element ...]
- **[NYV]** - LRANGE key start stop
- **[NYV]** - LREM key count element
- **[NYV]** - LSET key index element
- **[NYV]** - LTRIM key start stop
- **[NYV]** - RPOP key
- **[NYV]** - RPOPLPUSH source destination
- **[NYV]** - RPUSH key element [element ...]
- **[NYV]** - RPUSHX key element [element ...]


PubSub
------

https://redis.io/commands#pubsub

 .. warning::
 
     All pubsub commands is possible to execute and be routed to correct node when used.
 
     But in general pubsub solution should NOT be used inside a clustered environment unless you really know what you are doing.
 
     Please read the documentation section about pubsub to get more information about why.

- PSUBSCRIBE pattern [pattern ...]
- PUBSUB subcommand [argument [argument ...]]
- PUBLISH channel message
- PUNSUBSCRIBE [pattern [pattern ...]]
- SUBSCRIBE channel [channel ...]
- UNSUBSCRIBE [channel [channel ...]]


Scripting
---------

https://redis.io/commands#scripting

- EVAL script numkeys key [key ...] arg [arg ...]

 .. warning::

    Method has a custom client side implementation.

    Command will only work if all keys point to the same slot. Otherwise a CROSSSLOT error will be raised.

- SCRIPT DEBUG YES|SYNC|NO

 .. warning::

    Command will only be sent to all master nodes in the cluster and result will be aggregated into a dict where the key will be the internal node name.

- SCRIPT EXISTS sha1 [sha1 ...]

 .. warning::

    Command will only be sent to all master nodes in the cluster and result will be aggregated into a dict where the key will be the internal node name.

- SCRIPT FLUSH

 .. warning::

    Command will only be sent to all master nodes in the cluster and result will be aggregated into a dict where the key will be the internal node name.

- SCRIPT KILL

 .. warning::

    Command has been blocked from executing in a cluster environment

- SCRIPT LOAD script

 .. warning::

    Command will only be sent to all master nodes in the cluster and result will be aggregated into a dict where the key will be the internal node name.


Server
------

https://redis.io/commands#server

- ACL LOAD

 .. warning::

    Command has been blocked from executing in a cluster environment

- ACL SAVE

 .. warning::

    Command has been blocked from executing in a cluster environment

- ACL LIST

 .. warning::

    Command has been blocked from executing in a cluster environment

- ACL USERS

 .. warning::

    Command has been blocked from executing in a cluster environment

- ACL GETUSER username

 .. warning::

    Command has been blocked from executing in a cluster environment

- ACL SETUSER username [rule [rule ...]]

 .. warning::

    Command has been blocked from executing in a cluster environment

- ACL DELUSER username [username ...]

 .. warning::

    Command has been blocked from executing in a cluster environment

- ACL CAT [categoryname]

 .. warning::

    Command has been blocked from executing in a cluster environment

- ACL GENPASS [bits]

 .. warning::

    Command has been blocked from executing in a cluster environment

- ACL WHOAMI

 .. warning::

    Command has been blocked from executing in a cluster environment

- ACL LOG [count or RESET]

 .. warning::

    Command has been blocked from executing in a cluster environment

- ACL HELP

 .. warning::

    Command has been blocked from executing in a cluster environment

- BGREWRITEAOF

 .. warning::

    Command is sent to all nodes in the cluster.

    Result from each node will be aggregated into a dict where the key will be the internal node name.

- BGSAVE [SCHEDULE]

 .. warning::
 
     Command is sent to all nodes in the cluster.
 
     Result from each node will be aggregated into a dict where the key will be the internal node name.

- **[NYV]** - COMMAND
- **[NYV]** - COMMAND COUNT
- **[NYV]** - COMMAND GETKEYS
- **[NYV]** - COMMAND INFO command-name [command-name ...]
- **[NYV]** - CONFIG GET parameter
- **[NYV]** - CONFIG REWRITE
- **[NYV]** - CONFIG SET parameter value
- **[NYV]** - CONFIG RESETSTAT
- **[NYV]** - DBSIZE
- **[NYV]** - DEBUG OBJECT key
- **[NYV]** - DEBUG SEGFAULT
- **[NYV]** - FLUSHALL [ASYNC]
- **[NYV]** - FLUSHDB [ASYNC]
- **[NYV]** - INFO [section]
- **[NYV]** - LOLWUT [VERSION version]
- **[NYV]** - LASTSAVE
- **[NYV]** - MEMORY DOCTOR
- **[NYV]** - MEMORY HELP
- **[NYV]** - MEMORY MALLOC-STATS
- **[NYV]** - MEMORY PURGE
- **[NYV]** - MEMORY STATS
- **[NYV]** - MEMORY USAGE key [SAMPLES count]
- **[NYV]** - MODULE LIST
- **[NYV]** - MODULE LOAD path [ arg [arg ...]]
- **[NYV]** - MODULE UNLOAD name
- **[NYV]** - MONITOR
- **[NYV]** - ROLE
- **[NYV]** - SAVE
- **[NYV]** - SHUTDOWN [NOSAVE|SAVE]
- **[NYV]** - SLAVEOF host port
- **[NYV]** - REPLICAOF host port
- **[NYV]** - SLOWLOG subcommand [argument]
- **[NYV]** - SWAPDB index1 index2
- **[NYV]** - SYNC
- **[NYV]** - PSYNC replicationid offset
- **[NYV]** - TIME

 .. note::
 
    Command is sent to all nodes in the cluster.

    Result is merged into a single dict with node as key.

- **[NYV]** - LATENCY DOCTOR
- **[NYV]** - LATENCY GRAPH event
- **[NYV]** - LATENCY HISTORY event
- **[NYV]** - LATENCY LATEST
- **[NYV]** - LATENCY RESET [event [event ...]]
- **[NYV]** - LATENCY HELP


Sets
----

https://redis.io/commands#set

- **[NYV]** - SADD key member [member ...]
- **[NYV]** - SCARD key
- **[NYV]** - SDIFF key [key ...]
- **[NYV]** - SDIFFSTORE destination key [key ...]
- **[NYV]** - SINTER key [key ...]
- **[NYV]** - SINTERSTORE destination key [key ...]
- **[NYV]** - SISMEMBER key member
- **[NYV]** - SMEMBERS key
- **[NYV]** - SMOVE source destination member
- **[NYV]** - SPOP key [count]
- **[NYV]** - SRANDMEMBER key [count]
- **[NYV]** - SREM key member [member ...]
- **[NYV]** - SUNION key [key ...]
- **[NYV]** - SUNIONSTORE destination key [key ...]
- **[NYV]** - SSCAN key cursor [MATCH pattern] [COUNT count]


Sorted Sets
-----------

https://redis.io/commands#sorted_set

- **[NYV]** - BZPOPMIN key [key ...] timeout
- **[NYV]** - BZPOPMAX key [key ...] timeout
- **[NYV]** - ZADD key [NX|XX] [CH] [INCR] score member [score member ...]
- **[NYV]** - ZCARD key
- **[NYV]** - ZCOUNT key min max
- **[NYV]** - ZINCRBY key increment member
- **[NYV]** - ZINTERSTORE destination numkeys key [key ...] [WEIGHTS weight [weight ...]] [AGGREGATE SUM|MIN|MAX]
- **[NYV]** - ZLEXCOUNT key min max
- **[NYV]** - ZPOPMAX key [count]
- **[NYV]** - ZPOPMIN key [count]
- **[NYV]** - ZRANGE key start stop [WITHSCORES]
- **[NYV]** - ZRANGEBYLEX key min max [LIMIT offset count]
- **[NYV]** - ZREVRANGEBYLEX key max min [LIMIT offset count]
- **[NYV]** - ZRANGEBYSCORE key min max [WITHSCORES] [LIMIT offset count]
- **[NYV]** - ZRANK key member
- **[NYV]** - ZREM key member [member ...]
- **[NYV]** - ZREMRANGEBYLEX key min max
- **[NYV]** - ZREMRANGEBYRANK key start stop
- **[NYV]** - ZREMRANGEBYSCORE key min max
- **[NYV]** - ZREVRANGE key start stop [WITHSCORES]
- **[NYV]** - ZREVRANGEBYSCORE key max min [WITHSCORES] [LIMIT offset count]
- **[NYV]** - ZREVRANK key member
- **[NYV]** - ZSCORE key member
- **[NYV]** - ZUNIONSTORE destination numkeys key [key ...] [WEIGHTS weight [weight ...]] [AGGREGATE SUM|MIN|MAX]
- **[NYV]** - ZSCAN key cursor [MATCH pattern] [COUNT count]


Streams
-------

https://redis.io/commands#stream

- **[NYV]** - XINFO [CONSUMERS key groupname] [GROUPS key] [STREAM key] [HELP]
- **[NYV]** - XADD key ID field value [field value ...]
- **[NYV]** - XTRIM key MAXLEN [~] count
- **[NYV]** - XDEL key ID [ID ...]
- **[NYV]** - XRANGE key start end [COUNT count]
- **[NYV]** - XREVRANGE key end start [COUNT count]
- **[NYV]** - XLEN key
- **[NYV]** - XREAD [COUNT count] [BLOCK milliseconds] STREAMS key [key ...] id [id ...]
- **[NYV]** - XGROUP [CREATE key groupname id-or-$] [SETID key groupname id-or-$] [DESTROY key groupname] [DELCONSUMER key groupname consumername]
- **[NYV]** - XREADGROUP GROUP group consumer [COUNT count] [BLOCK milliseconds] [NOACK] STREAMS key [key ...] ID [ID ...]
- **[NYV]** - XACK key group ID [ID ...]
- **[NYV]** - XCLAIM key group consumer min-idle-time ID [ID ...] [IDLE ms] [TIME ms-unix-time] [RETRYCOUNT count] [FORCE] [JUSTID]
- **[NYV]** - XPENDING key group [start end count] [consumer]


Strings
-------

https://redis.io/commands#string

- **[NYV]** - APPEND key value
- **[NYV]** - BITCOUNT key [start end]
- **[NYV]** - BITFIELD key [GET type offset] [SET type offset value] [INCRBY type offset increment] [OVERFLOW WRAP|SAT|FAIL]
- BITOP operation destkey key [key ...]

 .. note::
 
     Command only works if keys is in same slot. No custom client implementation exists.

- BITPOS key bit [start] [end]
- DECR key
- DECRBY key decrement
- GET key
- GETBIT key offset
- GETRANGE key start end
- GETSET key value
- INCR key
- INCRBY key increment
- INCRBYFLOAT key increment
- **[NYV]** - MGET key [key ...]
- **[NYV]** - MSET key value [key value ...]
- **[NYV]** - MSETNX key value [key value ...]
- **[NYV]** - PSETEX key milliseconds value
- SET key value [EX seconds|PX milliseconds|KEEPTTL] [NX|XX]
- SETBIT key offset value
- SETEX key seconds value
- SETNX key value
- **[NYV]** - SETRANGE key offset value
- **[NYV]** - STRALGO LCS algo-specific-argument [algo-specific-argument ...]
- **[NYV]** - STRLEN key


Transactions
------------

https://redis.io/commands#transactions

- **[NYV]** - DISCARD
- **[NYV]** - EXEC
- **[NYV]** - MULTI
- **[NYV]** - UNWATCH
- **[NYV]** - WATCH key [key ...]


Sentinel
--------

https://redis.io/topics/sentinel

Sentinel commands is no longer needed or really supported by redis now when cluster solution is in place. All `SENTINEL` commands have been blocked by this client to be executed on any node in the cluster.

- SENTINEL GET-MASTER-ADDR-BY-NAME
- SENTINEL MASTER
- SENTINEL MASTERS
- SENTINEL MONITOR
- SENTINEL REMOVE
- SENTINEL SENTINELS
- SENTINEL SET
- SENTINEL SLAVES

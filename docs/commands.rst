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

- **[NYV]** - CLUSTER ADDSLOTS slot [slot ...]
- **[NYV]** - CLUSTER BUMPEPOCH
- **[NYV]** - CLUSTER COUNT_FAILURE-REPORTS node-id
- CLUSTER COUNTKEYSINSLOT slot

 .. note::

    Client will route command to node that owns the slot

- **[NYV]** - CLUSTER DELSLOTS slot [slot ...]
- **[NYV]** - CLUSTER FAILOVER [FORCE|TAKEOVER]
- **[NYV]** - CLUSTER FLUSHSLOTS
- **[NYV]** - CLUSTER FORGET node-id
- CLUSTER GETKEYSINSLOT slot count

 .. note::

    Client will route command to node that owns the slot

- CLUSTER INFO

 .. note::
 
    Command is sent to all nodees in the cluster and result is merged into a single dict with node as key.

- **[NYV]** - CLUSTER KEYSLOT key
- **[NYV]** - CLUSTER MEET ip port
- **[NYV]** - CLUSTER MYID
- CLUSTER NODES

 .. note::

    Command will be sent to random node in the cluster as the data should be the same on all nodes in a stable/working cluster

- **[NYV]** - CLUSTER REPLICATE node-id
- **[NYV]** - CLUSTER RESET [HARD|SOFT]
- **[NYV]** - CLUSTER SAVECONFIG
- **[NYV]** - CLUSTER SET-CONFIG-EPOCH config-epoch
- **[NYV]** - CLUSTER SETSLOT slot IMPORTING|MIGRATING|STABLE|NODE [node-id]
- **[NYV]** - CLUSTER SLAVES node-id
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
- **[NYV]** - CLIENT ID
- **[NYV]** - CLIENT KILL [ip:port] [ID client-id] [TYPE normal|master|slave|pubsub] [USER username] [ADDR ip:port] [SKIPME yes/no]
- **[NYV]** - CLIENT LIST [TYPE normal|master|replica|pubsub]
- **[NYV]** - CLIENT GETNAME
- **[NYV]** - CLIENT GETREDIR
- **[NYV]** - CLIENT PAUSE timeout
- **[NYV]** - CLIENT REPLY ON|OFF|SKIP
- **[NYV]** - CLIENT SETNAME connection-name
- **[NYV]** - CLIENT TRACKING ON|OFF [REDIRECT client-id] [PREFIX prefix [PREFIX prefix ...]] [BCAST] [OPTIN] [OPTOUT] [NOLOOP]
- **[NYV]** - CLIENT UNBLOCK client-id [TIMEOUT|ERROR]
- **[NYV]** - ECHO message
- **[NYV]** - HELLO protover [AUTH username password] [SETNAME clientname]
- **[NYV]** - PING [message]
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

- **[NYV]** - HDEL key field [field ...]
- **[NYV]** - HEXISTS key field
- **[NYV]** - HGET key field
- **[NYV]** - HGETALL key
- **[NYV]** - HINCRBY key field increment
- **[NYV]** - HINCRBYFLOAT key field increment
- **[NYV]** - HKEYS key
- **[NYV]** - HLEN key
- **[NYV]** - HMGET key field [field ...]
- **[NYV]** - HMSET key field value [field value ...]
- **[NYV]** - HSET key field value [field value ...]
- **[NYV]** - HSETNX key field value
- **[NYV]** - HSTRLEN key field
- **[NYV]** - HVALS key
- **[NYV]** - HSCAN key cursor [MATCH pattern] [COUNT count]


Hyperloglog
-----------

https://redis.io/commands#hyperloglog

- **[NYV]** - PFADD key element [element ...]
- **[NYV]** - PFCOUNT key [key ...]
- **[NYV]** - PFMERGE destkey sourcekey [sourcekey ...]


Keys/Generic
------------

https://redis.io/commands#generic

- **[NYV]** - DEL key [key ...]
- **[NYV]** - DUMP key
- **[NYV]** - EXISTS key [key ...]
- **[NYV]** - EXPIRE key seconds
- **[NYV]** - EXPIREAT key timestamp
- **[NYV]** - KEYS pattern
- **[NYV]** - MIGRATE host port key|"" destination-db timeout [COPY] [REPLACE] [AUTH password] [AUTH2 username password] [KEYS key [key ...]]
- **[NYV]** - MOVE key db
- **[NYV]** - OBJECT subcommand [arguments [arguments ...]]
- **[NYV]** - PERSIST key
- **[NYV]** - PEXPIRE key milliseconds
- **[NYV]** - PEXPIREAT key milliseconds-timestamp
- **[NYV]** - PTTL key
- **[NYV]** - RANDOMKEY
- **[NYV]** - RENAME key newkey
- **[NYV]** - RENAMENX key newkey
- **[NYV]** - RESTORE key ttl serialized-value [REPLACE] [ABSTTL] [IDLETIME seconds] [FREQ frequency]
- **[NYV]** - SORT key [BY pattern] [LIMIT offset count] [GET pattern [GET pattern ...]] [ASC|DESC] [ALPHA] [STORE destination]
- **[NYV]** - TOUCH key [key ...]
- **[NYV]** - TTL key
- **[NYV]** - TYPE key
- **[NYV]** - UNLINK key [key ...]
- **[NYV]** - WAIT numreplicas timeout
- **[NYV]** - SCAN cursor [MATCH pattern] [COUNT count] [TYPE type]


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

- **[NYV]** - PSUBSCRIBE pattern [pattern ...]
- **[NYV]** - PUBSUB subcommand [argument [argument ...]]
- **[NYV]** - PUBLISH channel message
- **[NYV]** - PUNSUBSCRIBE [pattern [pattern ...]]
- **[NYV]** - SUBSCRIBE channel [channel ...]
- **[NYV]** - UNSUBSCRIBE [channel [channel ...]]


Scripting
---------

https://redis.io/commands#scripting

-- **[NYV]** - EVAL script numkeys key [key ...] arg [arg ...]
-- **[NYV]** - SCRIPT DEBUG YES|SYNC|NO
-- **[NYV]** - SCRIPT EXISTS sha1 [sha1 ...]
-- **[NYV]** - SCRIPT FLUSH
-- **[NYV]** - SCRIPT KILL
-- **[NYV]** - SCRIPT LOAD script


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

- **[NYV]** - BGREWRITEAOF
- **[NYV]** - BGSAVE [SCHEDULE]
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
- **[NYV]** - BITOP operation destkey key [key ...]
- **[NYV]** - BITPOS key bit [start] [end]
- **[NYV]** - DECR key
- **[NYV]** - DECRBY key decrement
- **[NYV]** - GET key
- **[NYV]** - GETBIT key offset
- **[NYV]** - GETRANGE key start end
- **[NYV]** - GETSET key value
- **[NYV]** - INCR key
- **[NYV]** - INCRBY key increment
- **[NYV]** - INCRBYFLOAT key increment
- **[NYV]** - MGET key [key ...]
- **[NYV]** - MSET key value [key value ...]
- **[NYV]** - MSETNX key value [key value ...]
- **[NYV]** - PSETEX key milliseconds value
- **[NYV]** - SET key value [EX seconds|PX milliseconds|KEEPTTL] [NX|XX]
- **[NYV]** - SETBIT key offset value
- **[NYV]** - SETEX key seconds value
- **[NYV]** - SETNX key value
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

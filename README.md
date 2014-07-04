# redis-py-cluster

Python cluster client for the official cluster support targeted for redis 3.0

This project is a port to python based on the redis-rb-cluster implementation done by antirez.

The original source can be found at https://github.com/antirez/redis-rb-cluster



## Dependencies

- redis >= 2.9.1 (Python client - https://github.com/andymccurdy/redis-py - Install [pip install redis])
- Cluster enabled redis servers. Only Redis 3.0 beta.7 and above is supported because of CLUSTER SLOTS command was introduced in that release.



## Docker

I have created a Dockerfile/Image that I recommend you to use to make testing of this lib easy. 

It can be found at https://github.com/Grokzen/docker-redis-cluster



## Implemented commands

If a command is not listed here then the default implementation in 'StrictRedis' is used.



### Fanout Commands

These commands is changed to send the same request to all nodes in sequence in the cluster and all results is returned as a dict.

 - bgrewriteaof
 - bgsave
 - client_kill
 - client_list
 - client_getname
 - client_setname
 - config_get
 - config_set
 - config_resetstat
 - config_rewrite
 - dbsize
 - echo
 - info
 - lastsave
 - ping
 - save
 - slowlog_get
 - slowlog_len
 - slowlog_reset
 - time

These commands is changed to send the same request to all nodes in sequence in the cluster and all results is returned as a unified list.

 - keys

These commands is only sent to all master nodes in the cluster.

 - flushall
 - flushdb

These methods will call each master node and return a dict with k,v pair (NodeID, Scan-result). I reccomend to use the *scan_iter functions.

  - scan


### Blocked commands

These commands is currently blocked from use in cluster mode. 
Either because they do not work or it is not good to use them with a cluster.

 - client_setname
 - sentinel
 - sentinel_get_master_addr_by_name
 - sentinel_master
 - sentinel_masters
 - sentinel_monitor
 - sentinel_remove
 - sentinel_sentinels
 - sentinel_set
 - sentinel_slaves
 - shutdown  # Danger to shutdown entire cluster at same time
 - slaveof  # Cluster management should be done via redis-trib.rb manually
 - restore
 - watch
 - unwatch
 - publish
 - eval
 - evalsha
 - script_exists
 - script_flush
 - script_kill
 - script_load
 - register_script
 - move  # It is not possible to move a key from one db to another in cluster mode
 - bitop  # Currently to hard to implement a solution in python space



### Overridden methods

These methods is overridden from StrictRedis to enable them to work in cluster mode.

 - mget
 - mset
 - msetnx
 - randomkey
 - rename
 - renamenx
 - brpoplpus
 - pfmerge
 - rpoplpush
 - sort
 - sscan
 - scan_iter
 - sscan_iter
 - hscan
 - hscan_iter
 - zscan
 - zscan_iter
 - sdiff
 - sdiffstore
 - sinter
 - sinterstore
 - smove
 - sunion
 - sunionstore
 - zinterstore
 - zunionstore



## Limitations and differences with redis-py

There is alot of differences that have to be taken into consideration when using cluster mode in redis.

Any method that can operate on multiple keys have to be reimplemented in the client and in some cases that is not possible to do. In general any method that is overriden in RedisCluster have lost the ability of being atomic. 

Pipelines do not work the same way in cluster mode. In 'StrictRedis' it batch all commands so that they can be executed at the same time when requested. But with RedisCluster pipelines will send the command directly to the server when it is called, but it will still store the result internally and return the same data from .execute(). This is done so that the code still behaves like a pipeline and no code will break. Some better solution will be implemented in the future but a true transactional pipeline will not be possible right now.

Alot of methods will behave very different when using RedisCluster. Some methods send the same request to all servers and return the result in another format then 'StrictRedis' do. Some methods is blocked because they do not work / is not implemented / is dangerous to use in cluster mode (like shutdown()).



## Usage example

Small sample script that show how to get started with RedisCluster(). 'decode_responses=True' is required to have when running on python3.

```python
from rediscluster import RedisCluster

startup_nodes = [
    {"host": "127.0.0.1", "port": "7000"}
]

rc = RedisCluster(startup_nodes=startup_nodes, decode_responses=True)
rc.set("foo", "bar")
rc.get("foobar")
```



## How to setup a cluster manually

 - This video will describe how to setup and use a redis cluster: http://vimeo.com/63672368 (This video is old so look at instructions in Redis cluster tutorial link below)
 - Redis cluster tutorial: http://redis.io/topics/cluster-tutorial
 - Redis cluster specs: http://redis.io/topics/cluster-spect



## Python support

Current python support is

- 2.7  Yes
- 3.2  Yes
- 3.3  (Not yet tested)
- 3.4  (Not yet tested)



## Redisco support

Redisco is a ORM lib for Django and it is a good lib for testing redis-py-cluster because it use alot of redis functionality. Currently all tests pass when running on python-3.2

The working redisco branch can be found at https://github.com/Grokzen/redisco/tree/python3



## Disclaimer

Both this client and Redis Cluster are a work in progress that is not suitable to be used in production environments. This is only my current personal opinion about both projects.



## License

MIT (See LICENSE file)

The license should be the same as redis-py library (https://github.com/andymccurdy/redis-py)

Implemented commands
====================

This will describe all changes that StrictRedisCluster have done to make a command to work in a cluster environment.

If a command is not listed here then the default implementation from `StrictRedis` in the `redis-py` library is used.



Fanout Commands
---------------

The following commands will send the same request to all nodes in the cluster. Results is returned as a dict with k,v pair (NodeID, Result).

 - bgrewriteaof
 - bgsave
 - client_getname
 - client_kill
 - client_list
 - client_setname
 - config_get
 - config_resetstat
 - config_rewrite
 - config_set
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

The pubsub commands are sent to all nodes, and the resulting replies are merged together. They have an optional keyword argument `aggregate` which when set to `False` will return a dict with k,v pair (NodeID, Result) instead of the merged result.

 - pubsub_channels
 - pubsub_numsub
 - pubsub_numpat

This command will send the same request to all nodes in the cluster in sequence. Results is appended to a unified list.

 - keys

The following commands will only be send to the master nodes in the cluster. Results is returned as a dict with k,v pair (NodeID, Command-Result).

 - flushall
 - flushdb
 - scan

This command will sent to a random node in the cluster.

 - publish

The following commands will be sent to the server that matches the first key.

 - eval
 - evalsha

This following commands will be sent to the master nodes in the cluster.

- script load - the result is the hash of loaded script
- script flush - the result is `True` if the command succeeds on all master nodes, else `False`
- script exists - the result is an array of booleans. An entry is `True` only if the script exists on all the master nodes.

The following commands will be sent to the sever that matches the specefied key.

 - hscan
 - hscan_iter
 - scan_iter
 - sscan
 - sscan_iter
 - zscan
 - zscan_iter



Blocked commands
----------------

The following commands is blocked from use.

Either because they do not work, there is no working implementation or it is not good to use them within a cluster.

 - bitop - Currently to hard to implement a solution in python space
 - client_setname - Not yet implemented
 - move - It is not possible to move a key from one db to another in cluster mode
 - restore
 - script_kill - Not yet implemented
 - sentinel
 - sentinel_get_master_addr_by_name
 - sentinel_master
 - sentinel_masters
 - sentinel_monitor
 - sentinel_remove
 - sentinel_sentinels
 - sentinel_set
 - sentinel_slaves
 - shutdown
 - slaveof - Cluster management should be done via redis-trib.rb manually
 - unwatch - Not yet implemented
 - watch - Not yet implemented



Overridden methods
------------------

The following methods is overridden from StrictRedis with a custom implementation.

They can operate on keys that exists in different hashslots and require a client side implementation to work.

 - brpoplpus
 - mget
 - mset
 - msetnx
 - pfmerge
 - randomkey
 - rename
 - renamenx
 - rpoplpush
 - sdiff
 - sdiffstore
 - sinter
 - sinterstore
 - smove
 - sort
 - sunion
 - sunionstore
 - zinterstore
 - zunionstore

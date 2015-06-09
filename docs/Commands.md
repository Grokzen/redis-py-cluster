# Implemented commands

This document will describe all changes that StrictRedisCluster have done to make a command to work.

If a command is not listed here then the default implementation in 'StrictRedis' is used.



# Fanout Commands

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
 - script_flush
 - slowlog_get
 - slowlog_len
 - slowlog_reset
 - time

This command will send the same request to all nodes in the cluster in sequence. Results is appended to a unified list.

 - keys

The following commands will only be send to the master nodes in the cluster. Results is returned as a dict with k,v pair (NodeID, Command-Result).

 - flushall
 - flushdb
 - scan

This command will sent to a random node in the cluster.

 - publish

This command will be sent to the server that matches the first key.

 - eval

The following commands will be sent to the sever that matches the specefied key.

 - hscan
 - hscan_iter
 - scan_iter
 - sscan
 - sscan_iter
 - zscan
 - zscan_iter



# Blocked commands

The following commands is blocked from use.

Either because they do not work, there is no working implementation or it is not good to use them within a cluster.

 - bitop - Currently to hard to implement a solution in python space
 - client_setname - Not yet implemented
 - evalsha - Lua scripting is not yet implemented
 - move - It is not possible to move a key from one db to another in cluster mode
 - register_script - Lua scripting is not yet implemented
 - restore
 - script_exists - Lua scripting is not yet implemented
 - script_kill - Lua scripting is not yet implemented
 - script_load - Lua scripting is not yet implemented
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



# Overridden methods

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

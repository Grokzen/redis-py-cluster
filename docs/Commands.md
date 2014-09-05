# Implemented commands

This document will describe all changes that RedisCluster have done to make a command to work.

If a command is not listed here then the default implementation in 'StrictRedis' is used.



# Fanout Commands

These commands will the same request to all nodes in the cluster in sequence. Results are packed into a dict with k,v pair (NodeID, Result).

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
 - script_flush

This command will send the same request to all nodes in the cluster in sequence. Results is appended to a unified list.

 - keys

These commands will only send to the master nodes in the cluster. Results will be returned as a dict with k,v pair (NodeID, Command-Result).

 - flushall
 - flushdb
 - scan

This command will pick a random node to send the command to.

 - publish

This command will be sent to the server that matches the first key.

 - eval

These commands will be sent to the sever that matches the specefied key.

 - sscan
 - scan_iter
 - sscan_iter
 - hscan
 - hscan_iter
 - zscan
 - zscan_iter



# Blocked commands

These commands is currently blocked from use in cluster mode.

Either because they do not work, there is no working implementation or it is not good to use them within a cluster.

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
 - evalsha
 - script_exists
 - script_kill
 - script_load
 - register_script
 - move  # It is not possible to move a key from one db to another in cluster mode
 - bitop  # Currently to hard to implement a solution in python space



# Overridden methods

These methods is overridden from StrictRedis with a custom code implementation, to enable them to work in cluster mode.

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
 - sdiff
 - sdiffstore
 - sinter
 - sinterstore
 - smove
 - sunion
 - sunionstore
 - zinterstore
 - zunionstore

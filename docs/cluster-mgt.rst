Cluster Mgt class
=================

The redis cluster can be managed through a cluster management class. It can for example be used to query the cluster for the current slots or the nodes setup.

The following methods is implemented:

- info
- slots
- nodes

The following methods is not yet implemented:

- addslots
- count_failure_reports
- countkeysinslot
- delslots
- failover
- forget
- getkeysinslot
- keyslot
- meet
- replicate
- reset
- saveconfig
- set_config_epoch
- setslot
- slaves



Usage example
-------------

.. code-block:: python

    >>> from rediscluster.cluster_mgt import RedisClusterMgt
    >>> startup_nodes = [{"host": "127.0.0.1", "port": "7000"}]
    >>> r = RedisClusterMgt(startup_nodes)
    >>> r.slots()
    {
        'slave': defaultdict(<type 'list'>, {
            '172.17.42.12:7003': [[0L, 5460L]],
            '172.17.42.12:7005': [[10923L, 16383L]],
            '172.17.42.12:7004': [[5461L, 10922L]]
        }),
        'master': defaultdict(<type 'list'>, {
            '172.17.42.12:7002': [[10923L, 16383L]],
            '172.17.42.12:7001': [[5461L, 10922L]],
            '172.17.42.12:7000': [[0L, 5460L]]
        })
    }

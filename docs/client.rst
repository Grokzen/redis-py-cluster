RedisCluster client configuration options
=========================================

This chapter is supposed to describe all the configuration options and flags that can be sent into the RedisCluster class instance. 

Each option will be described in a seperate topic to describe how it works and what it does. This will only describe any options that does anything else when compared to redis-py, or new options that is cluster specific.



host_port_remap
---------------

This option exists to enable the client to fix a problem where the redis-server internally tracks a different ip:port compared to what your clients would like to connect to.

The simples example to describe this problem is if you start a redis cluster through docker on your local machine. If we assume that you start the docker image grokzen/redis-cluster, when the redis cluster is initialized it will track the docker network IP for each node in the cluster.

For example this could be 172.18.0.2. The problem is that a client that runs outside on your local machine will recieve from the redis cluster that each node is reachable on the ip 172.18.0.2. But in some cases this IP is not available on your host system and to solve this we need a remapping table where we can tell this client that if you get back from your cluster 172.18.0.2 then your should remap it to localhost instead. When the client does this it can now connect and reach all nodes in your cluster.

It is also possible to remap the port for each node as well.

Example script

.. code-block:: python

    from rediscluster import RedisCluster

    startup_nodes = [{"host": "127.0.0.1", "port": "7000"}]

    rc = RedisCluster(
        startup_nodes=startup_nodes,
        decode_responses=True,
        host_port_remap=[
            {
                'from_host': '172.18.0.2',
                'from_port': 7000,
                'to_host': 'localhost',
                'to_port': 7000,
            },
            {
                'from_host': '172.22.0.1',
                'from_port': 7000,
                'to_host': 'localhost',
                'to_port': 7000,
            },
        ]
    )

    ## Debug output to show the client config/setup after client has been initialized.
    ## It should point to localhost:7000 for those nodes.
    print(rc.connection_pool.nodes.nodes)

    ## Test the client that it can still send and recieve data from the nodes after the remap has been done
    print(rc.set('foo', 'bar'))


Pleaes note that this host_port_remap feature will not work on the startup_nodes so you still need to put in a valid and reachable set of startup nodes.

RedisCluster client configuration options
=========================================

This chapter is supposed to describe all the configuration options and flags that can be sent into the RedisCluster class instance. 

Each option will be described in a seperate topic to describe how it works and what it does. This will only describe any options that does anything else when compared to redis-py, or new options that is cluster specific.



host_port_remap
---------------

This option exists to enable the client to fix a problem where the redis-server internally tracks a different ip:port compared to what your clients would like to connect to.

A simple example to describe this problem is if you start a redis cluster through docker on your local machine. If we assume that you start the docker image grokzen/redis-cluster,
when the redis cluster is initialized it will track the docker network IP for each node in the cluster.

For example this could be 172.18.0.2. The problem is that a client that runs outside on your local machine will receive from the redis cluster that each node is reachable on the ip 172.18.0.2.
But in some cases this IP is not available on your host system.To solve this we need a remapping table where we can tell this client that if you get back from your cluster 172.18.0.2 then your should remap it to localhost instead.
When the client does this it can now connect and reach all nodes in your cluster.


Remapping works off a rules list. Each rule is a dictionary of the form shown below

.. code-block::

    {
        'from_host': <Host name on redis server side>, # String
        'from_port': <Port on the redis server side>, # Integer
        'to_host': <Host name that the client needs to map to>, # String
        'to_port': <Port that the client needs to map to> # Integer
    }


Remapping properties:

- This host_port_remap feature will not work on the startup_nodes so you still need to put in a valid and reachable set of startup nodes.
- The remapping logic treats host_port_remap list as a "rules list" and only the first matching remapping entry will be applied
- A remapping rule may contain just host or just port mapping, but both sides of the maping( i.e. from_host and to_host or from_port and to_port) are required for either
- If both from_host and from_port are specified, then both will be used to decide if a remapping rule applies

Examples of valid rules:

.. code-block:: python

    {'from_host': "1.2.3.4", 'from_port': 1000, 'to_host': "2.2.2.2", 'to_port': 2000}

    {'from_host': "1.1.1.1", 'to_host': "127.0.0.1"}

    {'from_port': 1000, 'to_port': 2000}


Example scripts:

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

This feature is also useful in cases such as when one is trying to access AWS ElastiCache cluster secured by Stunnel (https://www.stunnel.org/)

.. code-block:: python

    from rediscluster import RedisCluster

    startup_nodes = [
        {"host": "127.0.0.1", "port": "17000"},
        {"host": "127.0.0.1", "port": "17001"},
        {"host": "127.0.0.1", "port": "17002"},
        {"host": "127.0.0.1", "port": "17003"},
        {"host": "127.0.0.1", "port": "17004"},
        {"host": "127.0.0.1", "port": "17005"}
    ]

    host_port_remap=[
        {'from_host': '41.1.3.1', 'from_port': 6379, 'to_host': '127.0.0.1', 'to_port': 17000},
        {'from_host': '41.1.3.5', 'from_port': 6379, 'to_host': '127.0.0.1', 'to_port': 17001},
        {'from_host': '41.1.4.2', 'from_port': 6379, 'to_host': '127.0.0.1', 'to_port': 17002},
        {'from_host': '50.0.1.7', 'from_port': 6379, 'to_host': '127.0.0.1', 'to_port': 17003},
        {'from_host': '50.0.7.3', 'from_port': 6379, 'to_host': '127.0.0.1', 'to_port': 17004},
        {'from_host': '32.0.1.1', 'from_port': 6379, 'to_host': '127.0.0.1', 'to_port': 17005}
    ]


    # Note: decode_responses must be set to True when used with python3
    rc = RedisCluster(
        startup_nodes=startup_nodes,
        host_port_remap=host_port_remap,
        decode_responses=True,
        ssl=True,
        ssl_cert_reqs=None,
        # Needed for Elasticache Clusters
        skip_full_coverage_check=True)


    print(rc.connection_pool.nodes.nodes)
    print(rc.ping())
    print(rc.set('foo', 'bar'))
    print(rc.get('foo'))

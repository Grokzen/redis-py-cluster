Readonly mode
=============

By default, Redis Cluster always returns MOVE redirection response on accessing slave node. You can overcome this limitation [for scaling read with READONLY mode](http://redis.io/topics/cluster-spec#scaling-reads-using-slave-nodes).

redis-py-cluster also implements this mode. You can access slave by passing `readonly_mode=True` to RedisCluster (or RedisCluster) constructor.

.. code-block:: python

    >>> from rediscluster import RedisCluster
    >>> startup_nodes = [{"host": "127.0.0.1", "port": "7000"}]
    >>> rc = RedisCluster(startup_nodes=startup_nodes, decode_responses=True)
    >>> rc.set("foo16706", "bar")
    >>> rc.set("foo81", "foo")
    True
    >>> rc_readonly = RedisCluster(startup_nodes=startup_nodes, decode_responses=True, readonly_mode=True)
    >>> rc_readonly.get("foo16706")
    u'bar'
    >>> rc_readonly.get("foo81")
    u'foo'

We can use pipeline via `readonly_mode=True` object.

.. code-block:: python

    >>> with rc_readonly.pipeline() as readonly_pipe:
    ...     readonly_pipe.get('foo81')
    ...     readonly_pipe.get('foo16706')
    ...     readonly_pipe.execute()
    ...
    [u'foo', u'bar']

But this mode has some downside or limitations.

- It is possible that you cannot get the latest data from READONLY mode enabled object because Redis implements asynchronous replication.
- **You MUST NOT use SET related operation with READONLY mode enabled object**, otherwise you can possibly get 'Too many Cluster redirections' error because we choose master and its slave nodes randomly.
 - You should use get related stuff only.
 - Ditto with pipeline, otherwise you can get 'Command # X (XXXX) of pipeline: MOVED' error.

.. code-block:: python

    >>> rc_readonly = RedisCluster(startup_nodes=startup_nodes, decode_responses=True, readonly_mode=True)
    >>> # NO: This works in almost case, but possibly emits Too many Cluster redirections error...
    >>> rc_readonly.set('foo', 'bar')
    >>> # OK: You should always use get related stuff...
    >>> rc_readonly.get('foo')

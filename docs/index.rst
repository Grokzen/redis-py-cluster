.. redis-py-cluster documentation master file, created by
   sphinx-quickstart on Tue Mar 29 23:29:46 2016.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to redis-py-cluster's documentation!
============================================

This project is a port of `redis-rb-cluster` by antirez, with alot of added functionality. The original source can be found at https://github.com/antirez/redis-rb-cluster.


The source code is `available on github`_.

.. _available on github: http://github.com/grokzen/pykwalify



Installation
------------

Latest stable release from pypi

.. code-block:: bash

    $ pip install redis-py-cluster

or from source code

.. code-block:: bash

    $ python setup.py install



Usage example
-------------

Small sample script that shows how to get started with RedisCluster. It can also be found in the file `exmaples/basic.py`

.. code-block:: python

    >>> from rediscluster import StrictRedisCluster

    >>> startup_nodes = [{"host": "127.0.0.1", "port": "7000"}]

    >>> # Note: decode_responses must be set to True when used with python3
    >>> rc = StrictRedisCluster(startup_nodes=startup_nodes, decode_responses=True)

    >>> rc.set("foo", "bar")
    True
    >>> print(rc.get("foo"))
    'bar'



Dependencies & supported python versions
----------------------------------------

- Python: redis >= `2.10.2`, <= `2.10.5` is required.
  Older versions in the `2.10.x` series can work but using the latest one is allways recommended.
- Optional Python: hiredis >= `0.2.0`. Older versions might work but is not tested.
- A working Redis cluster based on version >= `3.0.0` is required. Only `3.0.x` releases is supported.



Supported python versions
-------------------------

- 2.7.x
- 3.3.x
- 3.4.1+
- 3.5.x

Experimental:

- Up to 3.6.0a0


.. note:: Python 3.4.0

    A segfault was found when running `redis-py` in python `3.4.0` that was introduced into the codebase in python `3.4.0`. Because of this both `redis-py` and `redis-py-cluster` will not work when running with `3.4.0`. This lib has decided to block the lib from execution on `3.4.0` and you will get a exception when trying to import the code. The only solution is to use python `3.4.1` or some other higher minor version in the `3.4` series.



The Usage Guide
---------------

.. _cluster_docs:

.. toctree::
   :maxdepth: 2
   :glob:

   cluster-mgt
   command-differences
   limitations-and-differences
   pipelines
   threaded-pipelines
   pubsub
   readonly-mode


.. _setup_and_performance:

.. toctree::
   :maxdepth: 2
   :glob:

   setup-redis-cluster
   benchmarks



The Community Guide
--------------------

.. _community-guide:

.. toctree::
    :maxdepth: 1
    :glob:

    testing
    upgrade-instructions
    release-notes
    authors
    license

.. redis-py-cluster documentation master file, created by
   sphinx-quickstart on Tue Mar 29 23:29:46 2016.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to redis-py-cluster's documentation!
============================================

This project is a port of `redis-rb-cluster` by antirez, with a lot of added functionality.

The original source can be found at https://github.com/antirez/redis-rb-cluster.

The source code for this project is `available on github`_.

.. _available on github: http://github.com/grokzen/redis-py-cluster



Installation
------------

Latest stable release from pypi

.. code-block:: bash

    $ pip install redis-py-cluster

or from source code

.. code-block:: bash

    $ python setup.py install



Basic usage example
-------------

Small sample script that shows how to get started with RedisCluster. It can also be found in the file `exmaples/basic.py`.

Additional code examples of more advance functionality can be found in the `examples/` folder in the source code git repo.

.. code-block:: python

    >>> from rediscluster import RedisCluster

    >>> # Requires at least one node for cluster discovery. Multiple nodes is recommended.
    >>> startup_nodes = [{"host": "127.0.0.1", "port": "7000"}]

    >>> # Note: See note on Python 3 for decode_responses behaviour
    >>> rc = RedisCluster(startup_nodes=startup_nodes, decode_responses=True)

    >>> rc.set("foo", "bar")
    True
    >>> print(rc.get("foo"))
    'bar'

.. note:: Python 3

    Since Python 3 changed to Unicode strings from Python 2's ASCII, the return type of *most* commands will be binary strings,
    unless the class is instantiated with the option ``decode_responses=True``.

    In this case, the responses will be Python 3 strings (Unicode).

    For the init argument `decode_responses`, when set to False, redis-py-cluster will not attempt to decode the responses it receives.

    In Python 3, this means the responses will be of type `bytes`. In Python 2, they will be native strings (`str`).

    If `decode_responses` is set to True, for Python 3 responses will be `str`, for Python 2 they will be `unicode`.



Library Dependencies
--------------------

It is always recommended to use the latest version of the dependencies of this project.

- Redis-py: 'redis>=3.0.0,<3.1.0' is required in this major version of this cluster lib.
- Optional Python: hiredis >= `0.2.0`. Older versions might work but is not tested.
- A working Redis cluster based on version `>=3.0.0` is required.



Supported python versions
-------------------------

Python versions should follow the same supported python versions as specificed by the upstream package `redis-py`, based on what major version(s) that is specified.

If this library supports more then one major version line of `redis-py`, then the supported python versions must include the set of supported python versions by all major version lines.

- 2.7
- 3.5
- 3.6
- 3.7
- 3.8



Regarding duplicate package name on pypi
----------------------------------------

It has been found that the python module name that is used in this library (rediscluster) is already shared with a similar but older project.

This lib will `NOT` change the naming of the module to something else to prevent collisions between the libs.

My reasoning for this is the following

 - Changing the namespace is a major task and probably should only be done in a complete rewrite of the lib, or if the lib had plans for a version 2.0.0 where this kind of backwards incompatibility could be introduced.
 - This project is more up to date, the last merged PR in the other project was 3 years ago.
 - This project is aimed for implement support for the cluster support in 3.0+, the other lib do not have that right now, but they implement almost the same cluster solution as the 3.0+ but in much more in the client side.
 - The 2 libs is not compatible to be run at the same time even if the name would not collide. It is not recommended to run both in the same python interpreter.

An issue has been raised in each repository to have tracking of the problem.

redis-py-cluster: https://github.com/Grokzen/redis-py-cluster/issues/150

rediscluster: https://github.com/salimane/rediscluster-py/issues/11



The Usage Guide
---------------

.. _cluster_docs:

.. toctree::
   :maxdepth: 2
   :glob:

   commands
   limitations-and-differences
   pipelines
   pubsub
   readonly-mode


.. _setup_and_performance:

.. toctree::
   :maxdepth: 2
   :glob:

   cluster-setup
   benchmarks



The Community Guide
--------------------

.. _community-guide:

.. toctree::
    :maxdepth: 2
    :glob:

    project-status
    testing
    upgrading
    release-notes
    authors
    license
    disclaimer

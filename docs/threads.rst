Threaded Pipeline
=================

Redis cluster optionally supports parallel execution of pipelined commands to reduce latency of pipelined requests via threads. 


Rationale
---------

When pipelining a bunch of commands to the cluster, many of the commands may be routed to different nodes in the cluster. The client-server design in redis-cluster dictates that the client communicates directly with each node in the cluster rather than treating each node as a homogenous group. 

The advantage to this design is that a smart client can communicate with the cluster with the same latency characteristics as it might communicate with a single-instance redis cluster. But only if the client can communicate with each node in parallel. 



Parallel network i/o using threads
----------------------------------

That's pretty good. But we are still issuing those 3 network requests in serial order. The code loops through each node and issues a request, then gets the response, then issues the next one. 

We improve the situation by using python threads, making each request in parallel over the network. Now we are only as slow as the slowest single request.

### Disabling Threads
You can disable threaded execution either in the class constructor:

.. code-block:: python

    r = rediscluster.StrictRedisCluster( ... pipeline_use_threads=False) #true by default
    pipe = r.pipeline()

Or you can disable it on a case by case basis as you instantiate the pipeline object.

.. code-block:: python

    pipe = r.pipeline(use_threads=False)

The later example always overrides if explicitly set. Otherwise, it falls back on the value passed to the StrictRedisCluster constructor.



Footnote: Gevent
----------------

Python offers something even more lightweight and efficient than threads to perform tasks in parallel: GEVENT.

You can read up more about gevent here: http://www.gevent.org/

If you want to try to get the benefits of gevent in redis-py-cluster, you can monkey patch your code with the following lines at the very beginning of your application:
 
.. code-block:: python

    import os
    os.environ["GEVENT_RESOLVER"] = "ares"
    import gevent.monkey
    gevent.monkey.patch_all()

This will patch the python socket code, threaded libraries, and dns resolution into a single threaded application substituting coroutines for parallel threads.

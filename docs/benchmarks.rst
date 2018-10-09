Benchmarks
==========

There is a few benchmarks that is designed to test specific parts of the code that will show how big of a performance difference there is between using this lib and the normal Redis client.



Setup benchmarks
----------------

Before running any benchmark you should install this lib in editable mode inside a virtualenv so it can import `StrictRedisCluster` lib.

Install with

.. code-block:: bash
    
    pip install -e .

You also need a few redis servers to test against. It is required to have 1 cluster with atleast one node on port `7001` and it also required to have a non-clustered server on port `7007`.



Implemented Bencmarks
---------------------

- `simple.py`, This benchmark can be used to messure a simple `set` and `get` operation chain. It also support running pipelines bu adding the flag `--pipeline`



Run predefined benchmarks
-------------------------

There is a set of predefined benchmarks that can be runned to messure performance drop from using this library.

To run the benchmarks run

.. code-block:: bash

    make benchmark

Example output and comparison of different runmodes

.. code-block::

     -- Running Simple benchmark with StrictRedis lib and non cluster server, 50 concurrent processes and total 50000*2 requests --
    python benchmarks/simple.py --host 172.16.166.31 --timeit --nocluster -c 50 -n 50000
    100.0k SET/GET operations took: 2.45 seconds... 40799.93 operations per second

     -- Running Simple benchmark with StrictRedisCluster lib and cluster server, 50 concurrent processes and total 50000*2 requests --
    python benchmarks/simple.py --host 172.16.166.31 --timeit -c 50 -n 50000
    100.0k SET/GET operations took: 9.51 seconds... 31513.71 operations per second

     -- Running Simple benchmark with pipelines & StrictRedis lib and non cluster server --
    python benchmarks/simple.py --host 172.16.166.31 --timeit --nocluster -c 50 -n 50000 --pipeline
    100.0k SET/GET operations took: 2.1728243827819824 seconds... 46023.047602201834 operations per second

     -- Running Simple benchmark with StrictRedisCluster lib and cluster server
    python benchmarks/simple.py --host 172.16.166.31 --timeit -c 50 -n 50000 --pipeline
    100.0k SET/GET operations took: 1.7181339263916016 seconds... 58202.68051514381 operations per second
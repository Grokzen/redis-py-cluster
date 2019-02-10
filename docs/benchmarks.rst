Benchmarks
==========

These are a few benchmarks that are designed to test specific parts of the code to demonstrate the performance difference between using this lib and the normal Redis client.



Setup benchmarks
----------------

Before running any benchmark you should install this lib in editable mode inside a virtualenv so it can import `RedisCluster` lib.

Install with

.. code-block:: bash
    
    pip install -e .

You also need a few redis servers to test against. You must have one cluster with at least one node on port `7001` and you must also have a non-clustered server on port `7007`.



Implemented benchmarks
---------------------

- `simple.py`, This benchmark can be used to measure a simple `set` and `get` operation chain. It also supports running pipelines by adding the flag `--pipeline`.



Run predefined benchmarks
-------------------------

These are a set of predefined benchmarks that can be run to measure the performance drop from using this library.

To run the benchmarks run

.. code-block:: bash

    make benchmark

Example output and comparison of different runmodes

.. code-block::

     -- Running Simple benchmark with Redis lib and non cluster server, 50 concurrent processes and total 50000*2 requests --
    python benchmarks/simple.py --host 127.0.0.1 --timeit --nocluster -c 50 -n 50000
    50.0k SET/GET operations took: 2.45 seconds... 40799.93 operations per second

     -- Running Simple benchmark with RedisCluster lib and cluster server, 50 concurrent processes and total 50000*2 requests --
    python benchmarks/simple.py --host 127.0.0.1 --timeit -c 50 -n 50000
    50.0k SET & GET (each 50%) operations took: 9.51 seconds... 31513.71 operations per second

     -- Running Simple benchmark with pipelines & Redis lib and non cluster server --
    python benchmarks/simple.py --host 127.0.0.1 --timeit --nocluster -c 50 -n 50000 --pipeline
    50.0k SET & GET (each 50%) operations took: 2.1728243827819824 seconds... 46023.047602201834 operations per second

     -- Running Simple benchmark with RedisCluster lib and cluster server
    python benchmarks/simple.py --host 127.0.0.1 --timeit -c 50 -n 50000 --pipeline
    50.0k SET & GET (each 50%) operations took: 1.7181339263916016 seconds... 58202.68051514381 operations per second
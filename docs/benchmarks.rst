Benchmarks
==========

These are a few benchmarks that are designed to test specific parts of the code to demonstrate the performance difference between using this lib and the normal Redis client.



Setup benchmarks
----------------

Before running any benchmark you should install this lib in editable mode inside a virtualenv so it can import `StrictRedisCluster` lib.

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

     -- Running Simple benchmark with StrictRedis lib and non cluster server --
    python benchmarks/simple.py --port 7007 --timeit --nocluster
    10.0k SET/GET operations took: 0.9711470603942871 seconds... 10297.10165208139 operations per second
    20.0k SET/GET operations took: 1.9136295318603516 seconds... 10451.343725113202 operations per second
    40.0k SET/GET operations took: 3.8409764766693115 seconds... 10414.018477584079 operations per second

     -- Running Simple benchmark with StrictRedisCluster lib and cluster server --
    python benchmarks/simple.py --port 7001 --timeit
    10.0k SET/GET operations took: 0.760077714920044 seconds... 13156.549394494412 operations per second
    20.0k SET/GET operations took: 1.5251967906951904 seconds... 13113.061948474155 operations per second
    40.0k SET/GET operations took: 3.05112361907959 seconds... 13109.924406165655 operations per second

     -- Running Simple benchmark with pipelines & StrictRedis lib and non cluster server --
    python benchmarks/simple.py --port 7007 --timeit --pipeline --nocluster
    10.0k SET/GET operations inside pipelines took: 0.8831894397735596 seconds... 11322.599149921782 operations per second
    20.0k SET/GET operations inside pipelines took: 1.6283915042877197 seconds... 12282.058674058404 operations per second
    40.0k SET/GET operations inside pipelines took: 3.2882907390594482 seconds... 12164.374495498905 operations per second

     -- Running Simple benchmark with StrictRedisCluster lib and cluster server
    python benchmarks/simple.py --port 7001 --timeit --pipeline
    10.0k SET/GET operations inside pipelines took: 0.709221601486206 seconds... 14099.965340937933 operations per second
    20.0k SET/GET operations inside pipelines took: 1.3776116371154785 seconds... 14517.879684783395 operations per second
    40.0k SET/GET operations inside pipelines took: 2.794893980026245 seconds... 14311.813001087214 operations per second

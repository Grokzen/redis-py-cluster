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

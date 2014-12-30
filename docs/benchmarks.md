# Benchmarks

There is a few benchmarks that is designed to test specific parts of the code that will show how big of a performance difference there is between using this lib and the normal Redis client.



## Setup benchmarks

Before running any benchmark you should install this lib in editable mode inside a virtualenv so it can import `RedisCluster` lib.

Install with

```
$ pip install -e .
```


## Bencmarks

`simple.py` - This benchmark can be used to messure a simple `set` and `get` operation chain.



## Run predefined benchmarks

There is a set of predefined benchmarks that can be runned to messure performance drop from using this library.

To run the benchmarks

```
make benchmark
```

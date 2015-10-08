# Scripting support

Scripting support is limited to scripts that operate on keys in the same key slot.
If a script is executed via `evalsha`, `eval` or by calling the callable returned by
`register_script` and the keys passed as arguments do not map to the same key slot,
a `RedisClusterException` will be thrown.

It is however, possible to query a key within the script, that is not passed
as an argument of `eval`, `evalsha`. In this scenarios it is not possible to detect
the error early and redis itself will raise an error which will be percolated
to the user. For example:

```python
    cluster = RedisCluster('localhost', 7000)
    script = """
    return redis.call('GET', KEYS[1]) * redis.call('GET', ARGV[1])
    """
    # this will succeed
    cluster.eval(script, 1, "A{Foo}", "A{Foo}")
    # this will fail as "A{Foo}" and "A{Bar}" are on different key slots.
    cluster.eval(script, 1, "A{Foo}", "A{Bar}")
```

## Unsupported operations

- The `SCRIPT KILL` command is not yet implemented.
- Scripting in the context of a pipeline is not yet implemented.

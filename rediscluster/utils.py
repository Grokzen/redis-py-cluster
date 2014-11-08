# -*- coding: utf-8 -*-

# rediscluster imports
from .exceptions import RedisClusterException, ClusterDownException


def string_keys_to_dict(key_strings, callback):
    """
    # TODO: Write
    """
    return dict.fromkeys(key_strings, callback)


def dict_merge(*dicts):
    """
    # TODO: Write
    """
    merged = {}
    [merged.update(d) for d in dicts]
    return merged


def blocked_command(self, command):
    """
    # TODO: Write
    """
    raise RedisClusterException("Command: {} is blocked in redis cluster mode".format(command))


def merge_result(command, res):
    """
    # TODO: Write
    """
    # TODO: Simplify/optimize
    result = set([])
    for k, v in res.items():
        for value in v:
            result.add(value)
    return list(result)


def first_key(command, res):
    """
    # TODO: Write
    """
    if len(res.keys()) != 1:
        raise RedisClusterException("More then 1 result from command: {0}".format(command))
    return list(res.values())[0]


def clusterdown_wrapper(func):
    """
    Wrapper for CLUSTERDOWN error handling.

    If the cluster reports it is down it is assumed that:
     - connection_pool was disconnected
     - connection_pool was reseted
     - refereh_table_asap set to True

    It will try 3 times to rerun the command and raises ClusterDownException if it continues to fail.
    """
    def inner(*args, **kwargs):
        for i in range(0, 3):
            try:
                return func(*args, **kwargs)
            except ClusterDownException:
                # Try again with the new cluster setup. All other errors
                # should be raised.
                pass

        # If it fails 3 times then raise exception back to caller
        raise ClusterDownException("CLUSTERDOWN error. Unable to rebuild the cluster")
    return inner

# -*- coding: utf-8 -*-

# rediscluster imports
from .exceptions import RedisClusterException


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

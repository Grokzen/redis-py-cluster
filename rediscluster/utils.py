# -*- coding: utf-8 -*-
from socket import gethostbyaddr

# rediscluster imports
from .exceptions import RedisClusterException, ClusterDownException


def is_dict(d):
    """
    Test if variable is a dict or not.
    """
    assert isinstance(d, dict)
    return True


def string_keys_to_dict(key_strings, callback):
    """
    Maps each string in `key_strings` to `callback` function
    and return as a dict.
    """
    return dict.fromkeys(key_strings, callback)


def dict_merge(*dicts):
    """
    Merge all provided dicts into 1 dict.
    """
    merged = {}
    for d in dicts:
        if is_dict(d):
            merged.update(d)
    return merged


def blocked_command(self, command):
    """
    Raises a `RedisClusterException` mentioning the command is blocked.
    """
    raise RedisClusterException("Command: {} is blocked in redis cluster mode".format(command))


def merge_result(command, res):
    """
    Merge all items in `res` into a list.

    This command is used when sending a command to multiple nodes
    and they result from each node should be merged into a single list.
    """
    is_dict(res)

    result = set([])
    for _, v in res.items():
        for value in v:
            result.add(value)
    return list(result)


def first_key(command, res):
    """
    Returns the first result for the given command.

    If more then 1 result is returned then a `RedisClusterException` is raised.
    """
    is_dict(res)

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
        for _ in range(0, 3):
            try:
                return func(*args, **kwargs)
            except ClusterDownException:
                # Try again with the new cluster setup. All other errors
                # should be raised.
                pass

        # If it fails 3 times then raise exception back to caller
        raise ClusterDownException("CLUSTERDOWN error. Unable to rebuild the cluster")
    return inner


def nslookup(node_ip):
    if ':' not in node_ip:
        return gethostbyaddr(node_ip)[0]
    ip, port = node_ip.split(':')
    return '%s:%s' % (gethostbyaddr(ip)[0], port)

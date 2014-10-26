# -*- coding: utf-8 -*-

# rediscluster imports
from .exceptions import RedisClusterException


def send_eval_to_connection(func):
    """
    If all the keys route to the same slot we can safely route the script to a node in the cluster.
    """
    def inner(self, script, numkeys, *keys_and_args):
        if numkeys < 1:
            raise RedisClusterException(" ERROR: eval only works with 1 or more keys when running redis in cluster mode...")

        # verify that the keys all map to the same key hash slot.
        # this will be true if there is only one key, or if all the keys are in the form:
        # A{foo} B{foo} C{foo}
        if len(set([self.keyslot(key) for key in keys_and_args[0:numkeys]])) != 1:
            raise RedisClusterException(" ERROR: eval only works if all keys map to the same key slot when running redis in cluster mode...")
        conn = self.get_connection_by_key(keys_and_args[0])
        return func(conn, script, numkeys, *keys_and_args)
    return inner


def block_command(func):
    """
    Prints error because some commands should be blocked when running in cluster-mode
    """
    def inner(*args, **kwargs):
        raise RedisClusterException("ERROR: Calling function {} is blocked when running redis in cluster mode...".format(func.__name__))
    return inner


def block_pipeline_command(func):
    """
    Prints error because some pipelined commands should be blocked when running in cluster-mode
    """
    def inner(*args, **kwargs):
        raise RedisClusterException("ERROR: Calling pipelined function {} is blocked when running redis in cluster mode...".format(func.__name__))
    return inner

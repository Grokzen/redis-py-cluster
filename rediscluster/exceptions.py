# -*- coding: utf-8 -*-

from redis.exceptions import (
    ResponseError, RedisError,
)


class RedisClusterConfigError(Exception):
    """
    """
    pass


class RedisClusterException(Exception):
    """
    """
    pass


class RedisClusterError(Exception):
    """
    """
    pass


class ClusterDownException(Exception):
    """
    """
    pass


class ClusterError(RedisError):
    """
    """
    pass


class ClusterCrossSlotError(ResponseError):
    """
    """
    message = "Keys in request don't hash to the same slot"


class ClusterDownError(ClusterError, ResponseError):
    """
    """

    def __init__(self, resp):
        self.args = (resp, )
        self.message = resp


class AskError(ResponseError):
    """
    src node: MIGRATING to dst node
        get > ASK error
        ask dst node > ASKING command
    dst node: IMPORTING from src node
        asking command only affects next command
        any op will be allowed after asking command
    """

    def __init__(self, resp):
        """should only redirect to master node"""
        self.args = (resp, )
        self.message = resp
        slot_id, new_node = resp.split(' ')
        host, port = new_node.rsplit(':', 1)
        self.slot_id = int(slot_id)
        self.node_addr = self.host, self.port = host, int(port)


class TryAgainError(ResponseError):
    """
    """

    def __init__(self, *args, **kwargs):
        pass


class MovedError(AskError):
    """
    """
    pass


class MasterDownError(ClusterDownError):
    """
    """
    pass


class SlotNotCoveredError(RedisClusterException):
    """
    This error only happens in the case where the connection pool will try to
    fetch what node that is covered by a given slot.

    If this error is raised the client should drop the current node layout and
    attempt to reconnect and refresh the node layout again
    """
    pass

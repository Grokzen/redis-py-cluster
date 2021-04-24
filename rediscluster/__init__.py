# -*- coding: utf-8 -*-

# python std lib
import logging

# rediscluster imports
from rediscluster.client import RedisCluster
from rediscluster.connection import (
    ClusterBlockingConnectionPool,
    ClusterConnection,
    ClusterConnectionPool,
)
from rediscluster.exceptions import (
    RedisClusterException,
    RedisClusterError,
    ClusterDownException,
    ClusterError,
    ClusterCrossSlotError,
    ClusterDownError,
    AskError,
    TryAgainError,
    MovedError,
    MasterDownError,
)
from rediscluster.pipeline import ClusterPipeline


def int_or_str(value):
    try:
        return int(value)
    except ValueError:
        return value


# Major, Minor, Fix version
__version__ = '2.1.3'
VERSION = tuple(map(int_or_str, __version__.split('.')))

__all__ = [
    'AskError',
    'ClusterBlockingConnectionPool',
    'ClusterConnection',
    'ClusterConnectionPool',
    'ClusterCrossSlotError',
    'ClusterDownError',
    'ClusterDownException',
    'ClusterError',
    'ClusterPipeline',
    'MasterDownError',
    'MovedError',
    'RedisCluster',
    'RedisClusterError',
    'RedisClusterException',
    'TryAgainError',
]

# Set default logging handler to avoid "No handler found" warnings.
logging.getLogger(__name__).addHandler(logging.NullHandler())

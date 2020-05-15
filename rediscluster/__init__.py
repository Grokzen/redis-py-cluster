# -*- coding: utf-8 -*-

# python std lib
import sys

# Import shortcut
from .client import RedisCluster
from .pipeline import ClusterPipeline
from .pubsub import ClusterPubSub

# Monkey patch RedisCluster class into redis for easy access
import redis
setattr(redis, "RedisCluster", RedisCluster)
setattr(redis, "ClusterPubSub", ClusterPubSub)
setattr(redis, "ClusterPipeline", ClusterPipeline)

# Major, Minor, Fix version
__version__ = (2, 1, 0)

def int_or_str(value):
    try:
        return int(value)
    except ValueError:
        return value


__version__ = '2.1.0'
VERSION = tuple(map(int_or_str, __version__.split('.')))

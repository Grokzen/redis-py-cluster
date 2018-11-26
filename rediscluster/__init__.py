# -*- coding: utf-8 -*-

# python std lib
import sys

# Import shortcut
from .client import RedisCluster
from .pipeline import StrictClusterPipeline
from .pubsub import ClusterPubSub

# Monkey patch RedisCluster class into redis for easy access
import redis
setattr(redis, "RedisCluster", RedisCluster)
setattr(redis, "ClusterPubSub", ClusterPubSub)
setattr(redis, "StrictClusterPipeline", StrictClusterPipeline)

# Major, Minor, Fix version
__version__ = (2, 0, 0)

def int_or_str(value):
    try:
        return int(value)
    except ValueError:
        return value


__version__ = '2.0.0'
VERSION = tuple(map(int_or_str, __version__.split('.')))

if sys.version_info[0:3] == (3, 4, 0):
    raise RuntimeError("CRITICAL: rediscluster do not work with python 3.4.0. Please use 3.4.1 or higher.")

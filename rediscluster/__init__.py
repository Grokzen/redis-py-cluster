# -*- coding: utf-8 -*-

# python std lib
import sys

# Import shortcut
from .client import StrictRedisCluster, RedisCluster
from .pipeline import StrictClusterPipeline
from .pubsub import ClusterPubSub

# Monkey patch RedisCluster class into redis for easy access
import redis
setattr(redis, "StrictRedisCluster", StrictRedisCluster)
setattr(redis, "RedisCluster", RedisCluster)
setattr(redis, "ClusterPubSub", ClusterPubSub)
setattr(redis, "StrictClusterPipeline", StrictClusterPipeline)

# Major, Minor, Fix version
__version__ = (1, 3, 1)

if sys.version_info[0:3] == (3, 4, 0):
    raise RuntimeError("CRITICAL: rediscluster do not work with python 3.4.0. Please use 3.4.1 or higher.")

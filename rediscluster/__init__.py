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
__version__ = (0, 2, 0)

if sys.version_info[0:3] == (3, 4, 0):
    print("CRITICAL: rediscluster do not work with python 3.4.0")
    sys.exit(1)

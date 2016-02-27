# -*- coding: utf-8 -*-

# python std lib
import sys

# Import shortcut
from .client import StrictRedisCluster, RedisCluster
from .cluster_mgt import RedisClusterMgt  # NOQA
from .pipeline import StrictClusterPipeline

# Monkey patch RedisCluster class into redis for easy access
import redis
setattr(redis, "StrictRedisCluster", StrictRedisCluster)
setattr(redis, "RedisCluster", RedisCluster)
setattr(redis, "StrictClusterPipeline", StrictClusterPipeline)

# Major, Minor, Fix version
__version__ = (1, 1, 0)

if sys.version_info[0:3] == (3, 4, 0):
    raise RuntimeError("CRITICAL: rediscluster do not work with python 3.4.0. Please use 3.4.1 or higher.")

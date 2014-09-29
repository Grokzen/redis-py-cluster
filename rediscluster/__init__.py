# Import shortcut
from rediscluster.client import RedisCluster

# Monkey patch RedisCluster class into redis for easy access
import redis
setattr(redis, "RedisCluster", RedisCluster)

# Major, Minor, Fix version
__version__ = (0, 1, 0)

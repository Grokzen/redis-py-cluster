# Import shortcut
from .rediscluster import RedisCluster

# Monkey patch RedisCluster class into redis for easy access
import redis
setattr(redis, "RedisCluster", RedisCluster)

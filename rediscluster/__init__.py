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
__version__ = (0, 1, 0)

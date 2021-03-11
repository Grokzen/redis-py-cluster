from redis._compat import xrange
from rediscluster import RedisCluster

startup_nodes = [{"host": "127.0.0.1", "port": 7000}]
r = RedisCluster(startup_nodes=startup_nodes, max_connections=32)

for i in xrange(1000000):
    d = str(i)
    r.set(d, d)
    r.incrby(d, 1)

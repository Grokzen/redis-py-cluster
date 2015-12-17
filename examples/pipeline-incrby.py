from redis._compat import xrange
from rediscluster import RedisCluster

startup_nodes = [{"host": "127.0.0.1", "port": 7000}]
r = RedisCluster(startup_nodes=startup_nodes, max_connections=32, decode_responses=True)

for i in xrange(1000000):
    d = str(i)
    pipe = r.pipeline(transaction=False)
    pipe.set(d, d)
    pipe.incrby(d, 1)
    pipe.execute()

    pipe = r.pipeline(transaction=False)
    pipe.set("foo-%s" % d, d)
    pipe.incrby("foo-%s" % d, 1)
    pipe.set("bar-%s" % d, d)
    pipe.incrby("bar-%s" % d, 1)
    pipe.set("bazz-%s" % d, d)
    pipe.incrby("bazz-%s" % d, 1)
    pipe.execute()

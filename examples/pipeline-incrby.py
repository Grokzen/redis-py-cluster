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
    pipe.set("foo-{0}".format(d, d))
    pipe.incrby("foo-{0}".format(d, 1))
    pipe.set("bar-{0}".format(d, d))
    pipe.incrby("bar-{0}".format(d, 1))
    pipe.set("bazz-{0}".format(d, d))
    pipe.incrby("bazz-{0}".format(d, 1))
    pipe.execute()

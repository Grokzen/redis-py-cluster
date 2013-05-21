from .rediscluster import RedisCluster

startup_nodes = [{"host": "127.0.0.1", "port": 6381}, {"host": "127.0.0.1", "port": 6382}]
rc = RedisCluster(startup_nodes, 32)

# for i in xrange(0, 50000):
#     rc.get("foo#{0}".format(i))
#     # print(rc.get("foo#{0}".format(i)))
#     # rc.set("foo#{0}".format(i), i)
#     # print(a)
#     #time.sleep(0.05)

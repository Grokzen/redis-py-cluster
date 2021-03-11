from rediscluster import RedisCluster

startup_nodes = [{"host": "127.0.0.1", "port": "7100"}]

# Note: decode_responses must be set to True when used with python3
rc = RedisCluster(startup_nodes=startup_nodes, password='password_is_protected')

rc.set("foo", "bar")

print(rc.get("foo"))

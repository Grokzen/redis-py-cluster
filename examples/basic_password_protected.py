from rediscluster import StrictRedisCluster

startup_nodes = [{"host": "127.0.0.1", "port": "7100"}]

# Note: decode_responses must be set to True when used with python3
rc = StrictRedisCluster(
    startup_nodes=startup_nodes, decode_responses=True, password="password_is_protected"
)

rc.set("foo", "bar")

print(rc.get("foo"))

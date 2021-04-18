from rediscluster import RedisCluster

startup_nodes = [{"host": "127.0.0.1", "port": "7000"}]

# Note: decode_responses must be set to True when used with python3
rc = RedisCluster(startup_nodes=startup_nodes, decode_responses=True)
rc.set("foo", "bar")
print(rc.get("foo"))

# Alternate simple mode of pointing to one startup node
rc = RedisCluster(
    host="127.0.0.1",
    port=7000,
    decode_responses=True,
)
rc.set("foo", "bar")
print(rc.get("foo"))

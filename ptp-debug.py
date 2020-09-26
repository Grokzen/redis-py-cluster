from rediscluster import RedisCluster

startup_nodes = [{"host": "127.0.0.1", "port": "7000"}]

# Note: decode_responses must be set to True when used with python3
rc = RedisCluster(startup_nodes=startup_nodes)
url_client = RedisCluster.from_url('http://127.0.0.1:7000')

__import__('ptpdb').set_trace()

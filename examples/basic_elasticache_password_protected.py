from rediscluster import RedisCluster

rc = RedisCluster(
    host='clustercfg.cfg-endpoint-name.aq25ta.euw1.cache.amazonaws.com',
    port=6379,
    password='password_is_protected',
    skip_full_coverage_check=True,  # Bypass Redis CONFIG call to elasticache 
    decode_responses=True,          # decode_responses must be set to True when used with python3
    ssl=True,                       # in-transit encryption, https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/in-transit-encryption.html 
    ssl_cert_reqs=None              # see https://github.com/andymccurdy/redis-py#ssl-connections
)

rc.set("foo", "bar")

print(rc.get("foo"))

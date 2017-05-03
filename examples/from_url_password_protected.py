from rediscluster import StrictRedisCluster

url="redis://:R1NFTBWTE1@10.127.91.90:6572/0"

rc = StrictRedisCluster.from_url(url, skip_full_coverage_check=True)

rc.set("foo", "bar")

print(rc.get("foo"))

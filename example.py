import sys
import time
import argparse

from rediscluster import RedisCluster


def loop(rc):
    last = False
    while last is False:
        try:
            last = rc.get("__last__")
            last = 0 if not last else int(last)
        except Exception as e:
            print("error {}".format(e))
            time.sleep(1)

    for i in xrange(last, 1000000000):
        try:
            rc.set("foo{}".format(i), i)
            print(rc.get("foo{}".format(i)))
            rc.set("__last__", i)
        except Exception as e:
            print("error {}".format(e))

        time.sleep(0.1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        conflict_handler="resolve",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-h",
        "--host",
        help="host of a cluster member",
        default="127.0.0.1"
    )
    parser.add_argument(
        "-p",
        "--port",
        help="port of a cluster member",
        type=int,
        default=7000
    )
    args = parser.parse_args()

    startup_nodes = [
        {"host": args.host, "port": args.port}
    ]

    rc = RedisCluster(startup_nodes, 32, timeout=0.1)
    loop(rc)

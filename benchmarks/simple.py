# -*- coding: utf-8 -*-

# python std lib
import time
import argparse

# rediscluster imports
from rediscluster.rediscluster import RedisCluster


def loop(rc, reset_last_key=None):
    """
    Regular debug loop that can be used to test how redis behaves during changes in the cluster.
    """
    if reset_last_key:
        rc.set("__last__", 0)

    last = False
    while last is False:
        try:
            last = rc.get("__last__")
            last = 0 if not last else int(last)
            print("starting at foo{0}".format(last))
        except Exception as e:
            print("error {0}".format(e))
            time.sleep(1)

    for i in xrange(last, 1000000000):
        try:
            print("SET foo{0} {1}".format(i, i))
            rc.set("foo{0}".format(i), i)
            got = rc.get("foo{0}".format(i))
            print("GET foo{0} {1}".format(i, got))
            rc.set("__last__", i)
        except Exception as e:
            print("error {0}".format(e))

        time.sleep(0.1)


def timeit(rc, itterations=50000):
    """ Time how long it take to run a number of set/get:s
    """
    t0 = time.time()
    for i in xrange(0, itterations):
        try:
            s = "foo{0}".format(i)
            rc.set(s, i)
            rc.get(s)
        except Exception as e:
            print("error {0}".format(e))

    t1 = time.time() - t0
    print("{}k SET and then GET took: {} seconds... {} itterations per second".format((itterations / 1000), t1, (itterations / t1)))


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
    parser.add_argument(
        "--timeit",
        help="run a mini benchmark to test performance",
        action="store_true"
    )
    parser.add_argument(
        "--resetlastkey",
        help="reset __last__ key",
        action="store_true"
    )
    args = parser.parse_args()

    startup_nodes = [
        {"host": args.host, "port": args.port}
    ]

    rc = RedisCluster(startup_nodes=startup_nodes, max_connections=32, socket_timeout=0.1, decode_responses=True)

    if args.timeit:
        test_itterstions = [
            10000,
            25000,
        ]
        for itterations in test_itterstions:
            timeit(rc, itterations=itterations)
    else:
        loop(rc, reset_last_key=args.resetlastkey)

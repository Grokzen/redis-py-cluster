#!/bin/env python3
"""
Usage:
  redis-cluster-benchmark.py [--host IP] [--port PORT] [--nocluster] [-n <reqursts>] [--timeit] [--pipeline] [--resetlastkey] [-c <concurrent>] [-h] [--version]

Options:
  -c <concurrent>    concurrent client number [default: 1]
  -n <reqursts>      request number [default: 100000]
  --nocluster        If flag is set then StrictRedis will be used instead of cluster lib
  --host IP          Redis server to test against [default: 127.0.0.1]
  --port PORT        Port on redis server [default: 6379]
  --timeit           run a mini benchmark to test performance
  --pipeline         Only usable with --timeit flag. Runs SET/GET inside pipelines.
  --resetlastkey     reset __last__ key
  -h --help          show this help and exit
  -v --version       show version and exit
"""
import time
from multiprocessing import Process

# 3rd party imports
from docopt import docopt
# from redis._compat import xrange


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

    for i in range(last, 1000000000):  # noqa
        try:
            print("SET foo{0} {1}".format(i, i))
            rc.set("foo{0}".format(i), i)
            got = rc.get("foo{0}".format(i))
            print("GET foo{0} {1}".format(i, got))
            rc.set("__last__", i)
        except Exception as e:
            print("error {0}".format(e))

        time.sleep(0.05)


def timeit(rc, num):
    """
    Time how long it take to run a number of set/get:s
    """
    # t0 = time.time()
    for i in range(0, num):  # noqa
        s = "foo{0}".format(i)
        rc.set(s, i)
        rc.get(s)
    # t1 = time.time() - t0
    # print("{0}k SET/GET operations took: {1} seconds... {2} operations per second".format((num / 1000) * 2, t1, (num / t1) * 2))


def timeit_pipeline(rc, num):
    """
    Time how long it takes to run a number of set/get:s inside a cluster pipeline
    """
    # t0 = time.time()
    for i in range(0, num):  # noqa
        s = "foo{0}".format(i)
        p = rc.pipeline()
        p.set(s, i)
        p.get(s)
        p.execute()
    # t1 = time.time() - t0
    # print("{0}k SET/GET operations inside pipelines took: {1} seconds... {2} operations per second".format((num / 1000) * 2, t1, (num / t1) * 2))


if __name__ == "__main__":
    args = docopt(__doc__, version="0.3.1")
    # print(args)
    #startup_nodes = [{"host": '172.16.166.31', "port": 6379}, {"host": '172.16.166.32', "port": 6379}, {"host": '172.16.166.33', "port": 6379}]
    startup_nodes = [{"host": args['--host'], "port": args['--port']}]
    if not args["--nocluster"]:
        from rediscluster import StrictRedisCluster
        rc = StrictRedisCluster(startup_nodes=startup_nodes, max_connections=32, socket_timeout=0.1, decode_responses=True)
        # print(rc)
    else:
        from redis import StrictRedis
        rc = StrictRedis(host=args["--host"], port=args["--port"], socket_timeout=0.1, decode_responses=True)
        # print(rc)
    # create specified number processes
    processes = []
    single_request = int(args["-n"]) // int(args["-c"])
    for j in range(int(args["-c"])):
        if args["--timeit"]:
            if args["--pipeline"]:
                p = Process(target=timeit_pipeline, args=(rc, single_request))
            else:
                p = Process(target=timeit, args=(rc, single_request))
        else:
            p = Process(target=loop, args=(rc, args["--resetlastkey"]))
        processes.append(p)
    t1 = time.time()
    for p in processes:
        p.start()
    for p in processes:
        p.join()
    t2 = time.time() - t1
    print("{0}k SET/GET operations took: {1} seconds... {2} operations per second".format(int(args["-n"]) / 1000 * 2, t2, int(args["-n"]) / t2 * 2))
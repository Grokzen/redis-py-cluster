from rediscluster import RedisCluster
import threading
from time import sleep

"""
This file will show the difference and how to use the READONLY feature to offload READ specific commands
to replica nodes in your cluster. The script will do two runs with 10 sets of commands each in a threaded environment
both with read_from_replica feature turned off and turned on so you can simulate both cases and test out your code
and ensure that it works before opting in to that feature.

The absolute best way to show what node is used inside the pipeline is to add a print(node) here

# pipeline.py
def _send_cluster_command(...):
    ...
    slot = self._determine_slot(*c.args)
    node = self.connection_pool.get_node_by_slot(slot, self.read_from_replicas and c.args[0] in READ_COMMANDS)
    print(node)
    ...

and when you run this test script it will show you what node is used in both cases and the first scenario it should show
only "master" as the node type all commands will be sent to. In the second run with read_from_replica=True it should
be a mix of "master" and "slave".
"""


def test_run(read_from_replica):
    print(f"########\nStarting test run with read_from_replica={read_from_replica}")
    rc = RedisCluster(host="127.0.0.1", port=7000, decode_responses=True, read_from_replicas=read_from_replica)

    print(rc.set("foo1", "bar"))
    print(rc.set("foo2", "bar"))
    print(rc.set("foo3", "bar"))
    print(rc.set("foo4", "bar"))
    print(rc.set("foo5", "bar"))
    print(rc.set("foo6", "bar"))
    print(rc.set("foo7", "bar"))
    print(rc.set("foo8", "bar"))
    print(rc.set("foo9", "bar"))

    print(rc.get("foo1"))
    print(rc.get("foo2"))
    print(rc.get("foo3"))
    print(rc.get("foo4"))
    print(rc.get("foo5"))
    print(rc.get("foo6"))
    print(rc.get("foo7"))
    print(rc.get("foo8"))
    print(rc.get("foo9"))

    def thread_func(num):
        # sleep(0.1)
        pipe = rc.pipeline(read_from_replicas=read_from_replica)
        pipe.set(f"foo{num}", "bar")
        pipe.get(f"foo{num}")
        pipe.get(f"foo{num}")
        pipe.get(f"foo{num}")
        pipe.get(f"foo{num}")
        pipe.get(f"foo{num}")
        pipe.get(f"foo{num}")
        pipe.get(f"foo{num}")
        pipe.get(f"foo{num}")
        print(threading.current_thread().getName(), pipe.execute())

    for i in range(0, 15):
        x = threading.Thread(target=thread_func, args=(i,), name=f"{i}")
        x.start()


test_run(False)
sleep(2)
test_run(True)

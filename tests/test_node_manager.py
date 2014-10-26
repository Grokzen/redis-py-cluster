# -*- coding: utf-8 -*-

# python std lib
from __future__ import with_statement

# rediscluster imports
from tests.conftest import skip_if_server_version_lt
from rediscluster import RedisCluster
from rediscluster.exceptions import RedisClusterException
from rediscluster.nodemanager import NodeManager

# 3rd party imports
import pytest
from redis import StrictRedis
from redis._compat import unicode


pytestmark = skip_if_server_version_lt('2.9.0')


def test_set_node_name(s):
    """
    Test that method sets ["name"] correctly
    """
    n = {"host": "127.0.0.1", "port": 7000}
    s.connection_pool.nodes.set_node_name(n)
    assert "name" in n
    assert n["name"] == "127.0.0.1:7000"


def test_keyslot():
    """
    Test that method will compute correct key in all supported cases
    """
    n = NodeManager([{}])

    assert n.keyslot("foo") == 12182
    assert n.keyslot("{foo}bar") == 12182
    assert n.keyslot("{foo}") == 12182
    assert n.keyslot(1337) == 4314

    # with pytest.raises(AttributeError):


def test_init_slots_cache_not_all_slots(s):
    """
    Test that if not all slots are covered it should raise an exception
    """
    # Create wrapper function so we can inject custom 'CLUSTER SLOTS' command result
    def get_redis_link_wrapper(host, port):
        link = StrictRedis(host="127.0.0.1", port=7000)

        # Missing slot 5460
        bad_slots_resp = [
            [0, 5459, [b'127.0.0.1', 7000], [b'127.0.0.1', 7003]],
            [5461, 10922, [b'127.0.0.1', 7001], [b'127.0.0.1', 7004]],
            [10923, 16383, [b'127.0.0.1', 7002], [b'127.0.0.1', 7005]],
        ]

        # Missing slot 5460
        link.execute_command = lambda *args: bad_slots_resp

        return link

    s.connection_pool.nodes.get_redis_link = get_redis_link_wrapper

    with pytest.raises(RedisClusterException) as ex:
        s.connection_pool.nodes.initialize()

    assert unicode(ex.value).startswith("All slots are not covered after querry all startup_nodes."), True


def test_init_slots_cache(s):
    """
    Test that slots cache can in initialized and all slots are covered
    """
    good_slots_resp = [
        [0, 5460, [b'127.0.0.1', 7000], [b'127.0.0.1', 7003]],
        [5461, 10922, [b'127.0.0.1', 7001], [b'127.0.0.1', 7004]],
        [10923, 16383, [b'127.0.0.1', 7002], [b'127.0.0.1', 7005]],
    ]

    s.execute_command = lambda *args: good_slots_resp
    s.connection_pool.nodes.initialize()
    assert len(s.connection_pool.nodes.slots) == NodeManager.RedisClusterHashSlots
    assert len(s.connection_pool.nodes.nodes) == 6


def test_empty_startup_nodes():
    """
    It should not be possible to create a node manager with no nodes specefied
    """
    with pytest.raises(RedisClusterException):
        NodeManager()

    with pytest.raises(RedisClusterException):
        NodeManager([])


def test_wrong_startup_nodes_type():
    """
    If something other then a list type itteratable is provided it should fail
    """
    with pytest.raises(RedisClusterException):
        NodeManager({})


def test_flush_slots_nodes_cache():
    """
    Slots cache should already be populated.
    """
    n = NodeManager([{"host": "127.0.0.1", "port": 7000}])
    n.initialize()
    assert len(n.slots) == NodeManager.RedisClusterHashSlots
    assert len(n.nodes) == 6

    n.flush_slots_cache()
    n.flush_nodes_cache()

    assert len(n.slots) == 0
    assert len(n.nodes) == 0


def test_init_slots_cache_slots_collision():
    """
    Test that if 2 nodes do not agree on the same slots setup it should raise an error.
    In this test both nodes will say that the first slots block should be bound to different
     servers.
    """
    n = NodeManager(startup_nodes=[
        {"host": "127.0.0.1", "port": 7000},
        {"host": "127.0.0.1", "port": 7001},
    ])

    def monkey_link(host=None, port=None):
        """
        Helper function to return custom slots cache data from different redis nodes
        """
        if port == 7000:
            r = RedisCluster(host="127.0.0.1", port=7000)
            r.result_callbacks["cluster"] = lambda command, res: [
                [0, 5460, [b'127.0.0.1', 7000], [b'127.0.0.1', 7003]],
                [5461, 10922, [b'127.0.0.1', 7001], [b'127.0.0.1', 7004]],
            ]
            return r
        elif port == 7001:
            r = RedisCluster(host="127.0.0.1", port=7000)
            r.result_callbacks["cluster"] = lambda command, res: [
                [0, 5460, [b'127.0.0.1', 7001], [b'127.0.0.1', 7003]],
                [5461, 10922, [b'127.0.0.1', 7000], [b'127.0.0.1', 7004]],
            ]
            return r

    n.get_redis_link = monkey_link

    with pytest.raises(RedisClusterException) as ex:
        n.initialize()
    assert unicode(ex.value).startswith("startup_nodes could not agree on a valid slots cache."), unicode(ex.value)


def test_all_nodes():
    """
    Set a list of nodes and it should be possible to itterate over all
    """
    n = NodeManager(startup_nodes=[{}])
    nodes = [{"1": 1}, {"2": 2}, {"3": 3}]
    n.nodes = nodes

    for i, node in enumerate(n.all_nodes()):
        assert nodes[i] == node


def test_all_nodes_masters():
    """
    Set a list of nodes with random masters/slaves config and it shold be possible
    to itterate over all of them.
    """
    n = NodeManager(startup_nodes=[{}])
    nodes = [
        {"1": 1, "server_type": "master"},
        {"2": 2, "server_type": "slave"},
        {"1": 1, "server_type": "master"},
    ]
    n.nodes = nodes

    for node in n.all_masters():
        assert node in nodes


def test_random_startup_node():
    """
    Hard to test reliable for a random
    """
    s = [{"1": 1}, {"2": 2}, {"3": 3}],
    n = NodeManager(startup_nodes=s)
    random_node = n.random_startup_node()

    for i in range(0, 5):
        assert random_node in s


def test_random_startup_node_ittr():
    """
    Hard to test reliable for a random function
    """
    s = [{"1": 1}, {"2": 2}, {"3": 3}],
    n = NodeManager(startup_nodes=s)

    for i, node in enumerate(n.random_startup_node_ittr()):
        if i == 5:
            break
        assert node in s


def test_determine_pubsub_node():
    """
    Given a set of nodes it should determine the same pubsub node each time.
    """
    n = NodeManager(startup_nodes=[{}])

    n.nodes = [
        {"host": "127.0.0.1", "port": 7001, "server_type": "master"},
        {"host": "127.0.0.1", "port": 7005, "server_type": "master"},
        {"host": "127.0.0.1", "port": 7000, "server_type": "master"},
        {"host": "127.0.0.1", "port": 7002, "server_type": "master"},
    ]

    n.determine_pubsub_node()
    assert n.pubsub_node == {"host": "127.0.0.1", "port": 7005, "server_type": "master", "pubsub": True}

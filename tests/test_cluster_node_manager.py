# -*- coding: utf-8 -*-

# python std lib
from __future__ import with_statement

# rediscluster imports
from tests.conftest import skip_if_server_version_lt
from rediscluster import RedisCluster
from rediscluster.exceptions import RedisClusterException, RedisClusterConfigError
from rediscluster.nodemanager import NodeManager

# 3rd party imports
import pytest
from mock import patch, Mock
from redis import Redis
from redis._compat import unicode
from redis import ConnectionError, ResponseError

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

    assert n.keyslot(125) == n.keyslot(b"125")
    assert n.keyslot(125) == n.keyslot("\x31\x32\x35")
    assert n.keyslot("大奖") == n.keyslot(b"\xe5\xa4\xa7\xe5\xa5\x96")
    assert n.keyslot(u"大奖") == n.keyslot(b"\xe5\xa4\xa7\xe5\xa5\x96")
    assert n.keyslot(1337.1234) == n.keyslot("1337.1234")
    assert n.keyslot(1337) == n.keyslot("1337")
    assert n.keyslot(b"abc") == n.keyslot("abc")
    assert n.keyslot("abc") == n.keyslot(unicode("abc"))
    assert n.keyslot(unicode("abc")) == n.keyslot(b"abc")


def test_init_slots_cache_not_all_slots(s):
    """
    Test that if not all slots are covered it should raise an exception
    """
    # Create wrapper function so we can inject custom 'CLUSTER SLOTS' command result
    def get_redis_link_wrapper(*args, **kwargs):
        link = Redis(host="127.0.0.1", port=7000, decode_responses=True)

        orig_exec_method = link.execute_command

        def patch_execute_command(*args, **kwargs):
            if args == ('cluster', 'slots'):
                # Missing slot 5460
                return [
                    [0, 5459, [b'127.0.0.1', 7000], [b'127.0.0.1', 7003]],
                    [5461, 10922, [b'127.0.0.1', 7001], [b'127.0.0.1', 7004]],
                    [10923, 16383, [b'127.0.0.1', 7002], [b'127.0.0.1', 7005]],
                ]

            return orig_exec_method(*args, **kwargs)

        # Missing slot 5460
        link.execute_command = patch_execute_command

        return link

    s.connection_pool.nodes.get_redis_link = get_redis_link_wrapper

    with pytest.raises(RedisClusterException) as ex:
        s.connection_pool.nodes.initialize()

    assert unicode(ex.value).startswith("All slots are not covered after query all startup_nodes.")


def test_init_slots_cache_not_all_slots_not_require_full_coverage(s):
    """
    Test that if not all slots are covered it should raise an exception
    """
    # Create wrapper function so we can inject custom 'CLUSTER SLOTS' command result
    def get_redis_link_wrapper(*args, **kwargs):
        link = Redis(host="127.0.0.1", port=7000, decode_responses=True)

        orig_exec_method = link.execute_command

        def patch_execute_command(*args, **kwargs):
            if args == ('cluster', 'slots'):
                # Missing slot 5460
                return [
                    [0, 5459, [b'127.0.0.1', 7000], [b'127.0.0.1', 7003]],
                    [5461, 10922, [b'127.0.0.1', 7001], [b'127.0.0.1', 7004]],
                    [10923, 16383, [b'127.0.0.1', 7002], [b'127.0.0.1', 7005]],
                ]
            elif args == ('CONFIG GET', 'cluster-require-full-coverage'):
                return {'cluster-require-full-coverage': 'no'}
            else:
                return orig_exec_method(*args, **kwargs)

        # Missing slot 5460
        link.execute_command = patch_execute_command

        return link

    s.connection_pool.nodes.get_redis_link = get_redis_link_wrapper

    s.connection_pool.nodes.initialize()

    assert 5460 not in s.connection_pool.nodes.slots


def test_init_slots_cache(s):
    """
    Test that slots cache can in initialized and all slots are covered
    """
    good_slots_resp = [
        [0, 5460, [b'127.0.0.1', 7000], [b'127.0.0.2', 7003]],
        [5461, 10922, [b'127.0.0.1', 7001], [b'127.0.0.2', 7004]],
        [10923, 16383, [b'127.0.0.1', 7002], [b'127.0.0.2', 7005]],
    ]

    with patch.object(Redis, 'execute_command') as execute_command_mock:
        def patch_execute_command(*args, **kwargs):
            if args == ('CONFIG GET', 'cluster-require-full-coverage'):
                return {'cluster-require-full-coverage': 'yes'}
            else:
                return good_slots_resp

        execute_command_mock.side_effect = patch_execute_command

        s.connection_pool.nodes.initialize()
        assert len(s.connection_pool.nodes.slots) == NodeManager.RedisClusterHashSlots
        for slot_info in good_slots_resp:
            all_hosts = [b'127.0.0.1', b'127.0.0.2']
            all_ports = [7000, 7001, 7002, 7003, 7004, 7005]
            slot_start = slot_info[0]
            slot_end = slot_info[1]
            for i in range(slot_start, slot_end + 1):
                assert len(s.connection_pool.nodes.slots[i]) == len(slot_info[2:])
                assert s.connection_pool.nodes.slots[i][0]['host'] in all_hosts
                assert s.connection_pool.nodes.slots[i][1]['host'] in all_hosts
                assert s.connection_pool.nodes.slots[i][0]['port'] in all_ports
                assert s.connection_pool.nodes.slots[i][1]['port'] in all_ports

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

    def monkey_link(host=None, port=None, *args, **kwargs):
        """
        Helper function to return custom slots cache data from different redis nodes
        """
        if port == 7000:
            result = [[0, 5460, [b'127.0.0.1', 7000], [b'127.0.0.1', 7003]],
                      [5461, 10922, [b'127.0.0.1', 7001], [b'127.0.0.1', 7004]]]

        elif port == 7001:
            result = [[0, 5460, [b'127.0.0.1', 7001], [b'127.0.0.1', 7003]],
                      [5461, 10922, [b'127.0.0.1', 7000], [b'127.0.0.1', 7004]]]

        else:
            result = []

        r = RedisCluster(host=host, port=port, decode_responses=True)
        orig_execute_command = r.execute_command

        def execute_command(*args, **kwargs):
            if args == ("cluster", "slots"):
                return result
            elif args == ('CONFIG GET', 'cluster-require-full-coverage'):
                return {'cluster-require-full-coverage': 'yes'}
            else:
                return orig_execute_command(*args, **kwargs)

        r.execute_command = execute_command
        return r

    n.get_redis_link = monkey_link
    with pytest.raises(RedisClusterException) as ex:
        n.initialize()
    assert unicode(ex.value).startswith("startup_nodes could not agree on a valid slots cache."), unicode(ex.value)


def test_all_nodes():
    """
    Set a list of nodes and it should be possible to itterate over all
    """
    n = NodeManager(startup_nodes=[{"host": "127.0.0.1", "port": 7000}])
    n.initialize()

    nodes = [node for node in n.nodes.values()]

    for i, node in enumerate(n.all_nodes()):
        assert node in nodes


def test_all_nodes_masters():
    """
    Set a list of nodes with random masters/slaves config and it shold be possible
    to itterate over all of them.
    """
    n = NodeManager(startup_nodes=[{"host": "127.0.0.1", "port": 7000}, {"host": "127.0.0.1", "port": 7001}])
    n.initialize()

    nodes = [node for node in n.nodes.values() if node['server_type'] == 'master']

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


def test_cluster_slots_error():
    """
    Check that exception is raised if initialize can't execute
    'CLUSTER SLOTS' command.
    """
    with patch.object(Redis, 'execute_command') as execute_command_mock:
        execute_command_mock.side_effect = Exception("foobar")

        with pytest.raises(RedisClusterException):
            n = NodeManager(startup_nodes=[{"host": "127.0.0.1", "port": 7000}])
            n.initialize()

        try:
            n = NodeManager(startup_nodes=[{"host": "127.0.0.1", "port": 7000}])
            n.initialize()
        except RedisClusterException as e:
            assert "ERROR sending 'cluster slots' command" in e.args[0]



def test_cluster_slots_error_expected_responseerror():
    """
    Check that exception is not raised if initialize can't execute
    'CLUSTER SLOTS' command but can hit other nodes.
    """
    with patch.object(Redis, 'execute_command') as execute_command_mock:
        execute_command_mock.side_effect = ResponseError("MASTERDOWN")

        with pytest.raises(RedisClusterException):
            n = NodeManager(startup_nodes=[{"host": "127.0.0.1", "port": 7000}])
            n.initialize()

        try:
            n = NodeManager(startup_nodes=[{"host": "127.0.0.1", "port": 7000}])
            n.initialize()
        except RedisClusterException as e:
            assert "Redis Cluster cannot be connected" in e.args[0]


def test_set_node():
    """
    Test to update data in a slot.
    """
    expected = {
        "host": "127.0.0.1",
        "name": "127.0.0.1:7000",
        "port": 7000,
        "server_type": "master",
    }

    n = NodeManager(startup_nodes=[{}])
    assert len(n.slots) == 0, "no slots should exist"
    res = n.set_node(host="127.0.0.1", port=7000, server_type="master")
    assert res == expected
    assert n.nodes == {expected['name']: expected}


def test_reset():
    """
    Test that reset method resets variables back to correct default values.
    """
    n = NodeManager(startup_nodes=[{}])
    n.initialize = Mock()
    n.reset()
    assert n.initialize.call_count == 1


def test_cluster_one_instance():
    """
    If the cluster exists of only 1 node then there is some hacks that must
    be validated they work.
    """
    with patch.object(Redis, 'execute_command') as mock_execute_command:
        return_data = [[0, 16383, ['', 7006]]]

        def patch_execute_command(*args, **kwargs):
            if args == ('CONFIG GET', 'cluster-require-full-coverage'):
                return {'cluster-require-full-coverage': 'yes'}
            else:
                return return_data

        # mock_execute_command.return_value = return_data
        mock_execute_command.side_effect = patch_execute_command

        n = NodeManager(startup_nodes=[{"host": "127.0.0.1", "port": 7006}])
        n.initialize()

        assert n.nodes == {"127.0.0.1:7006": {
            'host': '127.0.0.1',
            'name': '127.0.0.1:7006',
            'port': 7006,
            'server_type': 'master',
        }}

        assert len(n.slots) == 16384
        for i in range(0, 16384):
            assert n.slots[i] == [{
                "host": "127.0.0.1",
                "name": "127.0.0.1:7006",
                "port": 7006,
                "server_type": "master",
            }]


def test_initialize_follow_cluster():
    n = NodeManager(nodemanager_follow_cluster=True, startup_nodes=[{'host': '127.0.0.1', 'port': 7000}])
    n.orig_startup_nodes = None
    n.initialize()


def test_init_with_down_node():
    """
    If I can't connect to one of the nodes, everything should still work.
    But if I can't connect to any of the nodes, exception should be thrown.
    """
    def get_redis_link(host, port, decode_responses=False):
        if port == 7000:
            raise ConnectionError('mock connection error for 7000')
        return Redis(host=host, port=port, decode_responses=decode_responses)

    with patch.object(NodeManager, 'get_redis_link', side_effect=get_redis_link):
        n = NodeManager(startup_nodes=[{"host": "127.0.0.1", "port": 7000}])
        with pytest.raises(RedisClusterException) as e:
            n.initialize()
        assert 'Redis Cluster cannot be connected' in unicode(e.value)


def test_host_port_remap():
    """
    """
    # Test that providing nothing to NodeManager will not cause error
    n = NodeManager(
        startup_nodes=[{"host": "127.0.0.1", "port": 7000}],
        host_port_remap=None,
    )
    # Test that providing wrong root level object type will raise config exception. List is expected
    with pytest.raises(RedisClusterConfigError) as excp:
        n = NodeManager(
            startup_nodes=[{"host": "127.0.0.1", "port": 7000}],
            host_port_remap={},
        )
    # An empty host_port_remap  list should not raise an error
    n = NodeManager(
        startup_nodes=[{"host": "127.0.0.1", "port": 7000}],
        host_port_remap=[],
    )
    # A wrong object type inside host_port_remap list shold raise error
    with pytest.raises(RedisClusterConfigError) as excp:
        n = NodeManager(
            startup_nodes=[{"host": "127.0.0.1", "port": 7000}],
            host_port_remap=[None],
        )
    # The correct object typ inside list but empty should not give an error
    n = NodeManager(
        startup_nodes=[{"host": "127.0.0.1", "port": 7000}],
        host_port_remap=[{}, {}],
    )
    # If we only have either or from_host or to_host set we should get an error
    with pytest.raises(RedisClusterConfigError) as excp:
        n = NodeManager(
            startup_nodes=[{"host": "127.0.0.1", "port": 7000}],
            host_port_remap=[{'from_host': ''}],
        )
    with pytest.raises(RedisClusterConfigError) as excp:
        n = NodeManager(
            startup_nodes=[{"host": "127.0.0.1", "port": 7000}],
            host_port_remap=[{'to_host': ''}],
        )
    # If we only have either or from_port or to_port set we should get an error
    with pytest.raises(RedisClusterConfigError) as excp:
        n = NodeManager(
            startup_nodes=[{"host": "127.0.0.1", "port": 7000}],
            host_port_remap=[{'from_port': ''}],
        )
    with pytest.raises(RedisClusterConfigError) as excp:
        n = NodeManager(
            startup_nodes=[{"host": "127.0.0.1", "port": 7000}],
            host_port_remap=[{'to_port': ''}],
        )
    # Invalid keys in the rules should also raise exception
    with pytest.raises(RedisClusterConfigError) as excp:
        n = NodeManager(
            startup_nodes=[{"host": "127.0.0.1", "port": 7000}],
            host_port_remap=[{'invalid_key': ''}],
        )

    # Invalid ips in the rules should raise exception
    with pytest.raises(RedisClusterConfigError) as excp:
        n = NodeManager(
            startup_nodes=[{"host": "127.0.0.1", "port": 7000}],
            host_port_remap=[{'from_host': '127.2.x.w', 'to_host': '127.0.0.1'}],
        )
    # Incomplete ips in the rules should raise exception
    with pytest.raises(RedisClusterConfigError) as excp:
        n = NodeManager(
            startup_nodes=[{"host": "127.0.0.1", "port": 7000}],
            host_port_remap=[{'from_host': '127.2', 'to_host': '127.0.0.1'}],
        )

    # Creating a valid config with multiple entries
    n = NodeManager(
        startup_nodes=[{"host": "127.0.0.1", "port": 7000}],
        host_port_remap=[
            {'from_host': '127.0.0.1', 'to_host': '127.0.0.1', 'from_port': 7000, 'to_port': 70001},
            {'from_host': '172.1.0.1', 'to_host': '127.0.0.1', 'from_port': 7000, 'to_port': 70001},
        ],
    )

    # If no host_port_remap is set then a node obj should not be modified in any way when remapping it
    n = NodeManager(
        host_port_remap=None,
        startup_nodes=[{"host": "127.0.0.1", "port": 7000}]
    )
    initial_node_obj = ['127.0.0.1', 7000, 'xyz']
    unmodified_remapped_obj = n.remap_internal_node_object(initial_node_obj)
    assert unmodified_remapped_obj == initial_node_obj

    # Test that modifying both host and port works
    n = NodeManager(
        host_port_remap=[{'from_host': '127.1.1.1', 'to_host': '128.0.0.1', 'from_port': 7000, 'to_port': 7001},
                         {'from_host': '127.2.2.2', 'to_host': '128.0.0.1', 'from_port': 7000, 'to_port': 7005}],
        startup_nodes=[{"host": "128.0.0.1", "port": 7000}]
    )
    initial_node_obj = ['127.1.1.1', 7000, 'xyz']
    remapped_obj = n.remap_internal_node_object(initial_node_obj)
    assert remapped_obj[0] == '128.0.0.1'
    assert remapped_obj[1] == 7001

    # Validate that ports are NOT remapped in isolation if hosts are also present
    n = NodeManager(
        host_port_remap=[{'from_host': '127.2.2.2', 'to_host': '127.0.0.1', 'from_port': 7000, 'to_port': 7001},
                         {'from_host': '127.3.3.3', 'to_host': '127.0.0.1', 'from_port': 7000, 'to_port': 7005}],
        startup_nodes=[{"host": "127.0.0.1", "port": 7000}]
    )
    initial_node_obj = ['127.0.0.1', 7000, 'xyz']
    remapped_obj = n.remap_internal_node_object(initial_node_obj)
    assert remapped_obj[0] == '127.0.0.1'
    assert remapped_obj[1] == 7000

    # Validate that first applicable rule is applied
    n = NodeManager(
        host_port_remap=[{'from_host': '127.2.2.2', 'to_host': '127.0.0.1', 'from_port': 7000, 'to_port': 7001},
                         {'from_host': '127.3.3.3', 'to_host': '127.0.0.1', 'from_port': 7000, 'to_port': 7005},
                         {'from_host': '127.2.2.2', 'to_host': '127.0.0.1', 'from_port': 7000, 'to_port': 7006}],
        startup_nodes=[{"host": "127.0.0.1", "port": 7000}]
    )
    initial_node_obj = ['127.2.2.2', 7000, 'xyz']
    remapped_obj = n.remap_internal_node_object(initial_node_obj)
    assert remapped_obj[0] == '127.0.0.1'
    assert remapped_obj[1] == 7001

    # Validate just port mapping works
    n = NodeManager(
        host_port_remap=[{'from_port': 7000, 'to_port': 7001},
                         {'from_port': 7002, 'to_port': 7005}],
        startup_nodes=[{"host": "127.0.0.1", "port": 7000}]
    )
    initial_node_obj = ['127.0.0.1', 7000, 'xyz']
    remapped_obj = n.remap_internal_node_object(initial_node_obj)
    assert remapped_obj[0] == '127.0.0.1'
    assert remapped_obj[1] == 7001

    # Validate just host mapping works
    n = NodeManager(
        host_port_remap=[{'from_host': '127.2.2.2', 'to_host': '127.0.0.1'},
                         {'from_host': '127.3.3.3', 'to_host': '127.0.0.2'}],
        startup_nodes=[{"host": "127.0.0.1", "port": 7000}]
    )
    initial_node_obj = ['127.3.3.3', 7000, 'xyz']
    remapped_obj = n.remap_internal_node_object(initial_node_obj)
    assert remapped_obj[0] == '127.0.0.2'
    assert remapped_obj[1] == 7000

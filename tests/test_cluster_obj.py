# -*- coding: utf-8 -*-

# python std lib
from __future__ import with_statement
import re

# rediscluster imports
from rediscluster.connection import ClusterConnectionPool
from rediscluster.nodemanager import NodeManager
from rediscluster import RedisCluster
from rediscluster.exceptions import RedisClusterException
from tests.conftest import _get_client, skip_if_server_version_lt

# 3rd party imports
from redis import StrictRedis
from redis.exceptions import ConnectionError
from redis._compat import unicode
import pytest


pytestmark = skip_if_server_version_lt('2.9.0')


def test_representation(r):
    assert re.search('^RedisCluster<[0-9\.\:\,]+>$', str(r))


def test_blocked_strict_redis_args():
    """
    Some arguments should explicitly be blocked because they will not work in a cluster setup
    """
    params = {'startup_nodes': [{'host': '127.0.0.1', 'port': 7000}]}
    c = RedisCluster(**params)
    assert c.connection_pool.connection_kwargs["socket_timeout"] == ClusterConnectionPool.RedisClusterDefaultTimeout

    with pytest.raises(RedisClusterException) as ex:
        _get_client(db=1)
    assert unicode(ex.value).startswith("Argument 'db' is not possible to use in cluster mode")
    # TODO: Write tests for host & port arg


def test_host_port_startup_node():
    """
    Test that it is possible to use host & port arguments as startup node args
    """
    h = "192.168.0.1"
    p = 7000
    c = RedisCluster(host=h, port=p, init_slot_cache=False)
    assert {"host": h, "port": p} in c.connection_pool.nodes.startup_nodes


def test_set_node_name(s):
    """
    Test that method sets ["name"] correctly
    """
    n = {"host": "127.0.0.1", "port": 7000}
    s.connection_pool.nodes.set_node_name(n)
    assert "name" in n
    assert n["name"] == "127.0.0.1:7000"


def test_keyslot(s):
    """
    Test that method will compute correct key in all supported cases
    """
    assert s.connection_pool.nodes.RedisClusterHashSlots == 16384
    h = s.connection_pool.nodes.keyslot("foo")
    assert h == 12182

    h = s.connection_pool.nodes.keyslot("{foo}bar")
    assert h == 12182

    h = s.connection_pool.nodes.keyslot("{foo}")
    assert h == 12182

    with pytest.raises(AttributeError):
        h = s.connection_pool.nodes.keyslot(1337)


@pytest.mark.xfail(reason="TODO: needs fixing")
def test_init_slots_cache(s):
    """
    Test that slots cache can in initialized and all slots are covered
    """
    good_slots_resp = [[0, 5460, [b'127.0.0.1', 7000], [b'127.0.0.1', 7003]],
                       [5461, 10922, [b'127.0.0.1', 7001], [b'127.0.0.1', 7004]],
                       [10923, 16383, [b'127.0.0.1', 7002], [b'127.0.0.1', 7005]]]

    s.execute_command = lambda *args: good_slots_resp
    s.connection_pool.nodes.initialize()
    assert len(s.connection_pool.nodes.slots) == NodeManager.RedisClusterHashSlots
    assert len(s.connection_pool.nodes.nodes) == 6


@pytest.mark.xfail(reason="TODO: needs fixing")
def test_init_slots_cache_not_all_slots(s):
    """
    Test that if not all slots are covered it should raise an exception
    """
    # Create wrapper function so we can inject custom 'CLUSTER SLOTS' command result
    def get_redis_link_wrapper(host, port):
        link = StrictRedis(host="127.0.0.1", port=7000)

        # Missing slot 5460
        bad_slots_resp = [[0, 5459, [b'127.0.0.1', 7000], [b'127.0.0.1', 7003]],
                          [5461, 10922, [b'127.0.0.1', 7001], [b'127.0.0.1', 7004]],
                          [10923, 16383, [b'127.0.0.1', 7002], [b'127.0.0.1', 7005]]]

        # Missing slot 5460
        link.execute_command = lambda *args: bad_slots_resp

        return link

    s.connection_pool.nodes.get_redis_link = get_redis_link_wrapper

    with pytest.raises(RedisClusterException) as ex:
        s.connection_pool.nodes.initialize()

    assert unicode(ex.value).startswith("All slots are not covered after querry all startup_nodes."), True


@pytest.mark.xfail(reason="TODO: needs fixing")
def test_init_slots_cache_slots_collision():
    """
    Test that if 2 nodes do not agree on the same slots setup it should raise an error.
    In this test both nodes will say that the first slots block should be bound to different
     servers.
    """
    s = _get_client(init_slot_cache=False, startup_nodes=[{"host": "127.0.0.1", "port": "7000"}, {"host": "127.0.0.1", "port": "7001"}])

    # TODO: Broken, use other get by node command
    old_get_link_from_node = s.get_redis_link_from_node

    node_1 = old_get_link_from_node({"host": "127.0.0.1", "port": "7000"})
    node_2 = old_get_link_from_node({"host": "127.0.0.1", "port": "7001"})

    node_1_slots = [[0, 5460, [b'127.0.0.1', 7000], [b'127.0.0.1', 7003]],
                    [5461, 10922, [b'127.0.0.1', 7001], [b'127.0.0.1', 7004]]]

    node_2_slots = [[0, 5460, [b'127.0.0.1', 7001], [b'127.0.0.1', 7003]],
                    [5461, 10922, [b'127.0.0.1', 7000], [b'127.0.0.1', 7004]]]

    node_1.execute_command = lambda *args: node_1_slots
    node_2.execute_command = lambda *args: node_2_slots

    def new_get_link_from_node(host=None, port=None):
        # TODO: This seem like a bug that we have to exclude 'name' in first use but not in second use.
        # if node == {"host": "127.0.0.1", "port": "7000"}:  # , 'name': '127.0.0.1:7000'}:
        if host == "127.0.0.1" and port == "7000":
            return node_1
        # elif node == {"host": "127.0.0.1", "port": "7001", 'name': '127.0.0.1:7001'}:
        elif host == "127.0.0.1" and port == "7001":
            return node_2
        else:
            raise Exception("Foo")

    # s.get_redis_link_from_node = new_get_link_from_node
    s.connection_pool.nodes.get_redis_link = new_get_link_from_node

    with pytest.raises(RedisClusterException) as ex:
        s.connection_pool.nodes.initialize()

    assert unicode(ex.value).startswith("startup_nodes could not agree on a valid slots cache."), unicode(ex.value)


def test_empty_startup_nodes(s):
    """
    Test that exception is raised when empty providing empty startup_nodes
    """
    with pytest.raises(RedisClusterException) as ex:
        _get_client(init_slot_cache=False, startup_nodes=[])

    assert unicode(ex.value).startswith("No startup nodes provided"), unicode(ex.value)


@pytest.mark.xfail(reason="TODO: needs fixing")
def test_flush_slots_cache(r):
    """
    Slots cache should already be populated.
    """
    assert len(r.connection_pool.nodes.slots) == r.connection_pool.nodes.RedisClusterHashSlots
    r.flush_slots_cache()
    assert len(r.connection_pool.nodes.slots) == 0


@pytest.mark.xfail(reason="TODO: needs fixing")
def test_close_existing_connection():
    """
    We cannot use 'r' or 's' object because they have called flushdb() and connected to
    any number of redis servers. Creating it manually will not do that.

    close_existing_connection() is called inside get_connection_by_slot() and will limit
    the number of connections stored to 1
    """
    params = {'startup_nodes': [{"host": "127.0.0.1", "port": "7000"}],
              'max_connections': 1,
              'socket_timeout': 0.1,
              'decode_responses': False}

    client = RedisCluster(**params)
    assert len(client.connections) == 0
    c1 = client.get_connection_by_slot(0)
    assert len(client.connections) == 1
    c2 = client.get_connection_by_slot(16000)
    assert len(client.connections) == 1
    assert c1 != c2  # This shold not return different connections


@pytest.mark.xfail(reason="TODO: needs fixing")
def test_get_connection_by_key(r):
    """
    This test assumes that when hashing key 'foo' will be sent to server with port 7002
    """
    connection = r.get_connection_by_key("foo")
    assert connection.connection_pool.connection_kwargs["port"] == 7002

    with pytest.raises(RedisClusterException) as ex:
        r.get_connection_by_key(None)

    assert unicode(ex.value).startswith("No way to dispatch this command to Redis Cluster."), True


def test_blocked_commands(r):
    """
    These commands should be blocked and raise RedisClusterException
    """
    # TODO: This list should be gathered from RedisCluster class when it is moved
    blocked_commands = [
        "CLIENT SETNAME", "SENTINEL GET-MASTER-ADDR-BY-NAME", 'SENTINEL MASTER', 'SENTINEL MASTERS',
        'SENTINEL MONITOR', 'SENTINEL REMOVE', 'SENTINEL SENTINELS', 'SENTINEL SET',
        'SENTINEL SLAVES', 'SHUTDOWN', 'SLAVEOF', 'EVALSHA', 'SCRIPT EXISTS', 'SCRIPT KILL',
        'SCRIPT LOAD', 'MOVE', 'BITOP', 'SCAN',
    ]

    for command in blocked_commands:
        try:
            r.execute_command(command)
        except RedisClusterException:
            pass
        else:
            raise AssertionError("'RedisClusterException' not raised for method : {}".format(command))


@pytest.mark.xfail(reason="TODO: needs fixing")
def test_connection_error(r):
    execute_command_via_connection_original = r.execute_command_via_connection
    test = self
    test.execute_command_calls = []

    def execute_command_via_connection(r, *argv, **kwargs):
        # the first time this is called, simulate an ASK exception.
        # after that behave normally.
        # capture all the requests and responses.
        if not test.execute_command_calls:
            e = ConnectionError('FAKE: could not connect')
            test.execute_command_calls.append({'exception': e})
            raise e
        try:
            result = execute_command_via_connection_original(r, *argv, **kwargs)
            test.execute_command_calls.append({'argv': argv, 'kwargs': kwargs, 'result': result})
            return result
        except Exception as e:
            test.execute_command_calls.append({'argv': argv, 'kwargs': kwargs, 'exception': e})
            raise e

    try:
        r.execute_command_via_connection = execute_command_via_connection
        r.set('foo', 'bar')
        # print test.execute_command_calls
        assert re.match('FAKE', str(test.execute_command_calls[0]['exception'])) is not None
        # we might actually try a random node that is the correct one.
        # in which case we won't get a moved exception.
        if len(test.execute_command_calls) == 3:
            assert re.match('MOVED', str(test.execute_command_calls[1]['exception'])) is not None
            assert test.execute_command_calls[2]['argv'], ['SET', 'foo', 'bar']
            assert test.execute_command_calls[2]['result'], True
        else:
            assert test.execute_command_calls[1]['argv'], ['SET', 'foo', 'bar']
            assert test.execute_command_calls[1]['result'], True
    finally:
        r.execute_command_via_connection = execute_command_via_connection_original
    assert r.get('foo'), 'bar'

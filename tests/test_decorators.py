# -*- coding: utf-8 -*-

# rediscluster imports
from rediscluster import RedisCluster
from rediscluster.exceptions import RedisClusterException
from rediscluster.decorators import (send_to_random_node,
                                     block_command,
                                     get_connection_from_node_obj,
                                     send_to_all_masters_merge_list)
from tests.conftest import skip_if_server_version_lt, _get_client

# 3rd party imports
import pytest
from redis import StrictRedis
from testfixtures import compare


pytestmark = skip_if_server_version_lt('2.9.0')


class A(object):
    """
    Helper class to test decorator functions by providing a class
    similar to StrictRedis
    """

    def __init__(self):
        self.a_called = False

    def foo(self, *args, **kwargs):
        self.a_called = True
        return self


class B(object):
    """
    Helper class to test decorator functions by providing a class
    similar to Rediscluster
    """

    def __init__(self):
        self.b_called = False

    def get_random_connection(self, *args, **kwargs):
        self.b_called = True
        return A()


@pytest.mark.xfail(reason="not used any longer")
def test_send_to_random_node():
    """
    Test that when using 'send_to_random_node' decorator that
    'get_random_connection()' is called on RedisCluster (Class B) class and that
    when calling the wrapped method it calls the method in StrictRedis (Class A)
    """
    B.test_random_node = send_to_random_node(A.foo)

    b = B()
    a = b.test_random_node()

    assert b.b_called
    assert a.a_called


@pytest.mark.xfail(reason="not used any longer")
def test_block_command():
    """
    Test that when wrapping a method with 'block_command' a exception
    should be raised when the method is called
    """
    B.test_block_command = block_command(A.foo)

    b = B()
    with pytest.raises(RedisClusterException) as ex:
        b.test_block_command()
    compare(str(ex.value),
            "ERROR: Calling function {} is blocked when running redis in cluster mode...".format("foo"))


@pytest.mark.xfail(reason="not used any longer")
def test_get_connection_from_node_obj(s):
    """
    Test that a new connection is created from a node dict and is returned to clients.

    This test assumes that one server is running at 127.0.0.1:7000
    """
    # Verify that there is no existing connections in the pool
    compare(len(s.connections), 0, prefix="There should be no connections in the pool")

    node = {"host": "127.0.0.1", "port": 7000}
    conn = get_connection_from_node_obj(s, node)
    assert isinstance(conn, StrictRedis), "{}".format(conn._class__)

    # It is expected that get_connection_from_node_obj should set "name" on the node object
    assert "name" in node
    assert node["name"] == "127.0.0.1:7000"

    # Verify that there is now one connection in the pool
    assert len(s.connections) == 1, "There should only be 1 connection in the pool"

    # Test to open a connection to a node that should not be open
    node = {"host": "127.0.0.1", "port": 8000}
    with pytest.raises(RedisClusterException) as ex:
        conn = get_connection_from_node_obj(s, node)

    v = str(ex.value)
    assert v.startswith("unable to open new connection to node")
    assert "'host': '127.0.0.1" in v
    assert "'port': 8000" in v
    assert "'name': '127.0.0.1:8000" in v

    # Verify that no additional connections was opened
    assert len(s.connections) == 1, "There should only be 1 connection in the pool"


@pytest.mark.xfail(reason="not used any longer")
def test_send_to_all_nodes_merge_list():
    """
    Test that when sending to all nodes the the result from that operation
    is joined into a list and returned to caller.
    """
    # TODO
    pass


@pytest.mark.xfail(reason="not used any longer")
def test_send_to_all_nodes():
    """
    Test that when sending to all nodes that the result from that operation
    is joined into a dict and returned to caller.
    """
    pass


@pytest.mark.xfail(reason="not used any longer")
def test_send_to_all_masters_merge_list(r):
    """
    Test to send command to only master nodes and merge result into a dict
    and returned to caller.
    """
    # empty the cluster before continue
    r.flushall()

    RedisCluster.test_send_to_all_masters_merge_list = send_to_all_masters_merge_list(StrictRedis.keys)
    r = _get_client()
    r.set("foo", 1)
    r.set("bar", 2)
    s = r.test_send_to_all_masters_merge_list()
    assert isinstance(s, list), "returned data should be of type list : {}".format(s.__class__)

    # Check that data returned from cluster is correct
    assert b"foo" in s
    assert b"bar" in s


@pytest.mark.xfail(reason="not used any longer")
def test_send_to_all_master_nodes():
    """
    """
    # TODO
    pass


@pytest.mark.xfail(reason="not used any longer")
def test_send_eval_to_connection():
    """
    """
    # TODO
    pass


@pytest.mark.xfail(reason="not used any longer")
def test_send_connection_by_key():
    """
    """
    # TODO
    pass

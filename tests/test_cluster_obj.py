# -*- coding: utf-8 -*-

# python std lib
from __future__ import with_statement
import re

# rediscluster imports
from rediscluster.connection import ClusterConnectionPool
from rediscluster import RedisCluster
from rediscluster.exceptions import RedisClusterException
from tests.conftest import _get_client, skip_if_server_version_lt

# 3rd party imports
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


def test_host_port_startup_node():
    """
    Test that it is possible to use host & port arguments as startup node args
    """
    h = "192.168.0.1"
    p = 7000
    c = RedisCluster(host=h, port=p, init_slot_cache=False)
    assert {"host": h, "port": p} in c.connection_pool.nodes.startup_nodes


def test_empty_startup_nodes(s):
    """
    Test that exception is raised when empty providing empty startup_nodes
    """
    with pytest.raises(RedisClusterException) as ex:
        _get_client(init_slot_cache=False, startup_nodes=[])

    assert unicode(ex.value).startswith("No startup nodes provided"), unicode(ex.value)


def test_blocked_commands(r):
    """
    These commands should be blocked and raise RedisClusterException
    """
    # TODO: This list should be gathered from RedisCluster class when it is moved
    blocked_commands = [
        "CLIENT SETNAME", "SENTINEL GET-MASTER-ADDR-BY-NAME", 'SENTINEL MASTER', 'SENTINEL MASTERS',
        'SENTINEL MONITOR', 'SENTINEL REMOVE', 'SENTINEL SENTINELS', 'SENTINEL SET',
        'SENTINEL SLAVES', 'SHUTDOWN', 'SLAVEOF', 'EVALSHA', 'SCRIPT EXISTS', 'SCRIPT KILL',
        'SCRIPT LOAD', 'MOVE', 'BITOP',
    ]

    for command in blocked_commands:
        try:
            r.execute_command(command)
        except RedisClusterException:
            pass
        else:
            raise AssertionError("'RedisClusterException' not raised for method : {}".format(command))


def test_blocked_transaction(r):
    """
    Method transaction is blocked/NYI and should raise exception on use
    """
    with pytest.raises(RedisClusterException) as ex:
        r.transaction(None)
    assert unicode(ex.value).startswith("method RedisCluster.transaction() is not implemented"), unicode(ex.value)

# -*- coding: utf-8 -*-

# python std lib
import os
import sys
import json

# rediscluster imports
from rediscluster import RedisCluster

# 3rd party imports
import pytest
from distutils.version import StrictVersion
from mock import Mock
from redis import Redis
from redis.exceptions import ResponseError

# put our path in front so we can be sure we are testing locally not against the global package
basepath = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(1, basepath)

# redis 6 release candidates report a version number of 5.9.x. Use this
# constant for skip_if decorators as a placeholder until 6.0.0 is officially
# released
REDIS_6_VERSION = '5.9.0'

_REDIS_VERSIONS = {}
REDIS_INFO = {}

default_redis_url = "redis://127.0.0.1:7001"


def pytest_addoption(parser):
    parser.addoption(
        '--redis-url',
        default=default_redis_url,
        action="store",
        help="Redis connection string, defaults to `%(default)s`",
    )


def _get_info(redis_url):
    """
    customized for a cluster environment
    """
    client = RedisCluster.from_url(redis_url)
    info = client.info()
    for node_name, node_data in info.items():
        if '7001' in node_name:
            info = node_data
    client.connection_pool.disconnect()
    return info


def pytest_sessionstart(session):
    redis_url = session.config.getoption("--redis-url")
    info = _get_info(redis_url)
    version = info["redis_version"]
    arch_bits = info["arch_bits"]
    REDIS_INFO["version"] = version
    REDIS_INFO["arch_bits"] = arch_bits


def get_version(**kwargs):
    params = {'host': 'localhost', 'port': 7000}
    params.update(kwargs)
    key = '%s:%s' % (params['host'], params['port'])
    if key not in _REDIS_VERSIONS:
        client = RedisCluster(**params)

        # INFO command returns for all nodes but we only care for port 7000
        client_info = client.info()
        for client_id, client_data in client_info.items():
            if '7000' in key:
                _REDIS_VERSIONS[key] = client_data['redis_version']

        client.connection_pool.disconnect()
    return _REDIS_VERSIONS[key]


def _get_client(cls, request=None, **kwargs):
    params = {'host': 'localhost', 'port': 7000}
    params.update(kwargs)
    client = cls(**params)
    client.flushdb()
    if request:
        def teardown():
            client.flushdb()
            client.connection_pool.disconnect()
        request.addfinalizer(teardown)
    return client


def _init_client(request, cls=None, **kwargs):
    """
    """
    client = _get_client(cls=cls, **kwargs)
    client.flushdb()
    if request:
        def teardown():
            client.flushdb()
            client.connection_pool.disconnect()
        request.addfinalizer(teardown)
    return client


def _init_mgt_client(request, cls=None, **kwargs):
    """
    """
    client = _get_client(cls=cls, **kwargs)
    if request:
        def teardown():
            client.connection_pool.disconnect()
        request.addfinalizer(teardown)
    return client


def skip_for_no_cluster_impl():
    return pytest.mark.skipif(True, reason="Cluster has no or working implementation for this test")


def skip_if_not_password_protected_nodes():
    """
    """
    return pytest.mark.skipif('TEST_PASSWORD_PROTECTED' not in os.environ, reason="")


def skip_if_server_version_lt(min_version):
    check = StrictVersion(get_version()) < StrictVersion(min_version)
    return pytest.mark.skipif(check, reason="")


def skip_if_server_version_gte(min_version):
    check = StrictVersion(get_version()) >= StrictVersion(min_version)
    return pytest.mark.skipif(check, reason="")


def skip_if_redis_py_version_lt(min_version):
    """
    """
    import redis
    version = redis.__version__
    if StrictVersion(version) < StrictVersion(min_version):
        return pytest.mark.skipif(True, reason="")
    return pytest.mark.skipif(False, reason="")


@pytest.fixture()
def o(request, *args, **kwargs):
    """
    Create a RedisCluster instance with decode_responses set to True.
    """
    return _init_client(request, cls=RedisCluster, decode_responses=True, **kwargs)


@pytest.fixture()
def r(request, *args, **kwargs):
    """
    Create a RedisCluster instance with default settings.
    """
    return _init_client(request, cls=RedisCluster, **kwargs)


@pytest.fixture()
def ro(request, *args, **kwargs):
    """
    Create a RedisCluster instance with readonly mode
    """
    params = {'readonly_mode': True}
    params.update(kwargs)
    return _init_client(request, cls=RedisCluster, **params)


@pytest.fixture()
def s(*args, **kwargs):
    """
    Create a RedisCluster instance with 'init_slot_cache' set to false
    """
    s = _get_client(RedisCluster, init_slot_cache=False, **kwargs)
    assert s.connection_pool.nodes.slots == {}
    assert s.connection_pool.nodes.nodes == {}
    return s


@pytest.fixture()
def t(*args, **kwargs):
    """
    Create a regular Redis object instance
    """
    return Redis(*args, **kwargs)


@pytest.fixture()
def sr(request, *args, **kwargs):
    """
    Returns a instance of RedisCluster
    """
    return _init_client(request, reinitialize_steps=1, cls=RedisCluster, **kwargs)


def _gen_cluster_mock_resp(r, response):
    mock_connection_pool = Mock()
    connection = Mock()
    response = response
    connection.read_response.return_value = response
    mock_connection_pool.get_connection.return_value = connection
    r.connection_pool = mock_connection_pool
    return r


@pytest.fixture()
def mock_cluster_resp_ok(request, **kwargs):
    r = _get_client(RedisCluster, request, **kwargs)
    return _gen_cluster_mock_resp(r, 'OK')


@pytest.fixture()
def mock_cluster_resp_int(request, **kwargs):
    r = _get_client(RedisCluster, request, **kwargs)
    return _gen_cluster_mock_resp(r, '2')


@pytest.fixture()
def mock_cluster_resp_info(request, **kwargs):
    r = _get_client(RedisCluster, request, **kwargs)
    response = ('cluster_state:ok\r\ncluster_slots_assigned:16384\r\n'
                'cluster_slots_ok:16384\r\ncluster_slots_pfail:0\r\n'
                'cluster_slots_fail:0\r\ncluster_known_nodes:7\r\n'
                'cluster_size:3\r\ncluster_current_epoch:7\r\n'
                'cluster_my_epoch:2\r\ncluster_stats_messages_sent:170262\r\n'
                'cluster_stats_messages_received:105653\r\n')
    return _gen_cluster_mock_resp(r, response)


@pytest.fixture()
def mock_cluster_resp_nodes(request, **kwargs):
    r = _get_client(RedisCluster, request, **kwargs)
    response = ('c8253bae761cb1ecb2b61857d85dfe455a0fec8b 172.17.0.7:7006 '
                'slave aa90da731f673a99617dfe930306549a09f83a6b 0 '
                '1447836263059 5 connected\n'
                '9bd595fe4821a0e8d6b99d70faa660638a7612b3 172.17.0.7:7008 '
                'master - 0 1447836264065 0 connected\n'
                'aa90da731f673a99617dfe930306549a09f83a6b 172.17.0.7:7003 '
                'myself,master - 0 0 2 connected 5461-10922\n'
                '1df047e5a594f945d82fc140be97a1452bcbf93e 172.17.0.7:7007 '
                'slave 19efe5a631f3296fdf21a5441680f893e8cc96ec 0 '
                '1447836262556 3 connected\n'
                '4ad9a12e63e8f0207025eeba2354bcf4c85e5b22 172.17.0.7:7005 '
                'master - 0 1447836262555 7 connected 0-5460\n'
                '19efe5a631f3296fdf21a5441680f893e8cc96ec 172.17.0.7:7004 '
                'master - 0 1447836263562 3 connected 10923-16383\n'
                'fbb23ed8cfa23f17eaf27ff7d0c410492a1093d6 172.17.0.7:7002 '
                'master,fail - 1447829446956 1447829444948 1 disconnected\n'
                )
    return _gen_cluster_mock_resp(r, response)


@pytest.fixture()
def mock_cluster_resp_slaves(request, **kwargs):
    r = _get_client(RedisCluster, request, **kwargs)
    response = ("['1df047e5a594f945d82fc140be97a1452bcbf93e 172.17.0.7:7007 "
                "slave 19efe5a631f3296fdf21a5441680f893e8cc96ec 0 "
                "1447836789290 3 connected']")
    return _gen_cluster_mock_resp(r, response)


def skip_unless_arch_bits(arch_bits):
    return pytest.mark.skipif(
        REDIS_INFO["arch_bits"] != arch_bits,
        reason="server is not {}-bit".format(arch_bits),
    )

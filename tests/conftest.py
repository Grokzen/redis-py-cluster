# -*- coding: utf-8 -*-

# python std lib
import os
import sys
import json

# rediscluster imports
from rediscluster import StrictRedisCluster, RedisCluster

# 3rd party imports
import pytest
from redis import StrictRedis
from distutils.version import StrictVersion

# put our path in front so we can be sure we are testing locally not against the global package
basepath = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(1, basepath)

_REDIS_VERSIONS = {}


def get_versions(**kwargs):
    """
    """
    key = json.dumps(kwargs)
    if key not in _REDIS_VERSIONS:
        client = _get_client(**kwargs)
        _REDIS_VERSIONS[key] = {key: value['redis_version'] for key, value in client.info().items()}
    return _REDIS_VERSIONS[key]


def _get_client(cls=None, **kwargs):
    """
    """
    if not cls:
        cls = RedisCluster

    params = {
        'startup_nodes': [{
            'host': '127.0.0.1', 'port': 7000
        }],
        'socket_timeout': 10,
        'decode_responses': False,
    }
    params.update(kwargs)
    return cls(**params)


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


def skip_if_not_password_protected_nodes():
    """
    """
    return pytest.mark.skipif('TEST_PASSWORD_PROTECTED' not in os.environ, reason="")


def skip_if_server_version_lt(min_version):
    """
    """
    versions = get_versions()
    for version in versions.values():
        if StrictVersion(version) < StrictVersion(min_version):
            return pytest.mark.skipif(True, reason="")
    return pytest.mark.skipif(False, reason="")


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
    Create a StrictRedisCluster instance with decode_responses set to True.
    """
    return _init_client(request, cls=StrictRedisCluster, decode_responses=True, **kwargs)


@pytest.fixture()
def r(request, *args, **kwargs):
    """
    Create a StrictRedisCluster instance with default settings.
    """
    return _init_client(request, cls=StrictRedisCluster, **kwargs)


@pytest.fixture()
def ro(request, *args, **kwargs):
    """
    Create a StrictRedisCluster instance with readonly mode
    """
    params = {'readonly_mode': True}
    params.update(kwargs)
    return _init_client(request, cls=StrictRedisCluster, **params)


@pytest.fixture()
def s(*args, **kwargs):
    """
    Create a StrictRedisCluster instance with 'init_slot_cache' set to false
    """
    s = _get_client(init_slot_cache=False, **kwargs)
    assert s.connection_pool.nodes.slots == {}
    assert s.connection_pool.nodes.nodes == {}
    return s


@pytest.fixture()
def t(*args, **kwargs):
    """
    Create a regular StrictRedis object instance
    """
    return StrictRedis(*args, **kwargs)


@pytest.fixture()
def sr(request, *args, **kwargs):
    """
    Returns a instance of StrictRedisCluster
    """
    return _init_client(request, reinitialize_steps=1, cls=StrictRedisCluster, **kwargs)

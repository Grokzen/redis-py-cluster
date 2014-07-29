import pytest
import os
import sys

# put our path in front so we can be sure we are testing locally not against the global package
basepath = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(1, basepath)

from rediscluster import RedisCluster

from distutils.version import StrictVersion
import json

_REDIS_VERSIONS = {}


def get_versions(**kwargs):
    key = json.dumps(kwargs)
    if key not in _REDIS_VERSIONS:
        client = _get_client(**kwargs)
        _REDIS_VERSIONS[key] = {key: value['redis_version'] for key, value in client.info().items()}
    return _REDIS_VERSIONS[key]


def _get_client(**kwargs):
    params = {'startup_nodes': [{'host': '127.0.0.1', 'port': 7000}], 'socket_timeout': 10, 'decode_responses': False}
    params.update(kwargs)
    return RedisCluster(**params)


def _init_client(cls, request=None, **kwargs):
    client = _get_client(**kwargs)
    client.flushdb()
    if request:
        def teardown():
            client.flushdb()
            # client.connection_pool.disconnect()
        request.addfinalizer(teardown)
    return client


def skip_if_server_version_lt(min_version):
    versions = get_versions()
    for version in versions.values():
        if StrictVersion(version) < StrictVersion(min_version):
            return pytest.mark.skipif(True, reason="")
    return pytest.mark.skipif(False, reason="")


@pytest.fixture()
def r(request, **kwargs):
    return _init_client(request, **kwargs)


@pytest.fixture()
def s(request, **kwargs):
    s = _get_client(init_slot_cache=False, **kwargs)
    assert s.slots == {}
    assert s.nodes == []
    return s

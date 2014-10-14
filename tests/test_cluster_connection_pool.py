# -*- coding: utf-8 -*-

# python std lib
from __future__ import with_statement
import os
import re
import time
from threading import Thread

# rediscluster imports
from rediscluster import RedisCluster
from rediscluster.connection import ClusterConnectionPool, ClusterConnection, UnixDomainSocketConnection
from rediscluster.exceptions import RedisClusterException
from tests.conftest import skip_if_server_version_lt

# 3rd party imports
import pytest
import redis
from redis.connection import ssl_available
from redis._compat import unicode


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


# @pytest.mark.xfail(reason="TODO: needs fixing")
# def test_connection_error(r):
#     """
#     Test that lib handles connection error properly
#     """
#     execute_command_via_connection_original = r.execute_command_via_connection
#     test = self
#     test.execute_command_calls = []

#     def execute_command_via_connection(r, *argv, **kwargs):
#         # the first time this is called, simulate an ASK exception.
#         # after that behave normally.
#         # capture all the requests and responses.
#         if not test.execute_command_calls:
#             e = ConnectionError('FAKE: could not connect')
#             test.execute_command_calls.append({'exception': e})
#             raise e
#         try:
#             result = execute_command_via_connection_original(r, *argv, **kwargs)
#             test.execute_command_calls.append({'argv': argv, 'kwargs': kwargs, 'result': result})
#             return result
#         except Exception as e:
#             test.execute_command_calls.append({'argv': argv, 'kwargs': kwargs, 'exception': e})
#             raise e

#     try:
#         r.execute_command_via_connection = execute_command_via_connection
#         r.set('foo', 'bar')
#         # print test.execute_command_calls
#         assert re.match('FAKE', str(test.execute_command_calls[0]['exception'])) is not None
#         # we might actually try a random node that is the correct one.
#         # in which case we won't get a moved exception.
#         if len(test.execute_command_calls) == 3:
#             assert re.match('MOVED', str(test.execute_command_calls[1]['exception'])) is not None
#             assert test.execute_command_calls[2]['argv'], ['SET', 'foo', 'bar']
#             assert test.execute_command_calls[2]['result'], True
#         else:
#             assert test.execute_command_calls[1]['argv'], ['SET', 'foo', 'bar']
#             assert test.execute_command_calls[1]['result'], True
#     finally:
#         r.execute_command_via_connection = execute_command_via_connection_original
#     assert r.get('foo'), 'bar'


class DummyConnection(object):
    description_format = "DummyConnection<>"

    def __init__(self, host="localhost", port=7000, socket_timeout=None, **kwargs):
        self.kwargs = kwargs
        self.pid = os.getpid()
        self.host = host
        self.port = port


class TestConnectionPool(object):
    def get_pool(self, connection_kwargs=None, max_connections=None, connection_class=DummyConnection):
        connection_kwargs = connection_kwargs or {}
        pool = ClusterConnectionPool(
            connection_class=connection_class,
            max_connections=max_connections,
            startup_nodes=[{"host": "127.0.0.1", "port": 7000}],
            **connection_kwargs)
        return pool

    def test_connection_creation(self):
        connection_kwargs = {'foo': 'bar', 'biz': 'baz'}
        pool = self.get_pool(connection_kwargs=connection_kwargs)
        connection = pool.get_connection_by_node({"host": "127.0.0.1", "port": 7000})
        assert isinstance(connection, DummyConnection)
        assert connection.kwargs == connection_kwargs

    def test_multiple_connections(self):
        pool = self.get_pool()
        c1 = pool.get_connection_by_node({"host": "127.0.0.1", "port": 7000})
        c2 = pool.get_connection_by_node({"host": "127.0.0.1", "port": 7001})
        assert c1 != c2

    def test_max_connections(self):
        pool = self.get_pool(max_connections=2)
        pool.get_connection_by_node({"host": "127.0.0.1", "port": 7000})
        pool.get_connection_by_node({"host": "127.0.0.1", "port": 7001})
        with pytest.raises(RedisClusterException):
            pool.get_connection_by_node({"host": "127.0.0.1", "port": 7000})

    def test_reuse_previously_released_connection(self):
        pool = self.get_pool()
        c1 = pool.get_connection_by_node({"host": "127.0.0.1", "port": 7000})
        pool.release(c1)
        c2 = pool.get_connection_by_node({"host": "127.0.0.1", "port": 7000})
        assert c1 == c2

    def test_repr_contains_db_info_tcp(self):
        connection_kwargs = {'host': 'localhost', 'port': 7000}
        pool = self.get_pool(connection_kwargs=connection_kwargs,
                             connection_class=ClusterConnection)
        expected = 'ClusterConnectionPool<ClusterConnection<host=localhost,port=7000>>'
        assert repr(pool) == expected

    def test_repr_contains_db_info_unix(self):
        connection_kwargs = {'path': '/abc', 'db': 1}
        pool = self.get_pool(connection_kwargs=connection_kwargs,
                             connection_class=UnixDomainSocketConnection)
        expected = 'ClusterConnectionPool<ClusterUnixDomainSocketConnection<path=/abc>>'
        assert repr(pool) == expected

    def test_get_connection_by_key(self):
        """
        This test assumes that when hashing key 'foo' will be sent to server with port 7002
        """
        connection_kwargs = {}
        pool = self.get_pool(connection_kwargs=connection_kwargs)

        connection = pool.get_connection_by_key("foo")
        assert connection.port == 7002

        with pytest.raises(RedisClusterException) as ex:
            pool.get_connection_by_key(None)
        assert unicode(ex.value).startswith("No way to dispatch this command to Redis Cluster."), True

    def test_get_connection_by_slot(self):
        """
        This test assumes that when doing keyslot operation on "foo" it will return 12182
        """
        connection_kwargs = {}
        pool = self.get_pool(connection_kwargs=connection_kwargs)

        connection = pool.get_connection_by_slot(12182)
        assert connection.port == 7002

        with pytest.raises(RedisClusterException) as ex:
            pool.get_connection_by_key(None)
        assert unicode(ex.value).startswith("No way to dispatch this command to Redis Cluster."), True


class TestBlockingConnectionPool(object):
    def get_pool(self, connection_kwargs=None, max_connections=10, timeout=20):
        connection_kwargs = connection_kwargs or {}
        pool = redis.BlockingConnectionPool(connection_class=DummyConnection,
                                            max_connections=max_connections,
                                            timeout=timeout,
                                            **connection_kwargs)
        return pool

    def test_connection_creation(self):
        connection_kwargs = {'foo': 'bar', 'biz': 'baz'}
        pool = self.get_pool(connection_kwargs=connection_kwargs)
        connection = pool.get_connection('_')
        assert isinstance(connection, DummyConnection)
        assert connection.kwargs == connection_kwargs

    def test_multiple_connections(self):
        pool = self.get_pool()
        c1 = pool.get_connection('_')
        c2 = pool.get_connection('_')
        assert c1 != c2

    def test_connection_pool_blocks_until_timeout(self):
        "When out of connections, block for timeout seconds, then raise"
        pool = self.get_pool(max_connections=1, timeout=0.1)
        pool.get_connection('_')

        start = time.time()
        with pytest.raises(redis.ConnectionError):
            pool.get_connection('_')
        # we should have waited at least 0.1 seconds
        assert time.time() - start >= 0.1

    def connection_pool_blocks_until_another_connection_released(self):
        """
        When out of connections, block until another connection is released
        to the pool
        """
        pool = self.get_pool(max_connections=1, timeout=2)
        c1 = pool.get_connection('_')

        def target():
            time.sleep(0.1)
            pool.release(c1)

        Thread(target=target).start()
        start = time.time()
        pool.get_connection('_')
        assert time.time() - start >= 0.1

    def test_reuse_previously_released_connection(self):
        pool = self.get_pool()
        c1 = pool.get_connection('_')
        pool.release(c1)
        c2 = pool.get_connection('_')
        assert c1 == c2

    def test_repr_contains_db_info_tcp(self):
        pool = redis.ConnectionPool(host='localhost', port=6379, db=0)
        expected = 'ConnectionPool<Connection<host=localhost,port=6379,db=0>>'
        assert repr(pool) == expected

    def test_repr_contains_db_info_unix(self):
        pool = redis.ConnectionPool(
            connection_class=redis.UnixDomainSocketConnection,
            path='abc',
            db=0,
        )
        expected = 'ConnectionPool<UnixDomainSocketConnection<path=abc,db=0>>'
        assert repr(pool) == expected


class TestConnectionPoolURLParsing(object):
    def test_defaults(self):
        pool = redis.ConnectionPool.from_url('redis://localhost')
        assert pool.connection_class == redis.Connection
        assert pool.connection_kwargs == {
            'host': 'localhost',
            'port': 6379,
            'db': 0,
            'password': None,
        }

    def test_hostname(self):
        pool = redis.ConnectionPool.from_url('redis://myhost')
        assert pool.connection_class == redis.Connection
        assert pool.connection_kwargs == {
            'host': 'myhost',
            'port': 6379,
            'db': 0,
            'password': None,
        }

    def test_port(self):
        pool = redis.ConnectionPool.from_url('redis://localhost:6380')
        assert pool.connection_class == redis.Connection
        assert pool.connection_kwargs == {
            'host': 'localhost',
            'port': 6380,
            'db': 0,
            'password': None,
        }

    def test_password(self):
        pool = redis.ConnectionPool.from_url('redis://:mypassword@localhost')
        assert pool.connection_class == redis.Connection
        assert pool.connection_kwargs == {
            'host': 'localhost',
            'port': 6379,
            'db': 0,
            'password': 'mypassword',
        }

    def test_db_as_argument(self):
        pool = redis.ConnectionPool.from_url('redis://localhost', db='1')
        assert pool.connection_class == redis.Connection
        assert pool.connection_kwargs == {
            'host': 'localhost',
            'port': 6379,
            'db': 1,
            'password': None,
        }

    def test_db_in_path(self):
        pool = redis.ConnectionPool.from_url('redis://localhost/2', db='1')
        assert pool.connection_class == redis.Connection
        assert pool.connection_kwargs == {
            'host': 'localhost',
            'port': 6379,
            'db': 2,
            'password': None,
        }

    def test_db_in_querystring(self):
        pool = redis.ConnectionPool.from_url('redis://localhost/2?db=3',
                                             db='1')
        assert pool.connection_class == redis.Connection
        assert pool.connection_kwargs == {
            'host': 'localhost',
            'port': 6379,
            'db': 3,
            'password': None,
        }

    def test_extra_querystring_options(self):
        pool = redis.ConnectionPool.from_url('redis://localhost?a=1&b=2')
        assert pool.connection_class == redis.Connection
        assert pool.connection_kwargs == {
            'host': 'localhost',
            'port': 6379,
            'db': 0,
            'password': None,
            'a': '1',
            'b': '2'
        }

    def test_calling_from_subclass_returns_correct_instance(self):
        pool = redis.BlockingConnectionPool.from_url('redis://localhost')
        assert isinstance(pool, redis.BlockingConnectionPool)

    def test_client_creates_connection_pool(self):
        r = redis.StrictRedis.from_url('redis://myhost')
        assert r.connection_pool.connection_class == redis.Connection
        assert r.connection_pool.connection_kwargs == {
            'host': 'myhost',
            'port': 6379,
            'db': 0,
            'password': None,
        }


class TestConnectionPoolUnixSocketURLParsing(object):
    def test_defaults(self):
        pool = redis.ConnectionPool.from_url('unix:///socket')
        assert pool.connection_class == redis.UnixDomainSocketConnection
        assert pool.connection_kwargs == {
            'path': '/socket',
            'db': 0,
            'password': None,
        }

    def test_password(self):
        pool = redis.ConnectionPool.from_url('unix://:mypassword@/socket')
        assert pool.connection_class == redis.UnixDomainSocketConnection
        assert pool.connection_kwargs == {
            'path': '/socket',
            'db': 0,
            'password': 'mypassword',
        }

    def test_db_as_argument(self):
        pool = redis.ConnectionPool.from_url('unix:///socket', db=1)
        assert pool.connection_class == redis.UnixDomainSocketConnection
        assert pool.connection_kwargs == {
            'path': '/socket',
            'db': 1,
            'password': None,
        }

    def test_db_in_querystring(self):
        pool = redis.ConnectionPool.from_url('unix:///socket?db=2', db=1)
        assert pool.connection_class == redis.UnixDomainSocketConnection
        assert pool.connection_kwargs == {
            'path': '/socket',
            'db': 2,
            'password': None,
        }

    def test_extra_querystring_options(self):
        pool = redis.ConnectionPool.from_url('unix:///socket?a=1&b=2')
        assert pool.connection_class == redis.UnixDomainSocketConnection
        assert pool.connection_kwargs == {
            'path': '/socket',
            'db': 0,
            'password': None,
            'a': '1',
            'b': '2'
        }


class TestSSLConnectionURLParsing(object):
    @pytest.mark.skipif(not ssl_available, reason="SSL not installed")
    def test_defaults(self):
        pool = redis.ConnectionPool.from_url('rediss://localhost')
        assert pool.connection_class == redis.SSLConnection
        assert pool.connection_kwargs == {
            'host': 'localhost',
            'port': 6379,
            'db': 0,
            'password': None,
        }

    @pytest.mark.skipif(not ssl_available, reason="SSL not installed")
    def test_cert_reqs_options(self):
        import ssl
        pool = redis.ConnectionPool.from_url('rediss://?ssl_cert_reqs=none')
        assert pool.get_connection('_').cert_reqs == ssl.CERT_NONE

        pool = redis.ConnectionPool.from_url(
            'rediss://?ssl_cert_reqs=optional')
        assert pool.get_connection('_').cert_reqs == ssl.CERT_OPTIONAL

        pool = redis.ConnectionPool.from_url(
            'rediss://?ssl_cert_reqs=required')
        assert pool.get_connection('_').cert_reqs == ssl.CERT_REQUIRED


class TestConnection(object):
    def test_on_connect_error(self):
        """
        An error in Connection.on_connect should disconnect from the server
        see for details: https://github.com/andymccurdy/redis-py/issues/368
        """
        # this assumes the Redis server being tested against doesn't have
        # 9999 databases ;)
        bad_connection = redis.Redis(db=9999)
        # an error should be raised on connect
        with pytest.raises(redis.RedisError):
            bad_connection.info()
        pool = bad_connection.connection_pool
        assert len(pool._available_connections) == 1
        assert not pool._available_connections[0]._sock

    @skip_if_server_version_lt('2.8.8')
    def test_busy_loading_disconnects_socket(self, r):
        """
        If Redis raises a LOADING error, the connection should be
        disconnected and a BusyLoadingError raised
        """
        with pytest.raises(redis.BusyLoadingError):
            r.execute_command('DEBUG', 'ERROR', 'LOADING fake message')
        # TODO: Sinc we have to query the cluster before we send this DEBUG command
        #  we will have more then 1 connection in our pool and asserting 1 connection will
        #  not work.
        pool = r.connection_pool
        assert len(pool._available_connections) >= 1
        # assert not pool._available_connections[0]._sock

    @pytest.mark.xfail(reason="pipeline NYI")
    @skip_if_server_version_lt('2.8.8')
    def test_busy_loading_from_pipeline_immediate_command(self, r):
        """
        BusyLoadingErrors should raise from Pipelines that execute a
        command immediately, like WATCH does.
        """
        pipe = r.pipeline()
        with pytest.raises(redis.BusyLoadingError):
            pipe.immediate_execute_command('DEBUG', 'ERROR',
                                           'LOADING fake message')
        pool = r.connection_pool
        assert not pipe.connection
        assert len(pool._available_connections) == 1
        assert not pool._available_connections[0]._sock

    @pytest.mark.xfail(reason="pipeline NYI")
    @skip_if_server_version_lt('2.8.8')
    def test_busy_loading_from_pipeline(self, r):
        """
        BusyLoadingErrors should be raised from a pipeline execution
        regardless of the raise_on_error flag.
        """
        pipe = r.pipeline()
        pipe.execute_command('DEBUG', 'ERROR', 'LOADING fake message')
        with pytest.raises(redis.BusyLoadingError):
            pipe.execute()
        pool = r.connection_pool
        assert not pipe.connection
        assert len(pool._available_connections) == 1
        assert not pool._available_connections[0]._sock

    @skip_if_server_version_lt('2.8.8')
    def test_read_only_error(self, r):
        "READONLY errors get turned in ReadOnlyError exceptions"
        with pytest.raises(redis.ReadOnlyError):
            r.execute_command('DEBUG', 'ERROR', 'READONLY blah blah')

    def test_connect_from_url_tcp(self):
        connection = redis.Redis.from_url('redis://localhost')
        pool = connection.connection_pool

        assert re.match('(.*)<(.*)<(.*)>>', repr(pool)).groups() == (
            'ConnectionPool',
            'Connection',
            'host=localhost,port=6379,db=0',
        )

    def test_connect_from_url_unix(self):
        connection = redis.Redis.from_url('unix:///path/to/socket')
        pool = connection.connection_pool

        assert re.match('(.*)<(.*)<(.*)>>', repr(pool)).groups() == (
            'ConnectionPool',
            'UnixDomainSocketConnection',
            'path=/path/to/socket,db=0',
        )

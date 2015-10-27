# -*- coding: utf-8 -*-

# python std lib
from __future__ import with_statement
import os
import re
import time
from threading import Thread

# rediscluster imports
from rediscluster.connection import (
    ClusterConnectionPool, ClusterReadOnlyConnectionPool,
    ClusterConnection, UnixDomainSocketConnection)
from rediscluster.exceptions import RedisClusterException
from tests.conftest import skip_if_server_version_lt

# 3rd party imports
import pytest
import redis
from mock import patch, Mock
from redis.connection import ssl_available
from redis._compat import unicode


class DummyConnection(object):
    description_format = "DummyConnection<>"

    def __init__(self, host="localhost", port=7000, socket_timeout=None, **kwargs):
        self.kwargs = kwargs
        self.pid = os.getpid()
        self.host = host
        self.port = port


class TestConnectionPool(object):
    def get_pool(self, connection_kwargs=None, max_connections=None, max_connections_per_node=None,
                 connection_class=DummyConnection, init_slot_cache=True):
        connection_kwargs = connection_kwargs or {}
        pool = ClusterConnectionPool(
            connection_class=connection_class,
            max_connections=max_connections,
            max_connections_per_node=max_connections_per_node,
            startup_nodes=[{"host": "127.0.0.1", "port": 7000}],
            init_slot_cache=init_slot_cache,
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

    def test_max_connections_per_node(self):
        pool = self.get_pool(max_connections=2, max_connections_per_node=True)
        pool.get_connection_by_node({"host": "127.0.0.1", "port": 7000})
        pool.get_connection_by_node({"host": "127.0.0.1", "port": 7001})
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
        """
        Note: init_slot_cache muts be set to false otherwise it will try to
              query the test server for data and then it can't be predicted reliably
        """
        connection_kwargs = {'host': 'localhost', 'port': 7000}
        pool = self.get_pool(connection_kwargs=connection_kwargs,
                             connection_class=ClusterConnection,
                             init_slot_cache=False)
        expected = 'ClusterConnectionPool<ClusterConnection<host=localhost,port=7000>>'
        assert repr(pool) == expected

    def test_repr_contains_db_info_unix(self):
        """
        Note: init_slot_cache muts be set to false otherwise it will try to
              query the test server for data and then it can't be predicted reliably
        """
        connection_kwargs = {'path': '/abc', 'db': 1}
        pool = self.get_pool(connection_kwargs=connection_kwargs,
                             connection_class=UnixDomainSocketConnection,
                             init_slot_cache=False)
        expected = 'ClusterConnectionPool<ClusterUnixDomainSocketConnection<path=/abc>>'
        assert repr(pool) == expected

    def test_get_connection_by_key(self):
        """
        This test assumes that when hashing key 'foo' will be sent to server with port 7002
        """
        pool = self.get_pool(connection_kwargs={})

        # Patch the call that is made inside the method to allow control of the returned connection object
        with patch.object(ClusterConnectionPool, 'get_connection_by_slot', autospec=True) as pool_mock:
            def side_effect(self, *args, **kwargs):
                return DummyConnection(port=1337)
            pool_mock.side_effect = side_effect

            connection = pool.get_connection_by_key("foo")
            assert connection.port == 1337

        with pytest.raises(RedisClusterException) as ex:
            pool.get_connection_by_key(None)
        assert unicode(ex.value).startswith("No way to dispatch this command to Redis Cluster."), True

    def test_get_connection_by_slot(self):
        """
        This test assumes that when doing keyslot operation on "foo" it will return 12182
        """
        pool = self.get_pool(connection_kwargs={})

        # Patch the call that is made inside the method to allow control of the returned connection object
        with patch.object(ClusterConnectionPool, 'get_connection_by_node', autospec=True) as pool_mock:
            def side_effect(self, *args, **kwargs):
                return DummyConnection(port=1337)
            pool_mock.side_effect = side_effect

            connection = pool.get_connection_by_slot(12182)
            assert connection.port == 1337

        m = Mock()
        pool.get_random_connection = m

        # If None value is provided then a random node should be tried/returned
        pool.get_connection_by_slot(None)
        m.assert_called_once_with()

    def test_get_connection_blocked(self):
        """
        Currently get_connection() should only be used by pubsub command.
        All other commands should be blocked and exception raised.
        """
        pool = self.get_pool()

        with pytest.raises(RedisClusterException) as ex:
            pool.get_connection("GET")
        assert unicode(ex.value).startswith("Only 'pubsub' commands can be used by get_connection()")

    def test_master_node_by_slot(self):
        pool = self.get_pool(connection_kwargs={})
        node = pool.get_master_node_by_slot(0)
        node['port'] = 7000
        node = pool.get_master_node_by_slot(12182)
        node['port'] = 7002


class TestReadOnlyConnectionPool(object):
    def get_pool(self, connection_kwargs=None, max_connections=None, init_slot_cache=True, startup_nodes=None):
        startup_nodes = startup_nodes or [{'host': '127.0.0.1', 'port': 7000}]
        connection_kwargs = connection_kwargs or {}
        pool = ClusterReadOnlyConnectionPool(
            init_slot_cache=init_slot_cache,
            max_connections=max_connections,
            startup_nodes=startup_nodes,
            **connection_kwargs)
        return pool

    def test_repr_contains_db_info_readonly(self):
        """
        Note: init_slot_cache must be set to false otherwise it will try to
              query the test server for data and then it can't be predicted reliably
        """
        pool = self.get_pool(
            init_slot_cache=False,
            startup_nodes=[{"host": "127.0.0.1", "port": 7000}, {"host": "127.0.0.2", "port": 7001}],
        )
        expected = 'ClusterReadOnlyConnectionPool<ClusterConnection<host=127.0.0.1,port=7000>, ClusterConnection<host=127.0.0.2,port=7001>>'
        assert repr(pool) == expected

    def test_max_connections(self):
        pool = self.get_pool(max_connections=2)
        pool.get_connection_by_node({"host": "127.0.0.1", "port": 7000})
        pool.get_connection_by_node({"host": "127.0.0.1", "port": 7001})
        with pytest.raises(RedisClusterException):
            pool.get_connection_by_node({"host": "127.0.0.1", "port": 7000})

    def test_get_node_by_slot(self):
        """
        We can randomly get all nodes in readonly mode.
        """
        pool = self.get_pool(connection_kwargs={})

        expected_ports = {7000, 7003}
        actual_ports = set()
        for _ in range(0, 100):
            node = pool.get_node_by_slot(0)
            actual_ports.add(node['port'])
        assert actual_ports == expected_ports


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

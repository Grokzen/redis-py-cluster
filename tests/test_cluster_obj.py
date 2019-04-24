# -*- coding: utf-8 -*-

# python std lib
from __future__ import with_statement
import re
import time

# rediscluster imports
from rediscluster import RedisCluster
from rediscluster.connection import ClusterConnectionPool, ClusterReadOnlyConnectionPool
from rediscluster.exceptions import (
    RedisClusterException, MovedError, AskError, ClusterDownError,
)
from rediscluster.nodemanager import NodeManager
from tests.conftest import _get_client, skip_if_server_version_lt, skip_if_not_password_protected_nodes

# 3rd party imports
from mock import patch, Mock, MagicMock
from redis._compat import unicode
from redis import Redis
import pytest

pytestmark = skip_if_server_version_lt('2.9.0')


class DummyConnectionPool(ClusterConnectionPool):
    pass


class DummyConnection(object):
    pass


def get_mocked_redis_client(*args, **kwargs):
    """
    Return a stable RedisCluster object that have deterministic
    nodes and slots setup to remove the problem of different IP addresses
    on different installations and machines.
    """
    with patch.object(Redis, 'execute_command') as execute_command_mock:
        def execute_command(self, *args, **kwargs):
            if args[0] == 'slots':
                mock_cluster_slots = [
                    [
                        0, 5460,
                        ['127.0.0.1', 7000, 'node_0'],
                        ['127.0.0.1', 7004, 'node_4']
                    ],
                    [
                        5461, 10922,
                        ['127.0.0.1', 7001, 'node_1'],
                        ['127.0.0.1', 7005, 'node_5']
                    ],
                    [
                        10923, 16383,
                        ['127.0.0.1', 7002, 'node_2'],
                        ['127.0.0.1', 7003, '2node_3']
                    ]
                ]
                return mock_cluster_slots
            elif args[0] == 'cluster-require-full-coverage':
                return {'cluster-require-full-coverage': 'yes'}

        execute_command_mock.side_effect = execute_command

        return RedisCluster(*args, **kwargs)


def test_representation(r):
    assert re.search('^RedisCluster<[0-9\.\:\,].+>$', str(r))


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


@skip_if_not_password_protected_nodes()
def test_password_procted_nodes():
    """
    Test that it is possible to connect to password protected nodes
    """
    startup_nodes = [{"host": "127.0.0.1", "port": "7000"}]
    password_protected_startup_nodes = [{"host": "127.0.0.1", "port": "7100"}]
    with pytest.raises(RedisClusterException) as ex:
        _get_client(startup_nodes=password_protected_startup_nodes)
    assert unicode(ex.value).startswith("ERROR sending 'cluster slots' command to redis server:")
    _get_client(startup_nodes=password_protected_startup_nodes, password='password_is_protected')

    with pytest.raises(RedisClusterException) as ex:
        _get_client(startup_nodes=startup_nodes, password='password_is_protected')
    assert unicode(ex.value).startswith("ERROR sending 'cluster slots' command to redis server:")
    _get_client(startup_nodes=startup_nodes)


def test_host_port_startup_node():
    """
    Test that it is possible to use host & port arguments as startup node args
    """
    h = "192.168.0.1"
    p = 7000
    c = RedisCluster(host=h, port=p, init_slot_cache=False)
    assert {"host": h, "port": p} in c.connection_pool.nodes.startup_nodes


def test_empty_startup_nodes():
    """
    Test that exception is raised when empty providing empty startup_nodes
    """
    with pytest.raises(RedisClusterException) as ex:
        _get_client(init_slot_cache=False, startup_nodes=[])

    assert unicode(ex.value).startswith("No startup nodes provided"), unicode(ex.value)


def test_readonly_instance(ro):
    """
    Test that readonly_mode=True instance has ClusterReadOnlyConnectionPool
    """
    assert isinstance(ro.connection_pool, ClusterReadOnlyConnectionPool)


def test_custom_connectionpool():
    """
    Test that a custom connection pool will be used by RedisCluster
    """
    h = "192.168.0.1"
    p = 7001
    pool = DummyConnectionPool(host=h, port=p, connection_class=DummyConnection,
                               startup_nodes=[{'host': h, 'port': p}],
                               init_slot_cache=False)
    c = RedisCluster(connection_pool=pool, init_slot_cache=False)
    assert c.connection_pool is pool
    assert c.connection_pool.connection_class == DummyConnection
    assert {"host": h, "port": p} in c.connection_pool.nodes.startup_nodes


@patch('rediscluster.nodemanager.Redis', new=MagicMock())
def test_skip_full_coverage_check():
    """
    Test if the cluster_require_full_coverage NodeManager method was not called with the flag activated
    """
    c = RedisCluster("192.168.0.1", 7001, init_slot_cache=False, skip_full_coverage_check=True)
    c.connection_pool.nodes.cluster_require_full_coverage = MagicMock()
    c.connection_pool.nodes.initialize()
    assert not c.connection_pool.nodes.cluster_require_full_coverage.called


def test_blocked_commands(r):
    """
    These commands should be blocked and raise RedisClusterException
    """
    blocked_commands = [
        "CLIENT SETNAME", "SENTINEL GET-MASTER-ADDR-BY-NAME", 'SENTINEL MASTER', 'SENTINEL MASTERS',
        'SENTINEL MONITOR', 'SENTINEL REMOVE', 'SENTINEL SENTINELS', 'SENTINEL SET',
        'SENTINEL SLAVES', 'SHUTDOWN', 'SLAVEOF', 'SCRIPT KILL', 'MOVE', 'BITOP',
    ]

    for command in blocked_commands:
        try:
            r.execute_command(command)
        except RedisClusterException:
            pass
        else:
            raise AssertionError("'RedisClusterException' not raised for method : {0}".format(command))


def test_blocked_transaction(r):
    """
    Method transaction is blocked/NYI and should raise exception on use
    """
    with pytest.raises(RedisClusterException) as ex:
        r.transaction(None)
    assert unicode(ex.value).startswith("method RedisCluster.transaction() is not implemented"), unicode(ex.value)


def test_cluster_of_one_instance():
    """
    Test a cluster that starts with only one redis server and ends up with
    one server.

    There is another redis server joining the cluster, hold slot 0, and
    eventually quit the cluster. The RedisCluster instance may get confused
    when slots mapping and nodes change during the test.
    """
    with patch.object(RedisCluster, 'parse_response') as parse_response_mock:
        with patch.object(NodeManager, 'initialize', autospec=True) as init_mock:
            def side_effect(self, *args, **kwargs):
                def ok_call(self, *args, **kwargs):
                    assert self.port == 7007
                    return "OK"
                parse_response_mock.side_effect = ok_call

                raise ClusterDownError('CLUSTERDOWN The cluster is down. Use CLUSTER INFO for more information')

            def side_effect_rebuild_slots_cache(self):
                # make new node cache that points to 7007 instead of 7006
                self.nodes = [{'host': '127.0.0.1', 'server_type': 'master', 'port': 7006, 'name': '127.0.0.1:7006'}]
                self.slots = {}

                for i in range(0, 16383):
                    self.slots[i] = [{
                        'host': '127.0.0.1',
                        'server_type': 'master',
                        'port': 7006,
                        'name': '127.0.0.1:7006',
                    }]

                # Second call should map all to 7007
                def map_7007(self):
                    self.nodes = [{'host': '127.0.0.1', 'server_type': 'master', 'port': 7007, 'name': '127.0.0.1:7007'}]
                    self.slots = {}

                    for i in range(0, 16383):
                        self.slots[i] = [{
                            'host': '127.0.0.1',
                            'server_type': 'master',
                            'port': 7007,
                            'name': '127.0.0.1:7007',
                        }]

                # First call should map all to 7006
                init_mock.side_effect = map_7007

            parse_response_mock.side_effect = side_effect
            init_mock.side_effect = side_effect_rebuild_slots_cache

            rc = RedisCluster(host='127.0.0.1', port=7006)
            rc.set("foo", "bar")


def test_execute_command_errors(r):
    """
    If no command is given to `_determine_nodes` then exception
    should be raised.

    Test that if no key is provided then exception should be raised.
    """
    with pytest.raises(RedisClusterException) as ex:
        r.execute_command()
    assert unicode(ex.value).startswith("Unable to determine command to use")

    with pytest.raises(RedisClusterException) as ex:
        r.execute_command("GET")
    assert unicode(ex.value).startswith("No way to dispatch this command to Redis Cluster. Missing key.")


def test_refresh_table_asap():
    """
    If this variable is set externally, initialize() should be called.
    """
    with patch.object(NodeManager, 'initialize') as mock_initialize:
        mock_initialize.return_value = None

        # Patch parse_response to avoid issues when the cluster sometimes return MOVED
        with patch.object(RedisCluster, 'parse_response') as mock_parse_response:
            def side_effect(self, *args, **kwargs):
                return None
            mock_parse_response.side_effect = side_effect

            r = RedisCluster(host="127.0.0.1", port=7000)
            r.connection_pool.nodes.slots[12182] = [{
                "host": "127.0.0.1",
                "port": 7002,
                "name": "127.0.0.1:7002",
                "server_type": "master",
            }]
            r.refresh_table_asap = True

            i = len(mock_initialize.mock_calls)
            r.execute_command("SET", "foo", "bar")
            assert len(mock_initialize.mock_calls) - i == 1
            assert r.refresh_table_asap is False


def find_node_ip_based_on_port(cluster_client, port):
    for node_name, node_data in cluster_client.connection_pool.nodes.nodes.items():
        if node_name.endswith(port):
            return node_data['host']


def test_ask_redirection():
    """
    Test that the server handles ASK response.

    At first call it should return a ASK ResponseError that will point
    the client to the next server it should talk to.

    Important thing to verify is that it tries to talk to the second node.
    """
    r = RedisCluster(host="127.0.0.1", port=7000)
    r.connection_pool.nodes.nodes['127.0.0.1:7001'] = {
        'host': u'127.0.0.1',
        'server_type': 'master',
        'port': 7001,
        'name': '127.0.0.1:7001'
    }
    with patch.object(RedisCluster,
                      'parse_response') as parse_response:

        host_ip = find_node_ip_based_on_port(r, '7001')

        def ask_redirect_effect(connection, *args, **options):
            def ok_response(connection, *args, **options):
                assert connection.host == host_ip
                assert connection.port == 7001

                return "MOCK_OK"
            parse_response.side_effect = ok_response
            raise AskError("1337 {0}:7001".format(host_ip))

        parse_response.side_effect = ask_redirect_effect

        assert r.execute_command("SET", "foo", "bar") == "MOCK_OK"


def test_pipeline_ask_redirection():
    """
    Test that the server handles ASK response when used in pipeline.

    At first call it should return a ASK ResponseError that will point
    the client to the next server it should talk to.

    Important thing to verify is that it tries to talk to the second node.
    """
    r = get_mocked_redis_client(host="127.0.0.1", port=7000)
    with patch.object(RedisCluster,
                      'parse_response') as parse_response:

        def response(connection, *args, **options):
            def response(connection, *args, **options):
                def response(connection, *args, **options):
                    assert connection.host == "127.0.0.1"
                    assert connection.port == 7001
                    return "MOCK_OK"

                parse_response.side_effect = response
                raise AskError("12182 127.0.0.1:7001")

            parse_response.side_effect = response
            raise AskError("12182 127.0.0.1:7001")

        parse_response.side_effect = response

        p = r.pipeline()
        p.set("foo", "bar")
        assert p.execute() == ["MOCK_OK"]


def test_moved_redirection():
    """
    Test that the client handles MOVED response.

    At first call it should return a MOVED ResponseError that will point
    the client to the next server it should talk to.

    Important thing to verify is that it tries to talk to the second node.
    """
    r = get_mocked_redis_client(host="127.0.0.1", port=7000)
    m = Mock(autospec=True)

    def ask_redirect_effect(connection, *args, **options):
        def ok_response(connection, *args, **options):
            assert connection.host == "127.0.0.1"
            assert connection.port == 7002

            return "MOCK_OK"
        m.side_effect = ok_response
        raise MovedError("12182 127.0.0.1:7002")

    m.side_effect = ask_redirect_effect

    r.parse_response = m
    assert r.set("foo", "bar") == "MOCK_OK"


def test_moved_redirection_pipeline():
    """
    Test that the server handles MOVED response when used in pipeline.

    At first call it should return a MOVED ResponseError that will point
    the client to the next server it should talk to.

    Important thing to verify is that it tries to talk to the second node.
    """
    with patch.object(RedisCluster, 'parse_response') as parse_response:
        def moved_redirect_effect(connection, *args, **options):
            def ok_response(connection, *args, **options):
                assert connection.host == "127.0.0.1"
                assert connection.port == 7002

                return "MOCK_OK"
            parse_response.side_effect = ok_response
            raise MovedError("12182 127.0.0.1:7002")

        parse_response.side_effect = moved_redirect_effect

        # r = RedisCluster(host="127.0.0.1", port=7000)
        r = get_mocked_redis_client(host="127.0.0.1", port=7000)
        p = r.pipeline()
        p.set("foo", "bar")
        assert p.execute() == ["MOCK_OK"]


def assert_moved_redirection_on_slave(sr, connection_pool_cls, cluster_obj):
    """
    """
    # we assume this key is set on 127.0.0.1:7000(7003)
    sr.set('foo16706', 'foo')
    time.sleep(1)

    with patch.object(connection_pool_cls, 'get_node_by_slot') as return_slave_mock:
        return_slave_mock.return_value = {
            'name': '127.0.0.1:7004',
            'host': '127.0.0.1',
            'port': 7004,
            'server_type': 'slave',
        }

        master_value = {
            'host': '127.0.0.1',
            'name': '127.0.0.1:7000',
            'port': 7000,
            'server_type': 'master',
        }

        with patch.object(ClusterConnectionPool, 'get_master_node_by_slot') as return_master_mock:
            return_master_mock.return_value = master_value
            assert cluster_obj.get('foo16706') == b'foo'
            assert return_master_mock.call_count == 1


def test_moved_redirection_on_slave_with_default_client(sr):
    """
    Test that the client is redirected normally with default
    (readonly_mode=False) client even when we connect always to slave.
    """
    r = get_mocked_redis_client(host="127.0.0.1", port=7000)

    assert_moved_redirection_on_slave(
        sr,
        ClusterConnectionPool,
        # RedisCluster(host="127.0.0.1", port=7000, reinitialize_steps=1)
        get_mocked_redis_client(host="127.0.0.1", port=7000, reinitialize_steps=1)
    )


def test_moved_redirection_on_slave_with_readonly_mode_client(sr):
    """
    Ditto with READONLY mode.
    """
    assert_moved_redirection_on_slave(
        sr,
        ClusterReadOnlyConnectionPool,
        RedisCluster(host="127.0.0.1", port=7000, readonly_mode=True, reinitialize_steps=1)
    )


def test_access_correct_slave_with_readonly_mode_client(sr):
    """
    Test that the client can get value normally with readonly mode
    when we connect to correct slave.
    """

    # we assume this key is set on 127.0.0.1:7000(7003)
    sr.set('foo16706', 'foo')
    import time
    time.sleep(1)

    with patch.object(ClusterReadOnlyConnectionPool, 'get_node_by_slot') as return_slave_mock:
        return_slave_mock.return_value = {
            'name': '127.0.0.1:7003',
            'host': '127.0.0.1',
            'port': 7003,
            'server_type': 'slave',
        }

        master_value = {'host': '127.0.0.1', 'name': '127.0.0.1:7000', 'port': 7000, 'server_type': 'master'}
        with patch.object(
                ClusterConnectionPool,
                'get_master_node_by_slot',
                return_value=master_value) as return_master_mock:
            readonly_client = RedisCluster(host="127.0.0.1", port=7000, readonly_mode=True)
            assert b'foo' == readonly_client.get('foo16706')

            readonly_client = RedisCluster.from_url(url="redis://127.0.0.1:7000/0", readonly_mode=True)
            assert b'foo' == readonly_client.get('foo16706')


def test_refresh_using_specific_nodes(r):
    """
    Test making calls on specific nodes when the cluster has failed over to
    another node
    """
    with patch.object(RedisCluster, 'parse_response') as parse_response_mock:
        with patch.object(NodeManager, 'initialize', autospec=True) as init_mock:
            # simulate 7006 as a failed node
            def side_effect(self, *args, **kwargs):
                if self.port == 7006:
                    parse_response_mock.failed_calls += 1
                    raise ClusterDownError('CLUSTERDOWN The cluster is down. Use CLUSTER INFO for more information')
                elif self.port == 7007:
                    parse_response_mock.successful_calls += 1

            def side_effect_rebuild_slots_cache(self):
                # start with all slots mapped to 7006
                self.nodes = {'127.0.0.1:7006': {'host': '127.0.0.1', 'server_type': 'master', 'port': 7006, 'name': '127.0.0.1:7006'}}
                self.slots = {}

                for i in range(0, 16383):
                    self.slots[i] = [{
                        'host': '127.0.0.1',
                        'server_type': 'master',
                        'port': 7006,
                        'name': '127.0.0.1:7006',
                    }]

                # After the first connection fails, a reinitialize should follow the cluster to 7007
                def map_7007(self):
                    self.nodes = {'127.0.0.1:7007': {'host': '127.0.0.1', 'server_type': 'master', 'port': 7007, 'name': '127.0.0.1:7007'}}
                    self.slots = {}

                    for i in range(0, 16383):
                        self.slots[i] = [{
                            'host': '127.0.0.1',
                            'server_type': 'master',
                            'port': 7007,
                            'name': '127.0.0.1:7007',
                        }]
                init_mock.side_effect = map_7007

            parse_response_mock.side_effect = side_effect
            parse_response_mock.successful_calls = 0
            parse_response_mock.failed_calls = 0

            init_mock.side_effect = side_effect_rebuild_slots_cache

            rc = RedisCluster(host='127.0.0.1', port=7006)
            assert len(rc.connection_pool.nodes.nodes) == 1
            assert '127.0.0.1:7006' in rc.connection_pool.nodes.nodes

            rc.ping()

            # Cluster should now point to 7006, and there should be one failed and one succesful call
            assert len(rc.connection_pool.nodes.nodes) == 1
            assert '127.0.0.1:7007' in rc.connection_pool.nodes.nodes
            assert parse_response_mock.failed_calls == 1
            assert parse_response_mock.successful_calls == 1

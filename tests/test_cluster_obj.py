from __future__ import with_statement
from rediscluster import RedisCluster
import pytest
import redis
import re
from .conftest import _get_client, skip_if_server_version_lt
from rediscluster.exceptions import RedisClusterException
from redis._compat import unicode


pytestmark = skip_if_server_version_lt('2.9.0')


class TestClusterObj(object):

    def test_representation(self, r):
        assert re.search('^RedisCluster<[0-9\.\:\,]+>$', str(r))

    def test_blocked_strict_redis_args(self):
        """
        Some arguments should explicitly be blocked because they will not work in a cluster setup
        """
        c = RedisCluster({'startup_nodes': [{'host': '127.0.0.1', 'port': 7000}]})
        assert c.opt["socket_timeout"] == RedisCluster.RedisClusterDefaultTimeout

        with pytest.raises(RedisClusterException) as ex:
            _get_client(db=1)
        assert unicode(ex.value).startswith("(error) [Remove 'db' from kwargs]"), True

        with pytest.raises(RedisClusterException) as ex:
            _get_client(host="foo.bar")
        assert unicode(ex.value).startswith("(error) [Remove 'host' from kwargs]"), True

        with pytest.raises(RedisClusterException) as ex:
            _get_client(port=1337)
        assert unicode(ex.value).startswith("(error) [Remove 'port' from kwargs]"), True

    def test_get_redis_link(self, s):
        """
        Test that method returns a StrictRedis object
        """
        link = s.get_redis_link("127.0.0.1", 7000)
        assert isinstance(link, redis.StrictRedis)

    def test_set_node_name(self, s):
        """
        Test that method sets ["name"] correctly
        """
        n = {"host": "127.0.0.1", "port": 7000}
        s.set_node_name(n)
        assert "name" in n
        assert n["name"] == "127.0.0.1:7000"

    def test_keyslot(self, s):
        """
        Test that method will compute correct key in all supported cases
        """
        assert s.RedisClusterHashSlots == 16384
        h = s.keyslot("foo")
        assert h == 12182

        h = s.keyslot("{foo}bar")
        assert h == 12182

        h = s.keyslot("{foo}")
        assert h == 12182

        with pytest.raises(AttributeError):
            h = s.keyslot(1337)

    def test_init_slots_cache(self, s):
        """
        Test that slots cache can in initialized and all slots are covered
        """
        good_slots_resp = [[0, 5460, [b'127.0.0.1', 7000], [b'127.0.0.1', 7003]],
                           [5461, 10922, [b'127.0.0.1', 7001], [b'127.0.0.1', 7004]],
                           [10923, 16383, [b'127.0.0.1', 7002], [b'127.0.0.1', 7005]]]

        s.execute_command = lambda *args: good_slots_resp
        s.initialize_slots_cache()
        assert len(s.slots) == RedisCluster.RedisClusterHashSlots
        assert len(s.nodes) == 6

    def test_init_slots_cache_not_all_slots(self, s):
        """
        Test that if not all slots are covered it should raise an exception
        """
        # Save the old function so we can wrap it
        old_get_link_from_node = s.get_redis_link_from_node

        # Create wrapper function so we can inject custom 'CLUSTER SLOTS' command result
        def new_get_link_from_node(node):
            link = old_get_link_from_node(node)

            # Missing slot 5460
            bad_slots_resp = [[0, 5459, [b'127.0.0.1', 7000], [b'127.0.0.1', 7003]],
                              [5461, 10922, [b'127.0.0.1', 7001], [b'127.0.0.1', 7004]],
                              [10923, 16383, [b'127.0.0.1', 7002], [b'127.0.0.1', 7005]]]

            # Missing slot 5460
            link.execute_command = lambda *args: bad_slots_resp

            return link

        s.get_redis_link_from_node = new_get_link_from_node

        with pytest.raises(RedisClusterException) as ex:
            s.initialize_slots_cache()

        assert unicode(ex.value).startswith("All slots are not covered after querry all startup_nodes."), True

    def test_init_slots_cache_slots_collision(self):
        """
        Test that if 2 nodes do not agree on the same slots setup it should raise an error.
        In this test both nodes will say that the first slots block should be bound to different
         servers.
        """
        s = _get_client(init_slot_cache=False, startup_nodes=[{"host": "127.0.0.1", "port": "7000"}, {"host": "127.0.0.1", "port": "7001"}])

        old_get_link_from_node = s.get_redis_link_from_node

        node_1 = old_get_link_from_node({"host": "127.0.0.1", "port": "7000"})
        node_2 = old_get_link_from_node({"host": "127.0.0.1", "port": "7001"})

        node_1_slots = [[0, 5460, [b'127.0.0.1', 7000], [b'127.0.0.1', 7003]],
                        [5461, 10922, [b'127.0.0.1', 7001], [b'127.0.0.1', 7004]]]

        node_2_slots = [[0, 5460, [b'127.0.0.1', 7001], [b'127.0.0.1', 7003]],
                        [5461, 10922, [b'127.0.0.1', 7000], [b'127.0.0.1', 7004]]]

        node_1.execute_command = lambda *args: node_1_slots
        node_2.execute_command = lambda *args: node_2_slots

        def new_get_link_from_node(node):
            # TODO: This seem like a bug that we have to exclude 'name' in first use but not in second use.
            if node == {"host": "127.0.0.1", "port": "7000"}:  # , 'name': '127.0.0.1:7000'}:
                return node_1
            elif node == {"host": "127.0.0.1", "port": "7001", 'name': '127.0.0.1:7001'}:
                return node_2
            else:
                raise Exception("Foo")

        s.get_redis_link_from_node = new_get_link_from_node

        with pytest.raises(RedisClusterException) as ex:
            s.initialize_slots_cache()

        assert unicode(ex.value).startswith("startup_nodes could not agree on a valid slots cache."), True

    def test_empty_startup_nodes(self, s):
        """
        Test that exception is raised when empty providing empty startup_nodes
        """
        with pytest.raises(RedisClusterException) as ex:
            _get_client(init_slot_cache=False, startup_nodes=[])

        assert unicode(ex.value).startswith("No startup nodes provided"), True

    def test_flush_slots_cache(self, r):
        """
        Slots cache should already be populated.
        """
        assert len(r.slots) == r.RedisClusterHashSlots
        r.flush_slots_cache()
        assert len(r.slots) == 0

    def test_close_existing_connection(self):
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

    def test_get_connection_by_key(self, r):
        """
        This test assumes that when hashing key 'foo' will be sent to server with port 7002
        """
        connection = r.get_connection_by_key("foo")
        assert connection.connection_pool.connection_kwargs["port"] == 7002

        with pytest.raises(RedisClusterException) as ex:
            r.get_connection_by_key(None)

        assert unicode(ex.value).startswith("No way to dispatch this command to Redis Cluster."), True

    def test_blocked_commands(self, r):
        """
        These commands should be blocked and raise RedisClusterException
        """
        methods = {
            "client_setname": r.client_setname,
            "sentinel": r.sentinel,
            "sentinel_get_master_addr_by_name": r.sentinel_get_master_addr_by_name,
            "sentinel_master": r.sentinel_master,
            "sentinel_masters": r.sentinel_masters,
            "sentinel_monitor": r.sentinel_monitor,
            "sentinel_remove": r.sentinel_remove,
            "sentinel_sentinels": r.sentinel_sentinels,
            "sentinel_set": r.sentinel_set,
            "sentinel_slaves": r.sentinel_slaves,
            "shutdown": r.shutdown,
            "slaveof": r.slaveof,
            "watch": r.watch,
            "unwatch": r.unwatch,
            "move": r.move,
            "bitop": r.bitop,
        }

        for key, method in methods.items():
            try:
                method()
            except RedisClusterException:
                pass
            else:
                raise AssertionError("'RedisClusterException' not raised for method : {}".format(key))

    def test_connection_error(self, r):
        execute_command_via_connection_original = r.execute_command_via_connection
        test = self
        test.execute_command_calls = []

        def execute_command_via_connection(r, *argv, **kwargs):
            # the first time this is called, simulate an ASK exception.
            # after that behave normally.
            # capture all the requests and responses.
            if not test.execute_command_calls:
                e = redis.ConnectionError('FAKE: could not connect')
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

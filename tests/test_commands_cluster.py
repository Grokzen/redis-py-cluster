# -*- coding: utf-8 -*-

# python std lib
from __future__ import unicode_literals
import datetime

# rediscluster imports
import rediscluster
from rediscluster.exceptions import RedisClusterException
from rediscluster.utils import dict_merge
from .conftest import (
    skip_if_server_version_lt,
    skip_if_redis_py_version_lt,
    skip_if_server_version_gte,
    skip_for_no_cluster_impl,
    skip_unless_arch_bits,
    REDIS_6_VERSION,
)

# 3rd party imports
import pytest
from redis.exceptions import RedisError
from redis import exceptions


def redis_server_time(client):
    all_clients_time = client.time()
    for server_id, server_time_data in all_clients_time.items():
        if '7000' in server_id:
            seconds, milliseconds = server_time_data

    timestamp = float('%s.%s' % (seconds, milliseconds))
    return datetime.datetime.fromtimestamp(timestamp)


def get_main_cluster_node_data(command_result):
    """
    Tries to find whatever node is running on port :7000 in the cluster resonse
    """
    for node_id, node_data in command_result.items():
        if '7000' in node_id:
            return node_data
    return None


# RESPONSE CALLBACKS
class TestResponseCallbacksCluster(object):
    "Tests for the response callback system"

    def test_response_callbacks(self, r):
        all_response_callbacks = dict_merge(
            rediscluster.RedisCluster.RESPONSE_CALLBACKS,
            rediscluster.RedisCluster.CLUSTER_COMMANDS_RESPONSE_CALLBACKS,
        )

        assert r.response_callbacks == all_response_callbacks
        assert id(r.response_callbacks) != id(all_response_callbacks)
        r.set_response_callback('GET', lambda x: 'static')
        r['a'] = 'foo'
        assert r['a'] == 'static'


class TestRedisCommandsCluster(object):

    # SERVER INFORMATION
    def test_client_list(self, r):
        clients = r.client_list()
        client_data = get_main_cluster_node_data(clients)[0]
        assert isinstance(client_data, dict)
        assert 'addr' in client_data

    @skip_if_server_version_lt('5.0.0')
    def test_client_list_type(self, r):
        with pytest.raises(exceptions.RedisError):
            r.client_list(_type='not a client type')
        for client_type in ['normal', 'master', 'replica', 'pubsub']:
            clients = get_main_cluster_node_data(r.client_list(_type=client_type))
            assert isinstance(clients, list)

    @skip_if_server_version_lt('5.0.0')
    def test_client_id(self, r):
        assert get_main_cluster_node_data(r.client_id()) > 0

    @skip_if_server_version_lt('5.0.0')
    def test_client_unblock(self, r):
        myid = get_main_cluster_node_data(r.client_id())
        assert not r.client_unblock(myid)
        assert not r.client_unblock(myid, error=True)
        assert not r.client_unblock(myid, error=False)

    @skip_if_server_version_lt('2.6.9')
    def test_client_getname(self, r):
        assert get_main_cluster_node_data(r.client_getname()) is None

    def test_config_get(self, r):
        data = get_main_cluster_node_data(r.config_get())
        assert 'maxmemory' in data
        assert data['maxmemory'].isdigit()

    def test_config_resetstat(self, r):
        r.ping()
        prior_commands_processed = int(get_main_cluster_node_data(r.info())['total_commands_processed'])
        assert prior_commands_processed >= 1
        r.config_resetstat()
        reset_commands_processed = int(get_main_cluster_node_data(r.info())['total_commands_processed'])
        assert reset_commands_processed < prior_commands_processed

    def test_config_set(self, r):
        data = get_main_cluster_node_data(r.config_get())
        rdbname = data['dbfilename']
        try:
            assert r.config_set('dbfilename', 'redis_py_test.rdb')
            assert get_main_cluster_node_data(r.config_get())['dbfilename'] == 'redis_py_test.rdb'
        finally:
            assert r.config_set('dbfilename', rdbname)

    def test_dbsize(self, r):
        r['a'] = 'foo'
        r['b'] = 'bar'
        # Count all commands sent to the DB. Since we have one slave
        # for every master we will look for 4 and not 2
        dbsize_sum = sum([db_size_count for node_id, db_size_count in r.dbsize().items()])
        assert dbsize_sum == 4

    def test_echo(self, r):
        assert get_main_cluster_node_data(r.echo('foo bar')) == b'foo bar'

    def test_info(self, r):
        r['a'] = 'foo'
        r['b'] = 'bar'
        info = get_main_cluster_node_data(r.info())
        assert isinstance(info, dict)
        # We only have a "db0" in cluster mode and only one of the commands will bind to node :7000
        assert info['db0']['keys'] == 1
        # Sum all keys in all slots
        keys_sum = sum([node_data.get('db0', {}).get('keys', 0) for node_id, node_data in r.info().items()])
        assert keys_sum == 4

    def test_lastsave(self, r):
        assert isinstance(get_main_cluster_node_data(r.lastsave()), datetime.datetime)

    @skip_if_server_version_lt('2.6.0')
    def test_time(self, r):
        t = get_main_cluster_node_data(r.time())
        assert len(t) == 2
        assert isinstance(t[0], int)
        assert isinstance(t[1], int)

    # FIXME: Move this method to a more generic solution/method that tests the blocked nodes flags feature
    def test_bitop_not_supported(self, r):
        """
        Validate that the command is blocked in cluster mode and throws an Exception
        """
        r['a'] = ''
        with pytest.raises(RedisClusterException):
            r.bitop('not', 'r', 'a')

    def test_exists(self, r):
        """
        Keys need to be in specific slots to work out
        """
        assert r.exists('a') == 0
        r['G0B96'] = 'foo'
        r['TEFX5'] = 'bar'
        assert r.exists('G0B96') == 1
        assert r.exists('G0B96', 'TEFX5') == 2

    def test_blpop(self, r):
        """
        Generated keys for slot
            16299: ['0J8KD', '822JO', '8TJPT', 'HD644', 'SKUCM', 'N4N5Z', 'NRSWJ']
        """
        r.rpush('0J8KD', '1', '2')
        r.rpush('822JO', '3', '4')
        assert r.blpop(['822JO', '0J8KD'], timeout=1) == (b'822JO', b'3')
        assert r.blpop(['822JO', '0J8KD'], timeout=1) == (b'822JO', b'4')
        assert r.blpop(['822JO', '0J8KD'], timeout=1) == (b'0J8KD', b'1')
        assert r.blpop(['822JO', '0J8KD'], timeout=1) == (b'0J8KD', b'2')
        assert r.blpop(['822JO', '0J8KD'], timeout=1) is None
        r.rpush('c', '1')
        assert r.blpop('c', timeout=1) == (b'c', b'1')

    def test_brpop(self, r):
        """
        Generated keys for slot
            16299: ['0J8KD', '822JO', '8TJPT', 'HD644', 'SKUCM', 'N4N5Z', 'NRSWJ']
        """
        r.rpush('0J8KD', '1', '2')
        r.rpush('822JO', '3', '4')
        assert r.brpop(['822JO', '0J8KD'], timeout=1) == (b'822JO', b'4')
        assert r.brpop(['822JO', '0J8KD'], timeout=1) == (b'822JO', b'3')
        assert r.brpop(['822JO', '0J8KD'], timeout=1) == (b'0J8KD', b'2')
        assert r.brpop(['822JO', '0J8KD'], timeout=1) == (b'0J8KD', b'1')
        assert r.brpop(['822JO', '0J8KD'], timeout=1) is None
        r.rpush('c', '1')
        assert r.brpop('c', timeout=1) == (b'c', b'1')

    @skip_if_server_version_lt('2.8.0')
    def test_scan(self, r):
        """
        Test is adapted for a same slot scenario in a clustered environment.

        FIXME: Add test for cross slot functionality test

        Generated keys for slot
            0 : ['GQ5KU', 'IFWJL', 'X582D']
        """
        r.set('GQ5KU', 1)
        r.set('IFWJL', 2)
        r.set('X582D', 3)
        cursor, keys = get_main_cluster_node_data(r.scan())
        assert cursor == 0
        assert set(keys) == {b'GQ5KU', b'IFWJL', b'X582D'}
        _, keys = get_main_cluster_node_data(r.scan(match='GQ5KU'))
        assert set(keys) == {b'GQ5KU'}

    @skip_if_server_version_lt(REDIS_6_VERSION)
    def test_scan_type(self, r):
        """
        Test is adapted for a same slot scenario in a clustered environment.

        FIXME: Add test for cross slot functionality test

        Generated keys for slot
            0 : ['GQ5KU', 'IFWJL', 'X582D']
        """
        r.sadd('GQ5KU', 1)
        r.hset('IFWJL', 'foo', 2)
        r.lpush('X582D', 'aux', 3)
        _, keys = get_main_cluster_node_data(r.scan(match='G*', _type='SET'))
        assert set(keys) == {b'GQ5KU'}

    def test_zadd_incr_with_xx(self, r):
        """
        Generated keys for slot
            0 : ['60ZE7', '8I2EQ', 'R8H1V', 'NJP6N', '0VI0A', '0CEIC', 'MV75A', 'TMKD9']
        """
        # this asks zadd to incr 'a1' only if it exists, but it clearly
        # doesn't. Redis returns a null value in this case and so should
        # redis-py
        assert r.zadd('a', {'a1': 1}, xx=True, incr=True) is None

    def test_zinterstore_sum(self, r):
        """
        Generated keys for slot
            0 : ['60ZE7', '8I2EQ', 'R8H1V', 'NJP6N', '0VI0A', '0CEIC', 'MV75A', 'TMKD9']
        """
        r.zadd('60ZE7', {'a1': 1, 'a2': 1, 'a3': 1})
        r.zadd('8I2EQ', {'a1': 2, 'a2': 2, 'a3': 2})
        r.zadd('R8H1V', {'a1': 6, 'a3': 5, 'a4': 4})
        assert r.zinterstore('NJP6N', ['60ZE7', '8I2EQ', 'R8H1V']) == 2
        assert r.zrange('NJP6N', 0, -1, withscores=True) == \
            [(b'a3', 8), (b'a1', 9)]

    def test_zinterstore_max(self, r):
        """
        Generated keys for slot
            0 : ['60ZE7', '8I2EQ', 'R8H1V', 'NJP6N', '0VI0A', '0CEIC', 'MV75A', 'TMKD9']
        """
        r.zadd('60ZE7', {'a1': 1, 'a2': 1, 'a3': 1})
        r.zadd('8I2EQ', {'a1': 2, 'a2': 2, 'a3': 2})
        r.zadd('R8H1V', {'a1': 6, 'a3': 5, 'a4': 4})
        assert r.zinterstore('NJP6N', ['60ZE7', '8I2EQ', 'R8H1V'], aggregate='MAX') == 2
        assert r.zrange('NJP6N', 0, -1, withscores=True) == \
            [(b'a3', 5), (b'a1', 6)]

    def test_zinterstore_min(self, r):
        """
        Generated keys for slot
            0 : ['60ZE7', '8I2EQ', 'R8H1V', 'NJP6N', '0VI0A', '0CEIC', 'MV75A', 'TMKD9']
        """
        r.zadd('60ZE7', {'a1': 1, 'a2': 2, 'a3': 3})
        r.zadd('8I2EQ', {'a1': 2, 'a2': 3, 'a3': 5})
        r.zadd('R8H1V', {'a1': 6, 'a3': 5, 'a4': 4})
        assert r.zinterstore('NJP6N', ['60ZE7', '8I2EQ', 'R8H1V'], aggregate='MIN') == 2
        assert r.zrange('NJP6N', 0, -1, withscores=True) == \
            [(b'a1', 1), (b'a3', 3)]

    def test_zinterstore_with_weight(self, r):
        """
        Generated keys for slot
            0 : ['60ZE7', '8I2EQ', 'R8H1V', 'NJP6N', '0VI0A', '0CEIC', 'MV75A', 'TMKD9']
        """
        r.zadd('60ZE7', {'a1': 1, 'a2': 1, 'a3': 1})
        r.zadd('8I2EQ', {'a1': 2, 'a2': 2, 'a3': 2})
        r.zadd('R8H1V', {'a1': 6, 'a3': 5, 'a4': 4})
        assert r.zinterstore('NJP6N', {'60ZE7': 1, '8I2EQ': 2, 'R8H1V': 3}) == 2
        assert r.zrange('NJP6N', 0, -1, withscores=True) == \
            [(b'a3', 20), (b'a1', 23)]

    @skip_if_server_version_lt('4.9.0')
    def test_zpopmax(self, r):
        """
        Generated keys for slot
            0 : ['60ZE7', '8I2EQ', 'R8H1V', 'NJP6N', '0VI0A', '0CEIC', 'MV75A', 'TMKD9']
        """
        r.zadd('60ZE7', {'a1': 1, 'a2': 2, 'a3': 3})
        assert r.zpopmax('60ZE7') == [(b'a3', 3)]

        # with count
        assert r.zpopmax('60ZE7', count=2) == \
            [(b'a2', 2), (b'a1', 1)]

    @skip_if_server_version_lt('4.9.0')
    def test_zpopmin(self, r):
        """
        Generated keys for slot
            0 : ['60ZE7', '8I2EQ', 'R8H1V', 'NJP6N', '0VI0A', '0CEIC', 'MV75A', 'TMKD9']
        """
        r.zadd('60ZE7', {'a1': 1, 'a2': 2, 'a3': 3})
        assert r.zpopmin('60ZE7') == [(b'a1', 1)]

        # with count
        assert r.zpopmin('60ZE7', count=2) == \
            [(b'a2', 2), (b'a3', 3)]

    def test_zunionstore_sum(self, r):
        """
        Generated keys for slot
            0 : ['60ZE7', '8I2EQ', 'R8H1V', 'NJP6N', '0VI0A', '0CEIC', 'MV75A', 'TMKD9']
        """
        r.zadd('60ZE7', {'a1': 1, 'a2': 1, 'a3': 1})
        r.zadd('8I2EQ', {'a1': 2, 'a2': 2, 'a3': 2})
        r.zadd('R8H1V', {'a1': 6, 'a3': 5, 'a4': 4})
        assert r.zunionstore('NJP6N', ['60ZE7', '8I2EQ', 'R8H1V']) == 4
        assert r.zrange('NJP6N', 0, -1, withscores=True) == \
            [(b'a2', 3), (b'a4', 4), (b'a3', 8), (b'a1', 9)]

    def test_zunionstore_max(self, r):
        """
        Generated keys for slot
            0 : ['60ZE7', '8I2EQ', 'R8H1V', 'NJP6N', '0VI0A', '0CEIC', 'MV75A', 'TMKD9']
        """
        r.zadd('60ZE7', {'a1': 1, 'a2': 1, 'a3': 1})
        r.zadd('8I2EQ', {'a1': 2, 'a2': 2, 'a3': 2})
        r.zadd('R8H1V', {'a1': 6, 'a3': 5, 'a4': 4})
        assert r.zunionstore('NJP6N', ['60ZE7', '8I2EQ', 'R8H1V'], aggregate='MAX') == 4
        assert r.zrange('NJP6N', 0, -1, withscores=True) == \
            [(b'a2', 2), (b'a4', 4), (b'a3', 5), (b'a1', 6)]

    def test_zunionstore_min(self, r):
        """
        Generated keys for slot
            0 : ['60ZE7', '8I2EQ', 'R8H1V', 'NJP6N', '0VI0A', '0CEIC', 'MV75A', 'TMKD9']
        """
        r.zadd('60ZE7', {'a1': 1, 'a2': 2, 'a3': 3})
        r.zadd('8I2EQ', {'a1': 2, 'a2': 2, 'a3': 4})
        r.zadd('R8H1V', {'a1': 6, 'a3': 5, 'a4': 4})
        assert r.zunionstore('NJP6N', ['60ZE7', '8I2EQ', 'R8H1V'], aggregate='MIN') == 4
        assert r.zrange('NJP6N', 0, -1, withscores=True) == \
            [(b'a1', 1), (b'a2', 2), (b'a3', 3), (b'a4', 4)]

    def test_zunionstore_with_weight(self, r):
        """
        Generated keys for slot
            0 : ['60ZE7', '8I2EQ', 'R8H1V', 'NJP6N', '0VI0A', '0CEIC', 'MV75A', 'TMKD9']
        """
        r.zadd('60ZE7', {'a1': 1, 'a2': 1, 'a3': 1})
        r.zadd('8I2EQ', {'a1': 2, 'a2': 2, 'a3': 2})
        r.zadd('R8H1V', {'a1': 6, 'a3': 5, 'a4': 4})
        assert r.zunionstore('NJP6N', {'60ZE7': 1, '8I2EQ': 2, 'R8H1V': 3}) == 4
        assert r.zrange('NJP6N', 0, -1, withscores=True) == \
            [(b'a2', 5), (b'a4', 12), (b'a3', 20), (b'a1', 23)]

    def test_hmset(self, r):
        """
        Warning message is different in a RedisCluster instance
        """
        warning_message = (r'^RedisCluster\.hmset\(\) is deprecated\. '
                           r'Use RedisCluster\.hset\(\) instead\.$')
        h = {b'a': b'1', b'b': b'2', b'c': b'3'}
        with pytest.warns(DeprecationWarning, match=warning_message):
            assert r.hmset('a', h)
        assert r.hgetall('a') == h

    def test_sort_store(self, r):
        """
        Generated keys for slot
            0 : ['60ZE7', '8I2EQ', 'R8H1V', 'NJP6N', '0VI0A', '0CEIC', 'MV75A', 'TMKD9']
        """
        r.rpush('60ZE7', '2', '3', '1')
        assert r.sort('60ZE7', store='8I2EQ') == 3
        assert r.lrange('8I2EQ', 0, -1) == [b'1', b'2', b'3']

    @skip_if_server_version_lt('3.2.0')
    def test_georadius_store(self, r):
        """
        Generated keys for slot
            0 : ['60ZE7', '8I2EQ']
        """
        values = (2.1909389952632, 41.433791470673, 'place1') +\
                 (2.1873744593677, 41.406342043777, 'place2')

        r.geoadd('60ZE7', *values)
        r.georadius('60ZE7', 2.191, 41.433, 1000, store='8I2EQ')
        assert r.zrange('8I2EQ', 0, -1) == [b'place1']

    @skip_if_server_version_lt('3.2.0')
    def test_georadius_store_dist(self, r):
        """
        Generated keys for slot
            0 : ['60ZE7', '8I2EQ']
        """
        values = (2.1909389952632, 41.433791470673, 'place1') +\
                 (2.1873744593677, 41.406342043777, 'place2')

        r.geoadd('60ZE7', *values)
        r.georadius('60ZE7', 2.191, 41.433, 1000,
                    store_dist='8I2EQ')
        # instead of save the geo score, the distance is saved.
        assert r.zscore('8I2EQ', 'place1') == 88.05060698409301

    @pytest.mark.skip(reason="Sort works if done against keys in same slot")
    def test_sort_by(self, r):
        r['score:1'] = 8
        r['score:2'] = 3
        r['score:3'] = 5
        r.rpush('a', '3', '2', '1')
        assert r.sort('a', by='score:*') == [b'2', b'3', b'1']

    @pytest.mark.skip(reason="Sort works if done against keys in same slot")
    def test_sort_get(self, r):
        r['user:1'] = 'u1'
        r['user:2'] = 'u2'
        r['user:3'] = 'u3'
        r.rpush('a', '2', '3', '1')
        assert r.sort('a', get='user:*') == [b'u1', b'u2', b'u3']

    @pytest.mark.skip(reason="Sort works if done against keys in same slot")
    def test_sort_get_multi(self, r):
        r['user:1'] = 'u1'
        r['user:2'] = 'u2'
        r['user:3'] = 'u3'
        r.rpush('a', '2', '3', '1')
        assert r.sort('a', get=('user:*', '#')) == \
            [b'u1', b'1', b'u2', b'2', b'u3', b'3']

    @pytest.mark.skip(reason="Sort works if done against keys in same slot")
    def test_sort_get_groups_two(self, r):
        r['user:1'] = 'u1'
        r['user:2'] = 'u2'
        r['user:3'] = 'u3'
        r.rpush('a', '2', '3', '1')
        assert r.sort('a', get=('user:*', '#'), groups=True) == \
            [(b'u1', b'1'), (b'u2', b'2'), (b'u3', b'3')]

    @pytest.mark.skip(reason="Sort works if done against keys in same slot")
    def test_sort_groups_three_gets(self, r):
        r['user:1'] = 'u1'
        r['user:2'] = 'u2'
        r['user:3'] = 'u3'
        r['door:1'] = 'd1'
        r['door:2'] = 'd2'
        r['door:3'] = 'd3'
        r.rpush('a', '2', '3', '1')
        assert r.sort('a', get=('user:*', 'door:*', '#'), groups=True) == [
            (b'u1', b'd1', b'1'),
            (b'u2', b'd2', b'2'),
            (b'u3', b'd3', b'3')
        ]

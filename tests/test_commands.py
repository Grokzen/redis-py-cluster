# -*- coding: utf-8 -*-

# python std lib
from __future__ import with_statement
import datetime
import re
import time

# rediscluster imports
from rediscluster.exceptions import RedisClusterException
from tests.conftest import skip_if_server_version_lt, skip_if_redis_py_version_lt

# 3rd party imports
import pytest
from redis._compat import unichr, u, b, ascii_letters, iteritems, iterkeys, itervalues, unicode
from redis.client import parse_info
from redis.exceptions import ResponseError, DataError, RedisError


pytestmark = skip_if_server_version_lt('2.9.0')


def redis_server_time(client):
    seconds, milliseconds = list(client.time().values())[0]
    timestamp = float('{0}.{1}'.format(seconds, milliseconds))
    return datetime.datetime.fromtimestamp(timestamp)


class TestRedisCommands(object):

    @skip_if_server_version_lt('2.9.9')
    def test_zrevrangebylex(self, r):
        r.zadd('a', a=0, b=0, c=0, d=0, e=0, f=0, g=0)
        assert r.zrevrangebylex('a', '[c', '-') == [b('c'), b('b'), b('a')]
        assert r.zrevrangebylex('a', '(c', '-') == [b('b'), b('a')]
        assert r.zrevrangebylex('a', '(g', '[aaa') == \
            [b('f'), b('e'), b('d'), b('c'), b('b')]
        assert r.zrevrangebylex('a', '+', '[f') == [b('g'), b('f')]
        assert r.zrevrangebylex('a', '+', '-', start=3, num=2) == \
            [b('d'), b('c')]

    def test_command_on_invalid_key_type(self, r):
        r.lpush('a', '1')
        with pytest.raises(ResponseError):
            r['a']

    # SERVER INFORMATION
    def test_client_list(self, r):
        for server, clients in r.client_list().items():
            assert isinstance(clients[0], dict)
            assert 'addr' in clients[0]

    def test_client_getname(self, r):
        for server, name in r.client_getname().items():
            assert name is None

    def test_client_setname(self, r):
        with pytest.raises(RedisClusterException):
            assert r.client_setname('redis_py_test')

    def test_config_get(self, r):
        for server, data in r.config_get().items():
            assert 'maxmemory' in data
            assert data['maxmemory'].isdigit()

    def test_config_resetstat(self, r):
        r.ping()
        for server, info in r.info().items():
            prior_commands_processed = int(info['total_commands_processed'])
            assert prior_commands_processed >= 1
        r.config_resetstat()
        for server, info in r.info().items():
            reset_commands_processed = int(info['total_commands_processed'])
            assert reset_commands_processed < prior_commands_processed

    def test_config_set(self, r):
        assert r.config_set('dbfilename', 'redis_py_test.rdb')
        for server, config in r.config_get().items():
            assert config['dbfilename'] == 'redis_py_test.rdb'

    def test_echo(self, r):
        for server, res in r.echo('foo bar').items():
            assert res == b('foo bar')

    def test_object(self, r):
        r['a'] = 'foo'
        assert isinstance(r.object('refcount', 'a'), int)
        assert isinstance(r.object('idletime', 'a'), int)
        assert r.object('encoding', 'a') in (b('raw'), b('embstr'))
        assert r.object('idletime', 'invalid-key') is None

    def test_ping(self, r):
        assert r.ping()

    def test_time(self, r):
        for t in r.time().values():
            assert len(t) == 2
            assert isinstance(t[0], int)
            assert isinstance(t[1], int)

    # BASIC KEY COMMANDS
    def test_append(self, r):
        assert r.append('a', 'a1') == 2
        assert r['a'] == b('a1')
        assert r.append('a', 'a2') == 4
        assert r['a'] == b('a1a2')

    def test_bitcount(self, r):
        r.setbit('a', 5, True)
        assert r.bitcount('a') == 1
        r.setbit('a', 6, True)
        assert r.bitcount('a') == 2
        r.setbit('a', 5, False)
        assert r.bitcount('a') == 1
        r.setbit('a', 9, True)
        r.setbit('a', 17, True)
        r.setbit('a', 25, True)
        r.setbit('a', 33, True)
        assert r.bitcount('a') == 5
        assert r.bitcount('a', 0, -1) == 5
        assert r.bitcount('a', 2, 3) == 2
        assert r.bitcount('a', 2, -1) == 3
        assert r.bitcount('a', -2, -1) == 2
        assert r.bitcount('a', 1, 1) == 1

    def test_bitop_not_supported(self, r):
        r['a'] = ''
        with pytest.raises(RedisClusterException):
            r.bitop('not', 'r', 'a')

    @skip_if_server_version_lt('2.8.7')
    @skip_if_redis_py_version_lt("2.10.2")
    def test_bitpos(self, r):
        """
        Bitpos was added in redis-py in version 2.10.2

        # TODO: Added b() around keys but i think they should not have to be
                there for this command to work properly.
        """
        key = 'key:bitpos'
        r.set(key, b('\xff\xf0\x00'))
        assert r.bitpos(key, 0) == 12
        assert r.bitpos(key, 0, 2, -1) == 16
        assert r.bitpos(key, 0, -2, -1) == 12
        r.set(key, b('\x00\xff\xf0'))
        assert r.bitpos(key, 1, 0) == 8
        assert r.bitpos(key, 1, 1) == 8
        r.set(key, '\x00\x00\x00')
        assert r.bitpos(key, 1) == -1

    @skip_if_server_version_lt('2.8.7')
    @skip_if_redis_py_version_lt("2.10.2")
    def test_bitpos_wrong_arguments(self, r):
        """
        Bitpos was added in redis-py in version 2.10.2
        """
        key = 'key:bitpos:wrong:args'
        r.set(key, b('\xff\xf0\x00'))
        with pytest.raises(RedisError):
            r.bitpos(key, 0, end=1) == 12
        with pytest.raises(RedisError):
            r.bitpos(key, 7) == 12

    def test_decr(self, r):
        assert r.decr('a') == -1
        assert r['a'] == b('-1')
        assert r.decr('a') == -2
        assert r['a'] == b('-2')
        assert r.decr('a', amount=5) == -7
        assert r['a'] == b('-7')

    def test_delete(self, r):
        assert r.delete('a') == 0
        r['a'] = 'foo'
        assert r.delete('a') == 1

    def test_delete_with_multiple_keys(self, r):
        r['a'] = 'foo'
        r['b'] = 'bar'
        assert r.delete('a', 'b') == 2
        assert r.get('a') is None
        assert r.get('b') is None

    def test_delitem(self, r):
        r['a'] = 'foo'
        del r['a']
        assert r.get('a') is None

    def test_dump_and_restore(self, r):
        r['a'] = 'foo'
        dumped = r.dump('a')
        del r['a']
        r.restore('a', 0, dumped)
        assert r['a'] == b('foo')

    def test_exists(self, r):
        assert not r.exists('a')
        r['a'] = 'foo'
        assert r.exists('a')

    def test_exists_contains(self, r):
        assert 'a' not in r
        r['a'] = 'foo'
        assert 'a' in r

    def test_expire(self, r):
        assert not r.expire('a', 10)
        r['a'] = 'foo'
        assert r.expire('a', 10)
        assert 0 < r.ttl('a') <= 10
        assert r.persist('a')
        # the ttl command changes behavior in redis-2.8+ http://redis.io/commands/ttl
        assert r.ttl('a') == -1

    def test_expireat_datetime(self, r):
        expire_at = redis_server_time(r) + datetime.timedelta(minutes=1)
        r['a'] = 'foo'
        assert r.expireat('a', expire_at)
        assert 0 < r.ttl('a') <= 61

    def test_expireat_no_key(self, r):
        expire_at = redis_server_time(r) + datetime.timedelta(minutes=1)
        assert not r.expireat('a', expire_at)

    def test_expireat_unixtime(self, r):
        expire_at = redis_server_time(r) + datetime.timedelta(minutes=1)
        r['a'] = 'foo'
        expire_at_seconds = int(time.mktime(expire_at.timetuple()))
        assert r.expireat('a', expire_at_seconds)
        assert 0 < r.ttl('a') <= 61

    def test_get_and_set(self, r):
        # get and set can't be tested independently of each other
        assert r.get('a') is None
        byte_string = b('value')
        integer = 5
        unicode_string = unichr(3456) + u('abcd') + unichr(3421)
        assert r.set('byte_string', byte_string)
        assert r.set('integer', 5)
        assert r.set('unicode_string', unicode_string)
        assert r.get('byte_string') == byte_string
        assert r.get('integer') == b(str(integer))
        assert r.get('unicode_string').decode('utf-8') == unicode_string

    def test_getitem_and_setitem(self, r):
        r['a'] = 'bar'
        assert r['a'] == b('bar')

    def test_getitem_raises_keyerror_for_missing_key(self, r):
        with pytest.raises(KeyError):
            r['a']

    def test_get_set_bit(self, r):
        # no value
        assert not r.getbit('a', 5)
        # set bit 5
        assert not r.setbit('a', 5, True)
        assert r.getbit('a', 5)
        # unset bit 4
        assert not r.setbit('a', 4, False)
        assert not r.getbit('a', 4)
        # set bit 4
        assert not r.setbit('a', 4, True)
        assert r.getbit('a', 4)
        # set bit 5 again
        assert r.setbit('a', 5, True)
        assert r.getbit('a', 5)

    def test_getrange(self, r):
        r['a'] = 'foo'
        assert r.getrange('a', 0, 0) == b('f')
        assert r.getrange('a', 0, 2) == b('foo')
        assert r.getrange('a', 3, 4) == b('')

    def test_getset(self, r):
        assert r.getset('a', 'foo') is None
        assert r.getset('a', 'bar') == b('foo')
        assert r.get('a') == b('bar')

    def test_incr(self, r):
        assert r.incr('a') == 1
        assert r['a'] == b('1')
        assert r.incr('a') == 2
        assert r['a'] == b('2')
        assert r.incr('a', amount=5) == 7
        assert r['a'] == b('7')

    def test_incrby(self, r):
        assert r.incrby('a') == 1
        assert r.incrby('a', 4) == 5
        assert r['a'] == b('5')

    def test_incrbyfloat(self, r):
        assert r.incrbyfloat('a') == 1.0
        assert r['a'] == b('1')
        assert r.incrbyfloat('a', 1.1) == 2.1
        assert float(r['a']) == float(2.1)

    def test_keys(self, r):
        keys = r.keys()
        assert keys == []
        keys_with_underscores = set(['test_a', 'test_b'])
        keys = keys_with_underscores.union(set(['testc']))
        for key in keys:
            r[key] = 1
        assert set(r.keys(pattern='test_*')) == {b(k) for k in keys_with_underscores}
        assert set(r.keys(pattern='test*')) == {b(k) for k in keys}

    def test_mget(self, r):
        assert r.mget(['a', 'b']) == [None, None]
        r['a'] = '1'
        r['b'] = '2'
        r['c'] = '3'
        assert r.mget('a', 'other', 'b', 'c') == [b('1'), None, b('2'), b('3')]

    def test_mset(self, r):
        d = {'a': b('1'), 'b': b('2'), 'c': b('3')}
        assert r.mset(d)
        for k, v in iteritems(d):
            assert r[k] == v

    def test_mset_kwargs(self, r):
        d = {'a': b('1'), 'b': b('2'), 'c': b('3')}
        assert r.mset(**d)
        for k, v in iteritems(d):
            assert r[k] == v

    def test_msetnx(self, r):
        d = {'a': b('1'), 'b': b('2'), 'c': b('3')}
        assert r.msetnx(d)
        d2 = {'a': b('x'), 'd': b('4')}
        assert not r.msetnx(d2)
        for k, v in iteritems(d):
            assert r[k] == v
        assert r.get('d') is None

    def test_msetnx_kwargs(self, r):
        d = {'a': b('1'), 'b': b('2'), 'c': b('3')}
        assert r.msetnx(**d)
        d2 = {'a': b('x'), 'd': b('4')}
        assert not r.msetnx(**d2)
        for k, v in iteritems(d):
            assert r[k] == v
        assert r.get('d') is None

    def test_pexpire(self, r):
        assert not r.pexpire('a', 60000)
        r['a'] = 'foo'
        assert r.pexpire('a', 60000)
        assert 0 < r.pttl('a') <= 60000
        assert r.persist('a')
        # redis-py tests seemed to be for older version of redis?
        # redis-2.8+ returns -1 if key exists but is non-expiring: http://redis.io/commands/pttl
        assert r.pttl('a') == -1

    def test_pexpireat_datetime(self, r):
        expire_at = redis_server_time(r) + datetime.timedelta(minutes=1)
        r['a'] = 'foo'
        assert r.pexpireat('a', expire_at)
        assert 0 < r.pttl('a') <= 61000

    def test_pexpireat_no_key(self, r):
        expire_at = redis_server_time(r) + datetime.timedelta(minutes=1)
        assert not r.pexpireat('a', expire_at)

    def test_pexpireat_unixtime(self, r):
        expire_at = redis_server_time(r) + datetime.timedelta(minutes=1)
        r['a'] = 'foo'
        expire_at_seconds = int(time.mktime(expire_at.timetuple())) * 1000
        assert r.pexpireat('a', expire_at_seconds)
        assert 0 < r.pttl('a') <= 61000

    def test_psetex(self, r):
        assert r.psetex('a', 1000, 'value')
        assert r['a'] == b('value')
        assert 0 < r.pttl('a') <= 1000

    def test_psetex_timedelta(self, r):
        expire_at = datetime.timedelta(milliseconds=1000)
        assert r.psetex('a', expire_at, 'value')
        assert r['a'] == b('value')
        assert 0 < r.pttl('a') <= 1000

    def test_randomkey(self, r):
        assert r.randomkey() is None
        for key in ('a', 'b', 'c'):
            r[key] = 1
        assert r.randomkey() in (b('a'), b('b'), b('c'))

    def test_rename(self, r):
        r['a'] = '1'
        assert r.rename('a', 'b')
        assert r.get('a') is None
        assert r['b'] == b('1')

        with pytest.raises(ResponseError) as ex:
            r.rename("foo", "foo")
        assert unicode(ex.value).startswith("source and destination objects are the same")

        assert r.get("foo") is None
        with pytest.raises(ResponseError) as ex:
            r.rename("foo", "bar")
        assert unicode(ex.value).startswith("no such key")

    def test_renamenx(self, r):
        r['a'] = '1'
        r['b'] = '2'
        assert not r.renamenx('a', 'b')
        assert r['a'] == b('1')
        assert r['b'] == b('2')

        assert r.renamenx('a', 'c')
        assert r['c'] == b('1')

    def test_set_nx(self, r):
        assert r.set('a', '1', nx=True)
        assert not r.set('a', '2', nx=True)
        assert r['a'] == b('1')

    def test_set_xx(self, r):
        assert not r.set('a', '1', xx=True)
        assert r.get('a') is None
        r['a'] = 'bar'
        assert r.set('a', '2', xx=True)
        assert r.get('a') == b('2')

    def test_set_px(self, r):
        assert r.set('a', '1', px=10000)
        assert r['a'] == b('1')
        assert 0 < r.pttl('a') <= 10000
        assert 0 < r.ttl('a') <= 10

    def test_set_px_timedelta(self, r):
        expire_at = datetime.timedelta(milliseconds=1000)
        assert r.set('a', '1', px=expire_at)
        assert 0 < r.pttl('a') <= 1000
        assert 0 < r.ttl('a') <= 1

    def test_set_ex(self, r):
        assert r.set('a', '1', ex=10)
        assert 0 < r.ttl('a') <= 10

    def test_set_ex_timedelta(self, r):
        expire_at = datetime.timedelta(seconds=60)
        assert r.set('a', '1', ex=expire_at)
        assert 0 < r.ttl('a') <= 60

    def test_set_multipleoptions(self, r):
        r['a'] = 'val'
        assert r.set('a', '1', xx=True, px=10000)
        assert 0 < r.ttl('a') <= 10

    def test_setex(self, r):
        assert r.setex('a', 60, '1')
        assert r['a'] == b('1')
        assert 0 < r.ttl('a') <= 60

    def test_setnx(self, r):
        assert r.setnx('a', '1')
        assert r['a'] == b('1')
        assert not r.setnx('a', '2')
        assert r['a'] == b('1')

    def test_setrange(self, r):
        assert r.setrange('a', 5, 'foo') == 8
        assert r['a'] == b('\0\0\0\0\0foo')
        r['a'] = 'abcdefghijh'
        assert r.setrange('a', 6, '12345') == 11
        assert r['a'] == b('abcdef12345')

    def test_strlen(self, r):
        r['a'] = 'foo'
        assert r.strlen('a') == 3

    def test_substr(self, r):
        r['a'] = '0123456789'
        assert r.substr('a', 0) == b('0123456789')
        assert r.substr('a', 2) == b('23456789')
        assert r.substr('a', 3, 5) == b('345')
        assert r.substr('a', 3, -2) == b('345678')

    def test_type(self, r):
        assert r.type('a') == b('none')
        r['a'] = '1'
        assert r.type('a') == b('string')
        del r['a']
        r.lpush('a', '1')
        assert r.type('a') == b('list')
        del r['a']
        r.sadd('a', '1')
        assert r.type('a') == b('set')
        del r['a']
        r.zadd('a', **{'1': 1})
        assert r.type('a') == b('zset')

    # LIST COMMANDS
    def test_blpop(self, r):
        r.rpush('a{foo}', '1', '2')
        r.rpush('b{foo}', '3', '4')
        assert r.blpop(['b{foo}', 'a{foo}'], timeout=1) == (b('b{foo}'), b('3'))
        assert r.blpop(['b{foo}', 'a{foo}'], timeout=1) == (b('b{foo}'), b('4'))
        assert r.blpop(['b{foo}', 'a{foo}'], timeout=1) == (b('a{foo}'), b('1'))
        assert r.blpop(['b{foo}', 'a{foo}'], timeout=1) == (b('a{foo}'), b('2'))
        assert r.blpop(['b{foo}', 'a{foo}'], timeout=1) is None
        r.rpush('c{foo}', '1')
        assert r.blpop('c{foo}', timeout=1) == (b('c{foo}'), b('1'))

    def test_brpop(self, r):
        r.rpush('a{foo}', '1', '2')
        r.rpush('b{foo}', '3', '4')
        assert r.brpop(['b{foo}', 'a{foo}'], timeout=1) == (b('b{foo}'), b('4'))
        assert r.brpop(['b{foo}', 'a{foo}'], timeout=1) == (b('b{foo}'), b('3'))
        assert r.brpop(['b{foo}', 'a{foo}'], timeout=1) == (b('a{foo}'), b('2'))
        assert r.brpop(['b{foo}', 'a{foo}'], timeout=1) == (b('a{foo}'), b('1'))
        assert r.brpop(['b{foo}', 'a{foo}'], timeout=1) is None
        r.rpush('c{foo}', '1')
        assert r.brpop('c{foo}', timeout=1) == (b('c{foo}'), b('1'))

    def test_brpoplpush(self, r):
        r.rpush('a{foo}', '1', '2')
        r.rpush('b{foo}', '3', '4')
        assert r.brpoplpush('a{foo}', 'b{foo}') == b('2')
        assert r.brpoplpush('a{foo}', 'b{foo}') == b('1')
        assert r.brpoplpush('a{foo}', 'b{foo}', timeout=1) is None
        assert r.lrange('a{foo}', 0, -1) == []
        assert r.lrange('b{foo}', 0, -1) == [b('1'), b('2'), b('3'), b('4')]

    def test_brpoplpush_empty_string(self, r):
        r.rpush('a', '')
        assert r.brpoplpush('a', 'b') == b('')

    def test_lindex(self, r):
        r.rpush('a', '1', '2', '3')
        assert r.lindex('a', '0') == b('1')
        assert r.lindex('a', '1') == b('2')
        assert r.lindex('a', '2') == b('3')

    def test_linsert(self, r):
        r.rpush('a', '1', '2', '3')
        assert r.linsert('a', 'after', '2', '2.5') == 4
        assert r.lrange('a', 0, -1) == [b('1'), b('2'), b('2.5'), b('3')]
        assert r.linsert('a', 'before', '2', '1.5') == 5
        assert r.lrange('a', 0, -1) == \
            [b('1'), b('1.5'), b('2'), b('2.5'), b('3')]

    def test_llen(self, r):
        r.rpush('a', '1', '2', '3')
        assert r.llen('a') == 3

    def test_lpop(self, r):
        r.rpush('a', '1', '2', '3')
        assert r.lpop('a') == b('1')
        assert r.lpop('a') == b('2')
        assert r.lpop('a') == b('3')
        assert r.lpop('a') is None

    def test_lpush(self, r):
        assert r.lpush('a', '1') == 1
        assert r.lpush('a', '2') == 2
        assert r.lpush('a', '3', '4') == 4
        assert r.lrange('a', 0, -1) == [b('4'), b('3'), b('2'), b('1')]

    def test_lpushx(self, r):
        assert r.lpushx('a', '1') == 0
        assert r.lrange('a', 0, -1) == []
        r.rpush('a', '1', '2', '3')
        assert r.lpushx('a', '4') == 4
        assert r.lrange('a', 0, -1) == [b('4'), b('1'), b('2'), b('3')]

    def test_lrange(self, r):
        r.rpush('a', '1', '2', '3', '4', '5')
        assert r.lrange('a', 0, 2) == [b('1'), b('2'), b('3')]
        assert r.lrange('a', 2, 10) == [b('3'), b('4'), b('5')]
        assert r.lrange('a', 0, -1) == [b('1'), b('2'), b('3'), b('4'), b('5')]

    def test_lrem(self, r):
        r.rpush('a', '1', '1', '1', '1')
        assert r.lrem('a', '1', 1) == 1
        assert r.lrange('a', 0, -1) == [b('1'), b('1'), b('1')]
        assert r.lrem('a', 0, '1') == 3
        assert r.lrange('a', 0, -1) == []

    def test_lset(self, r):
        r.rpush('a', '1', '2', '3')
        assert r.lrange('a', 0, -1) == [b('1'), b('2'), b('3')]
        assert r.lset('a', 1, '4')
        assert r.lrange('a', 0, 2) == [b('1'), b('4'), b('3')]

    def test_ltrim(self, r):
        r.rpush('a', '1', '2', '3')
        assert r.ltrim('a', 0, 1)
        assert r.lrange('a', 0, -1) == [b('1'), b('2')]

    def test_rpop(self, r):
        r.rpush('a', '1', '2', '3')
        assert r.rpop('a') == b('3')
        assert r.rpop('a') == b('2')
        assert r.rpop('a') == b('1')
        assert r.rpop('a') is None

    def test_rpoplpush(self, r):
        r.rpush('a', 'a1', 'a2', 'a3')
        r.rpush('b', 'b1', 'b2', 'b3')
        assert r.rpoplpush('a', 'b') == b('a3')
        assert r.lrange('a', 0, -1) == [b('a1'), b('a2')]
        assert r.lrange('b', 0, -1) == [b('a3'), b('b1'), b('b2'), b('b3')]

    def test_rpush(self, r):
        assert r.rpush('a', '1') == 1
        assert r.rpush('a', '2') == 2
        assert r.rpush('a', '3', '4') == 4
        assert r.lrange('a', 0, -1) == [b('1'), b('2'), b('3'), b('4')]

    def test_rpushx(self, r):
        assert r.rpushx('a', 'b') == 0
        assert r.lrange('a', 0, -1) == []
        r.rpush('a', '1', '2', '3')
        assert r.rpushx('a', '4') == 4
        assert r.lrange('a', 0, -1) == [b('1'), b('2'), b('3'), b('4')]

    # SCAN COMMANDS
    def test_scan(self, r):
        r.set('a', 1)
        r.set('b', 2)
        r.set('c', 3)
        keys = []
        for result in r.scan().values():
            cursor, partial_keys = result
            assert cursor == 0
            keys += partial_keys

        assert set(keys) == set([b('a'), b('b'), b('c')])

        keys = []
        for result in r.scan(match='a').values():
            cursor, partial_keys = result
            assert cursor == 0
            keys += partial_keys
        assert set(keys) == set([b('a')])

    def test_scan_iter(self, r):
        alphabet = 'abcdefghijklmnopqrstuvwABCDEFGHIJKLMNOPQRSTUVW'
        for i, c in enumerate(alphabet):
            r.set(c, i)
        keys = list(r.scan_iter())
        expected_result = [b(c) for c in alphabet]
        assert set(keys) == set(expected_result)

        keys = list(r.scan_iter(match='a'))
        assert set(keys) == set([b('a')])

        r.set('Xa', 1)
        r.set('Xb', 2)
        r.set('Xc', 3)
        keys = list(r.scan_iter('X*', count=1000))
        assert len(keys) == 3
        assert set(keys) == set([b('Xa'), b('Xb'), b('Xc')])

    def test_sscan(self, r):
        r.sadd('a', 1, 2, 3)
        cursor, members = r.sscan('a')
        assert cursor == 0
        assert set(members) == set([b('1'), b('2'), b('3')])
        _, members = r.sscan('a', match=b('1'))
        assert set(members) == set([b('1')])

    def test_sscan_iter(self, r):
        r.sadd('a', 1, 2, 3)
        members = list(r.sscan_iter('a'))
        assert set(members) == set([b('1'), b('2'), b('3')])
        members = list(r.sscan_iter('a', match=b('1')))
        assert set(members) == set([b('1')])

    def test_hscan(self, r):
        r.hmset('a', {'a': 1, 'b': 2, 'c': 3})
        cursor, dic = r.hscan('a')
        assert cursor == 0
        assert dic == {b('a'): b('1'), b('b'): b('2'), b('c'): b('3')}
        _, dic = r.hscan('a', match='a')
        assert dic == {b('a'): b('1')}

    def test_hscan_iter(self, r):
        r.hmset('a', {'a': 1, 'b': 2, 'c': 3})
        dic = dict(r.hscan_iter('a'))
        assert dic == {b('a'): b('1'), b('b'): b('2'), b('c'): b('3')}
        dic = dict(r.hscan_iter('a', match='a'))
        assert dic == {b('a'): b('1')}

    def test_zscan(self, r):
        r.zadd('a', 1, 'a', 2, 'b', 3, 'c')
        cursor, pairs = r.zscan('a')
        assert cursor == 0
        assert set(pairs) == set([(b('a'), 1), (b('b'), 2), (b('c'), 3)])
        _, pairs = r.zscan('a', match='a')
        assert set(pairs) == set([(b('a'), 1)])

    def test_zscan_iter(self, r):
        r.zadd('a', 1, 'a', 2, 'b', 3, 'c')
        pairs = list(r.zscan_iter('a'))
        assert set(pairs) == set([(b('a'), 1), (b('b'), 2), (b('c'), 3)])
        pairs = list(r.zscan_iter('a', match='a'))
        assert set(pairs) == set([(b('a'), 1)])

    # SET COMMANDS
    def test_sadd(self, r):
        members = set([b('1'), b('2'), b('3')])
        r.sadd('a', *members)
        assert r.smembers('a') == members

    def test_scard(self, r):
        r.sadd('a', '1', '2', '3')
        assert r.scard('a') == 3

    def test_sdiff(self, r):
        r.sadd('a{foo}', '1', '2', '3')
        assert r.sdiff('a{foo}', 'b{foo}') == set([b('1'), b('2'), b('3')])
        r.sadd('b{foo}', '2', '3')
        assert r.sdiff('a{foo}', 'b{foo}') == set([b('1')])

    def test_sdiffstore(self, r):
        r.sadd('a{foo}', '1', '2', '3')
        assert r.sdiffstore('c{foo}', 'a{foo}', 'b{foo}') == 3
        assert r.smembers('c{foo}') == set([b('1'), b('2'), b('3')])
        r.sadd('b{foo}', '2', '3')
        assert r.sdiffstore('c{foo}', 'a{foo}', 'b{foo}') == 1
        assert r.smembers('c{foo}') == set([b('1')])

        # Diff:s that return empty set should not fail
        r.sdiffstore('d{foo}', 'e{foo}') == 0

    def test_sinter(self, r):
        r.sadd('a{foo}', '1', '2', '3')
        assert r.sinter('a{foo}', 'b{foo}') == set()
        r.sadd('b{foo}', '2', '3')
        assert r.sinter('a{foo}', 'b{foo}') == set([b('2'), b('3')])

    def test_sinterstore(self, r):
        r.sadd('a{foo}', '1', '2', '3')
        assert r.sinterstore('c{foo}', 'a{foo}', 'b{foo}') == 0
        assert r.smembers('c{foo}') == set()
        r.sadd('b{foo}', '2', '3')
        assert r.sinterstore('c{foo}', 'a{foo}', 'b{foo}') == 2
        assert r.smembers('c{foo}') == set([b('2'), b('3')])

    def test_sismember(self, r):
        r.sadd('a', '1', '2', '3')
        assert r.sismember('a', '1')
        assert r.sismember('a', '2')
        assert r.sismember('a', '3')
        assert not r.sismember('a', '4')

    def test_smembers(self, r):
        r.sadd('a', '1', '2', '3')
        assert r.smembers('a') == set([b('1'), b('2'), b('3')])

    def test_smove(self, r):
        r.sadd('a{foo}', 'a1', 'a2')
        r.sadd('b{foo}', 'b1', 'b2')
        assert r.smove('a{foo}', 'b{foo}', 'a1')
        assert r.smembers('a{foo}') == set([b('a2')])
        assert r.smembers('b{foo}') == set([b('b1'), b('b2'), b('a1')])

    def test_spop(self, r):
        s = [b('1'), b('2'), b('3')]
        r.sadd('a', *s)
        value = r.spop('a')
        assert value in s
        assert r.smembers('a') == set(s) - set([value])

    def test_srandmember(self, r):
        s = [b('1'), b('2'), b('3')]
        r.sadd('a', *s)
        assert r.srandmember('a') in s

    def test_srandmember_multi_value(self, r):
        s = [b('1'), b('2'), b('3')]
        r.sadd('a', *s)
        randoms = r.srandmember('a', number=2)
        assert len(randoms) == 2
        assert set(randoms).intersection(s) == set(randoms)

    def test_srem(self, r):
        r.sadd('a', '1', '2', '3', '4')
        assert r.srem('a', '5') == 0
        assert r.srem('a', '2', '4') == 2
        assert r.smembers('a') == set([b('1'), b('3')])

    def test_sunion(self, r):
        r.sadd('a{foo}', '1', '2')
        r.sadd('b{foo}', '2', '3')
        assert r.sunion('a{foo}', 'b{foo}') == set([b('1'), b('2'), b('3')])

    def test_sunionstore(self, r):
        r.sadd('a{foo}', '1', '2')
        r.sadd('b{foo}', '2', '3')
        assert r.sunionstore('c{foo}', 'a{foo}', 'b{foo}') == 3
        assert r.smembers('c{foo}') == set([b('1'), b('2'), b('3')])

    # SORTED SET COMMANDS
    def test_zadd(self, r):
        r.zadd('a', a1=1, a2=2, a3=3)
        assert r.zrange('a', 0, -1) == [b('a1'), b('a2'), b('a3')]

    def test_zcard(self, r):
        r.zadd('a', a1=1, a2=2, a3=3)
        assert r.zcard('a') == 3

    def test_zcount(self, r):
        r.zadd('a', a1=1, a2=2, a3=3)
        assert r.zcount('a', '-inf', '+inf') == 3
        assert r.zcount('a', 1, 2) == 2
        assert r.zcount('a', 10, 20) == 0

    def test_zincrby(self, r):
        r.zadd('a', a1=1, a2=2, a3=3)
        assert r.zincrby('a', 'a2') == 3.0
        assert r.zincrby('a', 'a3', amount=5) == 8.0
        assert r.zscore('a', 'a2') == 3.0
        assert r.zscore('a', 'a3') == 8.0

    def test_zlexcount(self, r):
        r.zadd('a', a=0, b=0, c=0, d=0, e=0, f=0, g=0)
        assert r.zlexcount('a', '-', '+') == 7
        assert r.zlexcount('a', '[b', '[f') == 5

    def test_zinterstore_fail_cross_slot(self, r):
        r.zadd('a', a1=1, a2=1, a3=1)
        r.zadd('b', a1=2, a2=2, a3=2)
        r.zadd('c', a1=6, a3=5, a4=4)
        with pytest.raises(ResponseError) as excinfo:
            r.zinterstore('d', ['a', 'b', 'c'])
        assert re.search('ClusterCrossSlotError', str(excinfo))

    def test_zinterstore_sum(self, r):
        r.zadd('a{foo}', a1=1, a2=1, a3=1)
        r.zadd('b{foo}', a1=2, a2=2, a3=2)
        r.zadd('c{foo}', a1=6, a3=5, a4=4)
        assert r.zinterstore('d{foo}', ['a{foo}', 'b{foo}', 'c{foo}']) == 2
        assert r.zrange('d{foo}', 0, -1, withscores=True) == \
            [(b('a3'), 8), (b('a1'), 9)]

    def test_zinterstore_max(self, r):
        r.zadd('a{foo}', a1=1, a2=1, a3=1)
        r.zadd('b{foo}', a1=2, a2=2, a3=2)
        r.zadd('c{foo}', a1=6, a3=5, a4=4)
        assert r.zinterstore('d{foo}', ['a{foo}', 'b{foo}', 'c{foo}'], aggregate='MAX') == 2
        assert r.zrange('d{foo}', 0, -1, withscores=True) == \
            [(b('a3'), 5), (b('a1'), 6)]

    def test_zinterstore_min(self, r):
        r.zadd('a{foo}', a1=1, a2=2, a3=3)
        r.zadd('b{foo}', a1=2, a2=3, a3=5)
        r.zadd('c{foo}', a1=6, a3=5, a4=4)
        assert r.zinterstore('d{foo}', ['a{foo}', 'b{foo}', 'c{foo}'], aggregate='MIN') == 2
        assert r.zrange('d{foo}', 0, -1, withscores=True) == \
            [(b('a1'), 1), (b('a3'), 3)]

    def test_zinterstore_with_weight(self, r):
        r.zadd('a{foo}', a1=1, a2=1, a3=1)
        r.zadd('b{foo}', a1=2, a2=2, a3=2)
        r.zadd('c{foo}', a1=6, a3=5, a4=4)
        assert r.zinterstore('d{foo}', {'a{foo}': 1, 'b{foo}': 2, 'c{foo}': 3}) == 2
        assert r.zrange('d{foo}', 0, -1, withscores=True) == \
            [(b('a3'), 20), (b('a1'), 23)]

    def test_zrange(self, r):
        r.zadd('a', a1=1, a2=2, a3=3)
        assert r.zrange('a', 0, 1) == [b('a1'), b('a2')]
        assert r.zrange('a', 1, 2) == [b('a2'), b('a3')]

        # withscores
        assert r.zrange('a', 0, 1, withscores=True) == \
            [(b('a1'), 1.0), (b('a2'), 2.0)]
        assert r.zrange('a', 1, 2, withscores=True) == \
            [(b('a2'), 2.0), (b('a3'), 3.0)]

        # custom score function
        assert r.zrange('a', 0, 1, withscores=True, score_cast_func=int) == \
            [(b('a1'), 1), (b('a2'), 2)]

    def test_zrangebylex(self, r):
        r.zadd('a', a=0, b=0, c=0, d=0, e=0, f=0, g=0)
        assert r.zrangebylex('a', '-', '[c') == [b('a'), b('b'), b('c')]
        assert r.zrangebylex('a', '-', '(c') == [b('a'), b('b')]
        assert r.zrangebylex('a', '[aaa', '(g') == \
            [b('b'), b('c'), b('d'), b('e'), b('f')]
        assert r.zrangebylex('a', '[f', '+') == [b('f'), b('g')]
        assert r.zrangebylex('a', '-', '+', start=3, num=2) == [b('d'), b('e')]

    def test_zrangebyscore(self, r):
        r.zadd('a', a1=1, a2=2, a3=3, a4=4, a5=5)
        assert r.zrangebyscore('a', 2, 4) == [b('a2'), b('a3'), b('a4')]

        # slicing with start/num
        assert r.zrangebyscore('a', 2, 4, start=1, num=2) == \
            [b('a3'), b('a4')]

        # withscores
        assert r.zrangebyscore('a', 2, 4, withscores=True) == \
            [(b('a2'), 2.0), (b('a3'), 3.0), (b('a4'), 4.0)]

        # custom score function
        assert r.zrangebyscore('a', 2, 4, withscores=True,
                               score_cast_func=int) == \
            [(b('a2'), 2), (b('a3'), 3), (b('a4'), 4)]

    def test_zrank(self, r):
        r.zadd('a', a1=1, a2=2, a3=3, a4=4, a5=5)
        assert r.zrank('a', 'a1') == 0
        assert r.zrank('a', 'a2') == 1
        assert r.zrank('a', 'a6') is None

    def test_zrem(self, r):
        r.zadd('a', a1=1, a2=2, a3=3)
        assert r.zrem('a', 'a2') == 1
        assert r.zrange('a', 0, -1) == [b('a1'), b('a3')]
        assert r.zrem('a', 'b') == 0
        assert r.zrange('a', 0, -1) == [b('a1'), b('a3')]

    def test_zrem_multiple_keys(self, r):
        r.zadd('a', a1=1, a2=2, a3=3)
        assert r.zrem('a', 'a1', 'a2') == 2
        assert r.zrange('a', 0, 5) == [b('a3')]

    def test_zremrangebylex(self, r):
        r.zadd('a', a=0, b=0, c=0, d=0, e=0, f=0, g=0)
        assert r.zremrangebylex('a', '-', '[c') == 3
        assert r.zrange('a', 0, -1) == [b('d'), b('e'), b('f'), b('g')]
        assert r.zremrangebylex('a', '[f', '+') == 2
        assert r.zrange('a', 0, -1) == [b('d'), b('e')]
        assert r.zremrangebylex('a', '[h', '+') == 0
        assert r.zrange('a', 0, -1) == [b('d'), b('e')]

    def test_zremrangebyrank(self, r):
        r.zadd('a', a1=1, a2=2, a3=3, a4=4, a5=5)
        assert r.zremrangebyrank('a', 1, 3) == 3
        assert r.zrange('a', 0, 5) == [b('a1'), b('a5')]

    def test_zremrangebyscore(self, r):
        r.zadd('a', a1=1, a2=2, a3=3, a4=4, a5=5)
        assert r.zremrangebyscore('a', 2, 4) == 3
        assert r.zrange('a', 0, -1) == [b('a1'), b('a5')]
        assert r.zremrangebyscore('a', 2, 4) == 0
        assert r.zrange('a', 0, -1) == [b('a1'), b('a5')]

    def test_zrevrange(self, r):
        r.zadd('a', a1=1, a2=2, a3=3)
        assert r.zrevrange('a', 0, 1) == [b('a3'), b('a2')]
        assert r.zrevrange('a', 1, 2) == [b('a2'), b('a1')]

        # withscores
        assert r.zrevrange('a', 0, 1, withscores=True) == \
            [(b('a3'), 3.0), (b('a2'), 2.0)]
        assert r.zrevrange('a', 1, 2, withscores=True) == \
            [(b('a2'), 2.0), (b('a1'), 1.0)]

        # custom score function
        assert r.zrevrange('a', 0, 1, withscores=True,
                           score_cast_func=int) == \
            [(b('a3'), 3.0), (b('a2'), 2.0)]

    def test_zrevrangebyscore(self, r):
        r.zadd('a', a1=1, a2=2, a3=3, a4=4, a5=5)
        assert r.zrevrangebyscore('a', 4, 2) == [b('a4'), b('a3'), b('a2')]

        # slicing with start/num
        assert r.zrevrangebyscore('a', 4, 2, start=1, num=2) == \
            [b('a3'), b('a2')]

        # withscores
        assert r.zrevrangebyscore('a', 4, 2, withscores=True) == \
            [(b('a4'), 4.0), (b('a3'), 3.0), (b('a2'), 2.0)]

        # custom score function
        assert r.zrevrangebyscore('a', 4, 2, withscores=True,
                                  score_cast_func=int) == \
            [(b('a4'), 4), (b('a3'), 3), (b('a2'), 2)]

    def test_zrevrank(self, r):
        r.zadd('a', a1=1, a2=2, a3=3, a4=4, a5=5)
        assert r.zrevrank('a', 'a1') == 4
        assert r.zrevrank('a', 'a2') == 3
        assert r.zrevrank('a', 'a6') is None

    def test_zscore(self, r):
        r.zadd('a', a1=1, a2=2, a3=3)
        assert r.zscore('a', 'a1') == 1.0
        assert r.zscore('a', 'a2') == 2.0
        assert r.zscore('a', 'a4') is None

    def test_zunionstore_fail_crossslot(self, r):
        r.zadd('a', a1=1, a2=1, a3=1)
        r.zadd('b', a1=2, a2=2, a3=2)
        r.zadd('c', a1=6, a3=5, a4=4)
        with pytest.raises(ResponseError) as excinfo:
            r.zunionstore('d', ['a', 'b', 'c'])
        assert re.search('ClusterCrossSlotError', str(excinfo))

    def test_zunionstore_sum(self, r):
        r.zadd('a{foo}', a1=1, a2=1, a3=1)
        r.zadd('b{foo}', a1=2, a2=2, a3=2)
        r.zadd('c{foo}', a1=6, a3=5, a4=4)
        assert r.zunionstore('d{foo}', ['a{foo}', 'b{foo}', 'c{foo}']) == 4
        assert r.zrange('d{foo}', 0, -1, withscores=True) == \
            [(b('a2'), 3), (b('a4'), 4), (b('a3'), 8), (b('a1'), 9)]

    def test_zunionstore_max(self, r):
        r.zadd('a{foo}', a1=1, a2=1, a3=1)
        r.zadd('b{foo}', a1=2, a2=2, a3=2)
        r.zadd('c{foo}', a1=6, a3=5, a4=4)
        assert r.zunionstore('d{foo}', ['a{foo}', 'b{foo}', 'c{foo}'], aggregate='MAX') == 4
        assert r.zrange('d{foo}', 0, -1, withscores=True) == \
            [(b('a2'), 2), (b('a4'), 4), (b('a3'), 5), (b('a1'), 6)]

    def test_zunionstore_min(self, r):
        r.zadd('a{foo}', a1=1, a2=2, a3=3)
        r.zadd('b{foo}', a1=2, a2=2, a3=4)
        r.zadd('c{foo}', a1=6, a3=5, a4=4)
        assert r.zunionstore('d{foo}', ['a{foo}', 'b{foo}', 'c{foo}'], aggregate='MIN') == 4
        assert r.zrange('d{foo}', 0, -1, withscores=True) == \
            [(b('a1'), 1), (b('a2'), 2), (b('a3'), 3), (b('a4'), 4)]

    def test_zunionstore_with_weight(self, r):
        r.zadd('a{foo}', a1=1, a2=1, a3=1)
        r.zadd('b{foo}', a1=2, a2=2, a3=2)
        r.zadd('c{foo}', a1=6, a3=5, a4=4)
        assert r.zunionstore('d{foo}', {'a{foo}': 1, 'b{foo}': 2, 'c{foo}': 3}) == 4
        assert r.zrange('d{foo}', 0, -1, withscores=True) == \
            [(b('a2'), 5), (b('a4'), 12), (b('a3'), 20), (b('a1'), 23)]

#     # HYPERLOGLOG TESTS
    def test_pfadd(self, r):
        members = set([b('1'), b('2'), b('3')])
        assert r.pfadd('a', *members) == 1
        assert r.pfadd('a', *members) == 0
        assert r.pfcount('a') == len(members)

    @pytest.mark.xfail(reason="New pfcount in 2.10.5 currently breaks in cluster")
    @skip_if_server_version_lt('2.8.9')
    def test_pfcount(self, r):
        members = set([b('1'), b('2'), b('3')])
        r.pfadd('a', *members)
        assert r.pfcount('a') == len(members)
        members_b = set([b('2'), b('3'), b('4')])
        r.pfadd('b', *members_b)
        assert r.pfcount('b') == len(members_b)
        assert r.pfcount('a', 'b') == len(members_b.union(members))

    def test_pfmerge(self, r):
        mema = set([b('1'), b('2'), b('3')])
        memb = set([b('2'), b('3'), b('4')])
        memc = set([b('5'), b('6'), b('7')])
        r.pfadd('a', *mema)
        r.pfadd('b', *memb)
        r.pfadd('c', *memc)
        r.pfmerge('d', 'c', 'a')
        assert r.pfcount('d') == 6
        r.pfmerge('d', 'b')
        assert r.pfcount('d') == 7

    # HASH COMMANDS
    def test_hget_and_hset(self, r):
        r.hmset('a', {'1': 1, '2': 2, '3': 3})
        assert r.hget('a', '1') == b('1')
        assert r.hget('a', '2') == b('2')
        assert r.hget('a', '3') == b('3')

        # field was updated, redis returns 0
        assert r.hset('a', '2', 5) == 0
        assert r.hget('a', '2') == b('5')

        # field is new, redis returns 1
        assert r.hset('a', '4', 4) == 1
        assert r.hget('a', '4') == b('4')

        # key inside of hash that doesn't exist returns null value
        assert r.hget('a', 'b') is None

    def test_hdel(self, r):
        r.hmset('a', {'1': 1, '2': 2, '3': 3})
        assert r.hdel('a', '2') == 1
        assert r.hget('a', '2') is None
        assert r.hdel('a', '1', '3') == 2
        assert r.hlen('a') == 0

    def test_hexists(self, r):
        r.hmset('a', {'1': 1, '2': 2, '3': 3})
        assert r.hexists('a', '1')
        assert not r.hexists('a', '4')

    def test_hgetall(self, r):
        h = {b('a1'): b('1'), b('a2'): b('2'), b('a3'): b('3')}
        r.hmset('a', h)
        assert r.hgetall('a') == h

    def test_hincrby(self, r):
        assert r.hincrby('a', '1') == 1
        assert r.hincrby('a', '1', amount=2) == 3
        assert r.hincrby('a', '1', amount=-2) == 1

    def test_hincrbyfloat(self, r):
        assert r.hincrbyfloat('a', '1') == 1.0
        assert r.hincrbyfloat('a', '1') == 2.0
        assert r.hincrbyfloat('a', '1', 1.2) == 3.2

    def test_hkeys(self, r):
        h = {b('a1'): b('1'), b('a2'): b('2'), b('a3'): b('3')}
        r.hmset('a', h)
        local_keys = list(iterkeys(h))
        remote_keys = r.hkeys('a')
        assert (sorted(local_keys) == sorted(remote_keys))

    def test_hlen(self, r):
        r.hmset('a', {'1': 1, '2': 2, '3': 3})
        assert r.hlen('a') == 3

    def test_hmget(self, r):
        assert r.hmset('a', {'a': 1, 'b': 2, 'c': 3})
        assert r.hmget('a', 'a', 'b', 'c') == [b('1'), b('2'), b('3')]

    def test_hmset(self, r):
        h = {b('a'): b('1'), b('b'): b('2'), b('c'): b('3')}
        assert r.hmset('a', h)
        assert r.hgetall('a') == h

    def test_hsetnx(self, r):
        # Initially set the hash field
        assert r.hsetnx('a', '1', 1)
        assert r.hget('a', '1') == b('1')
        assert not r.hsetnx('a', '1', 2)
        assert r.hget('a', '1') == b('1')

    def test_hvals(self, r):
        h = {b('a1'): b('1'), b('a2'): b('2'), b('a3'): b('3')}
        r.hmset('a', h)
        local_vals = list(itervalues(h))
        remote_vals = r.hvals('a')
        assert sorted(local_vals) == sorted(remote_vals)

    # SORT
    def test_sort_basic(self, r):
        r.rpush('a', '3', '2', '1', '4')
        assert r.sort('a') == [b('1'), b('2'), b('3'), b('4')]

    def test_sort_limited(self, r):
        r.rpush('a', '3', '2', '1', '4')
        assert r.sort('a', start=1, num=2) == [b('2'), b('3')]

    def test_sort_by(self, r):
        r['score:1'] = 8
        r['score:2'] = 3
        r['score:3'] = 5
        r.rpush('a', '3', '2', '1')
        assert r.sort('a', by='score:*') == [b('2'), b('3'), b('1')]

    def test_sort_get(self, r):
        r['user:1'] = 'u1'
        r['user:2'] = 'u2'
        r['user:3'] = 'u3'
        r.rpush('a', '2', '3', '1')
        assert r.sort('a', get='user:*') == [b('u1'), b('u2'), b('u3')]

    def test_sort_get_multi(self, r):
        r['user:1'] = 'u1'
        r['user:2'] = 'u2'
        r['user:3'] = 'u3'
        r.rpush('a', '2', '3', '1')
        assert r.sort('a', get=('user:*', '#')) == \
            [b('u1'), b('1'), b('u2'), b('2'), b('u3'), b('3')]

    def test_sort_get_groups_two(self, r):
        r['user:1'] = 'u1'
        r['user:2'] = 'u2'
        r['user:3'] = 'u3'
        r.rpush('a', '2', '3', '1')
        assert r.sort('a', get=('user:*', '#'), groups=True) == \
            [(b('u1'), b('1')), (b('u2'), b('2')), (b('u3'), b('3'))]

    def test_sort_groups_string_get(self, r):
        r['user:1'] = 'u1'
        r['user:2'] = 'u2'
        r['user:3'] = 'u3'
        r.rpush('a', '2', '3', '1')
        with pytest.raises(DataError):
            r.sort('a', get='user:*', groups=True)

    def test_sort_groups_just_one_get(self, r):
        r['user:1'] = 'u1'
        r['user:2'] = 'u2'
        r['user:3'] = 'u3'
        r.rpush('a', '2', '3', '1')
        with pytest.raises(DataError):
            r.sort('a', get=['user:*'], groups=True)

    def test_sort_groups_no_get(self, r):
        r['user:1'] = 'u1'
        r['user:2'] = 'u2'
        r['user:3'] = 'u3'
        r.rpush('a', '2', '3', '1')
        with pytest.raises(DataError):
            r.sort('a', groups=True)

    def test_sort_groups_three_gets(self, r):
        r['user:1'] = 'u1'
        r['user:2'] = 'u2'
        r['user:3'] = 'u3'
        r['door:1'] = 'd1'
        r['door:2'] = 'd2'
        r['door:3'] = 'd3'
        r.rpush('a', '2', '3', '1')
        assert r.sort('a', get=('user:*', 'door:*', '#'), groups=True) == [
            (b('u1'), b('d1'), b('1')),
            (b('u2'), b('d2'), b('2')),
            (b('u3'), b('d3'), b('3'))
        ]

    def test_sort_desc(self, r):
        r.rpush('a', '2', '3', '1')
        assert r.sort('a', desc=True) == [b('3'), b('2'), b('1')]

    def test_sort_alpha(self, r):
        r.rpush('a', 'e', 'c', 'b', 'd', 'a')
        assert r.sort('a', alpha=True) == \
            [b('a'), b('b'), b('c'), b('d'), b('e')]

    def test_sort_store(self, r):
        r.rpush('a', '2', '3', '1')
        assert r.sort('a', store='sorted_values') == 3
        assert r.lrange('sorted_values', 0, -1) == [b('1'), b('2'), b('3')]

    def test_sort_all_options(self, r):
        r['user:1:username'] = 'zeus'
        r['user:2:username'] = 'titan'
        r['user:3:username'] = 'hermes'
        r['user:4:username'] = 'hercules'
        r['user:5:username'] = 'apollo'
        r['user:6:username'] = 'athena'
        r['user:7:username'] = 'hades'
        r['user:8:username'] = 'dionysus'

        r['user:1:favorite_drink'] = 'yuengling'
        r['user:2:favorite_drink'] = 'rum'
        r['user:3:favorite_drink'] = 'vodka'
        r['user:4:favorite_drink'] = 'milk'
        r['user:5:favorite_drink'] = 'pinot noir'
        r['user:6:favorite_drink'] = 'water'
        r['user:7:favorite_drink'] = 'gin'
        r['user:8:favorite_drink'] = 'apple juice'

        r.rpush('gods', '5', '8', '3', '1', '2', '7', '6', '4')
        num = r.sort('gods', start=2, num=4, by='user:*:username',
                     get='user:*:favorite_drink', desc=True, alpha=True,
                     store='sorted')
        assert num == 4
        assert r.lrange('sorted', 0, 10) == \
            [b('vodka'), b('milk'), b('gin'), b('apple juice')]


class TestStrictCommands(object):

    def test_strict_zadd(self, sr):
        sr.zadd('a', 1.0, 'a1', 2.0, 'a2', a3=3.0)
        assert sr.zrange('a', 0, -1, withscores=True) == \
            [(b('a1'), 1.0), (b('a2'), 2.0), (b('a3'), 3.0)]

    def test_strict_lrem(self, sr):
        sr.rpush('a', 'a1', 'a2', 'a3', 'a1')
        sr.lrem('a', 0, 'a1')
        assert sr.lrange('a', 0, -1) == [b('a2'), b('a3')]

    def test_strict_setex(self, sr):
        assert sr.setex('a', 60, '1')
        assert sr['a'] == b('1')
        assert 0 < sr.ttl('a') <= 60

    def test_strict_ttl(self, sr):
        assert not sr.expire('a', 10)
        sr['a'] = '1'
        assert sr.expire('a', 10)
        assert 0 < sr.ttl('a') <= 10
        assert sr.persist('a')
        assert sr.ttl('a') == -1

    def test_strict_pttl(self, sr):
        assert not sr.pexpire('a', 10000)
        sr['a'] = '1'
        assert sr.pexpire('a', 10000)
        assert 0 < sr.pttl('a') <= 10000
        assert sr.persist('a')
        assert sr.pttl('a') == -1

    def test_eval(self, sr):
        res = sr.eval("return {KEYS[1],KEYS[2],ARGV[1],ARGV[2]}", 2, "A{foo}", "B{foo}", "first", "second")
        assert res[0] == b('A{foo}')
        assert res[1] == b('B{foo}')
        assert res[2] == b('first')
        assert res[3] == b('second')


class TestBinarySave(object):
    def test_binary_get_set(self, r):
        assert r.set(' foo bar ', '123')
        assert r.get(' foo bar ') == b('123')

        assert r.set(' foo\r\nbar\r\n ', '456')
        assert r.get(' foo\r\nbar\r\n ') == b('456')

        assert r.set(' \r\n\t\x07\x13 ', '789')
        assert r.get(' \r\n\t\x07\x13 ') == b('789')

        assert sorted(r.keys('*')) == \
            [b(' \r\n\t\x07\x13 '), b(' foo\r\nbar\r\n '), b(' foo bar ')]

        assert r.delete(' foo bar ')
        assert r.delete(' foo\r\nbar\r\n ')
        assert r.delete(' \r\n\t\x07\x13 ')

    def test_binary_lists(self, r):
        mapping = {
            b('foo bar'): [b('1'), b('2'), b('3')],
            b('foo\r\nbar\r\n'): [b('4'), b('5'), b('6')],
            b('foo\tbar\x07'): [b('7'), b('8'), b('9')],
        }
        # fill in lists
        for key, value in iteritems(mapping):
            r.rpush(key, *value)

        # check that KEYS returns all the keys as they are
        assert sorted(r.keys('*')) == sorted(list(iterkeys(mapping)))

        # check that it is possible to get list content by key name
        for key, value in iteritems(mapping):
            assert r.lrange(key, 0, -1) == value

    def test_22_info(self):
        """
        Older Redis versions contained 'allocation_stats' in INFO that
        was the cause of a number of bugs when parsing.
        """
        info = "allocation_stats:6=1,7=1,8=7141,9=180,10=92,11=116,12=5330," \
               "13=123,14=3091,15=11048,16=225842,17=1784,18=814,19=12020," \
               "20=2530,21=645,22=15113,23=8695,24=142860,25=318,26=3303," \
               "27=20561,28=54042,29=37390,30=1884,31=18071,32=31367,33=160," \
               "34=169,35=201,36=10155,37=1045,38=15078,39=22985,40=12523," \
               "41=15588,42=265,43=1287,44=142,45=382,46=945,47=426,48=171," \
               "49=56,50=516,51=43,52=41,53=46,54=54,55=75,56=647,57=332," \
               "58=32,59=39,60=48,61=35,62=62,63=32,64=221,65=26,66=30," \
               "67=36,68=41,69=44,70=26,71=144,72=169,73=24,74=37,75=25," \
               "76=42,77=21,78=126,79=374,80=27,81=40,82=43,83=47,84=46," \
               "85=114,86=34,87=37,88=7240,89=34,90=38,91=18,92=99,93=20," \
               "94=18,95=17,96=15,97=22,98=18,99=69,100=17,101=22,102=15," \
               "103=29,104=39,105=30,106=70,107=22,108=21,109=26,110=52," \
               "111=45,112=33,113=67,114=41,115=44,116=48,117=53,118=54," \
               "119=51,120=75,121=44,122=57,123=44,124=66,125=56,126=52," \
               "127=81,128=108,129=70,130=50,131=51,132=53,133=45,134=62," \
               "135=12,136=13,137=7,138=15,139=21,140=11,141=20,142=6,143=7," \
               "144=11,145=6,146=16,147=19,148=1112,149=1,151=83,154=1," \
               "155=1,156=1,157=1,160=1,161=1,162=2,166=1,169=1,170=1,171=2," \
               "172=1,174=1,176=2,177=9,178=34,179=73,180=30,181=1,185=3," \
               "187=1,188=1,189=1,192=1,196=1,198=1,200=1,201=1,204=1,205=1," \
               "207=1,208=1,209=1,214=2,215=31,216=78,217=28,218=5,219=2," \
               "220=1,222=1,225=1,227=1,234=1,242=1,250=1,252=1,253=1," \
               ">=256=203"
        parsed = parse_info(info)
        assert 'allocation_stats' in parsed
        assert '6' in parsed['allocation_stats']
        assert '>=256' in parsed['allocation_stats']

    def test_large_responses(self, r):
        "The PythonParser has some special cases for return values > 1MB"
        # load up 100K of data into a key
        data = ''.join([ascii_letters] * (100000 // len(ascii_letters)))
        r['a'] = data
        assert r['a'] == b(data)

    def test_floating_point_encoding(self, r):
        """
        High precision floating point values sent to the server should keep
        precision.
        """
        timestamp = 1349673917.939762
        r.zadd('a', timestamp, 'a1')
        assert r.zscore('a', 'a1') == timestamp

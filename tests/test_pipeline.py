# -*- coding: utf-8 -*-

# python std lib
from __future__ import with_statement
import re

# rediscluster imports
from rediscluster.client import StrictRedisCluster
from rediscluster.connection import ClusterConnectionPool, ClusterReadOnlyConnectionPool
from rediscluster.exceptions import RedisClusterException

# 3rd party imports
import pytest
from mock import patch
from redis._compat import b, u, unichr, unicode
from redis.exceptions import WatchError, ResponseError, ConnectionError


class TestPipeline(object):
    """
    """

    def test_pipeline(self, r):
        with r.pipeline() as pipe:
            pipe.set('a', 'a1').get('a').zadd('z', z1=1).zadd('z', z2=4)
            pipe.zincrby('z', 'z1').zrange('z', 0, 5, withscores=True)
            assert pipe.execute() == [
                True,
                b('a1'),
                True,
                True,
                2.0,
                [(b('z1'), 2.0), (b('z2'), 4)],
            ]

    def test_pipeline_length(self, r):
        with r.pipeline() as pipe:
            # Initially empty.
            assert len(pipe) == 0
            assert not pipe

            # Fill 'er up!
            pipe.set('a', 'a1').set('b', 'b1').set('c', 'c1')
            assert len(pipe) == 3
            assert pipe

            # Execute calls reset(), so empty once again.
            pipe.execute()
            assert len(pipe) == 0
            assert not pipe

    def test_pipeline_no_transaction(self, r):
        with r.pipeline(transaction=False) as pipe:
            pipe.set('a', 'a1').set('b', 'b1').set('c', 'c1')
            assert pipe.execute() == [True, True, True]
            assert r['a'] == b('a1')
            assert r['b'] == b('b1')
            assert r['c'] == b('c1')

    def test_pipeline_eval(self, r):
        with r.pipeline(transaction=False) as pipe:
            pipe.eval("return {KEYS[1],KEYS[2],ARGV[1],ARGV[2]}", 2, "A{foo}", "B{foo}", "first", "second")
            res = pipe.execute()[0]
            assert res[0] == b('A{foo}')
            assert res[1] == b('B{foo}')
            assert res[2] == b('first')
            assert res[3] == b('second')

    @pytest.mark.xfail(reason="unsupported command: watch")
    def test_pipeline_no_transaction_watch(self, r):
        r['a'] = 0

        with r.pipeline(transaction=False) as pipe:
            pipe.watch('a')
            a = pipe.get('a')

            pipe.multi()
            pipe.set('a', int(a) + 1)
            assert pipe.execute() == [True]

    @pytest.mark.xfail(reason="unsupported command: watch")
    def test_pipeline_no_transaction_watch_failure(self, r):
        r['a'] = 0

        with r.pipeline(transaction=False) as pipe:
            pipe.watch('a')
            a = pipe.get('a')

            r['a'] = 'bad'

            pipe.multi()
            pipe.set('a', int(a) + 1)

            with pytest.raises(WatchError):
                pipe.execute()

            assert r['a'] == b('bad')

    def test_exec_error_in_response(self, r):
        """
        an invalid pipeline command at exec time adds the exception instance
        to the list of returned values
        """
        r['c'] = 'a'
        with r.pipeline() as pipe:
            pipe.set('a', 1).set('b', 2).lpush('c', 3).set('d', 4)
            result = pipe.execute(raise_on_error=False)

            assert result[0]
            assert r['a'] == b('1')
            assert result[1]
            assert r['b'] == b('2')

            # we can't lpush to a key that's a string value, so this should
            # be a ResponseError exception
            assert isinstance(result[2], ResponseError)
            assert r['c'] == b('a')

            # since this isn't a transaction, the other commands after the
            # error are still executed
            assert result[3]
            assert r['d'] == b('4')

            # make sure the pipe was restored to a working state
            assert pipe.set('z', 'zzz').execute() == [True]
            assert r['z'] == b('zzz')

    def test_exec_error_raised(self, r):
        r['c'] = 'a'
        with r.pipeline() as pipe:
            pipe.set('a', 1).set('b', 2).lpush('c', 3).set('d', 4)
            with pytest.raises(ResponseError) as ex:
                pipe.execute()
            assert unicode(ex.value).startswith('Command # 3 (LPUSH c 3) of '
                                                'pipeline caused error: ')

            # make sure the pipe was restored to a working state
            assert pipe.set('z', 'zzz').execute() == [True]
            assert r['z'] == b('zzz')

    def test_parse_error_raised(self, r):
        with r.pipeline() as pipe:
            # the zrem is invalid because we don't pass any keys to it
            pipe.set('a', 1).zrem('b').set('b', 2)
            with pytest.raises(ResponseError) as ex:
                pipe.execute()

            assert unicode(ex.value).startswith('Command # 2 (ZREM b) of '
                                                'pipeline caused error: ')

            # make sure the pipe was restored to a working state
            assert pipe.set('z', 'zzz').execute() == [True]
            assert r['z'] == b('zzz')

    @pytest.mark.xfail(reason="unsupported command: watch")
    def test_watch_succeed(self, r):
        r['a'] = 1
        r['b'] = 2

        with r.pipeline() as pipe:
            pipe.watch('a', 'b')
            assert pipe.watching
            a_value = pipe.get('a')
            b_value = pipe.get('b')
            assert a_value == b('1')
            assert b_value == b('2')
            pipe.multi()

            pipe.set('c', 3)
            assert pipe.execute() == [True]
            assert not pipe.watching

    @pytest.mark.xfail(reason="unsupported command: watch")
    def test_watch_failure(self, r):
        r['a'] = 1
        r['b'] = 2

        with r.pipeline() as pipe:
            pipe.watch('a', 'b')
            r['b'] = 3
            pipe.multi()
            pipe.get('a')
            with pytest.raises(WatchError):
                pipe.execute()

            assert not pipe.watching

    @pytest.mark.xfail(reason="unsupported command: watch")
    def test_unwatch(self, r):
        r['a'] = 1
        r['b'] = 2

        with r.pipeline() as pipe:
            pipe.watch('a', 'b')
            r['b'] = 3
            pipe.unwatch()
            assert not pipe.watching
            pipe.get('a')
            assert pipe.execute() == [b('1')]

    @pytest.mark.xfail(reason="unsupported command: watch")
    def test_transaction_callable(self, r):
        r['a'] = 1
        r['b'] = 2
        has_run = []

        def my_transaction(pipe):
            a_value = pipe.get('a')
            assert a_value in (b('1'), b('2'))
            b_value = pipe.get('b')
            assert b_value == b('2')

            # silly run-once code... incr's "a" so WatchError should be raised
            # forcing this all to run again. this should incr "a" once to "2"
            if not has_run:
                r.incr('a')
                has_run.append('it has')

            pipe.multi()
            pipe.set('c', int(a_value) + int(b_value))

        result = r.transaction(my_transaction, 'a', 'b')
        assert result == [True]
        assert r['c'] == b('4')

    def test_exec_error_in_no_transaction_pipeline(self, r):
        r['a'] = 1
        with r.pipeline(transaction=False) as pipe:
            pipe.llen('a')
            pipe.expire('a', 100)

            with pytest.raises(ResponseError) as ex:
                pipe.execute()

            assert unicode(ex.value).startswith('Command # 1 (LLEN a) of '
                                                'pipeline caused error: ')

        assert r['a'] == b('1')

    def test_exec_error_in_no_transaction_pipeline_unicode_command(self, r):
        key = unichr(3456) + u('abcd') + unichr(3421)
        r[key] = 1
        with r.pipeline(transaction=False) as pipe:
            pipe.llen(key)
            pipe.expire(key, 100)

            with pytest.raises(ResponseError) as ex:
                pipe.execute()

            expected = unicode('Command # 1 (LLEN {0}) of pipeline caused error: ').format(key)
            assert unicode(ex.value).startswith(expected)

        assert r[key] == b('1')

    def test_blocked_methods(self, r):
        """
        Currently some method calls on a Cluster pipeline
        is blocked when using in cluster mode.
        They maybe implemented in the future.
        """
        pipe = r.pipeline(transaction=False)
        with pytest.raises(RedisClusterException):
            pipe.multi()

        with pytest.raises(RedisClusterException):
            pipe.immediate_execute_command()

        with pytest.raises(RedisClusterException):
            pipe._execute_transaction(None, None, None)

        with pytest.raises(RedisClusterException):
            pipe.load_scripts()

        with pytest.raises(RedisClusterException):
            pipe.watch()

        with pytest.raises(RedisClusterException):
            pipe.unwatch()

        with pytest.raises(RedisClusterException):
            pipe.script_load_for_pipeline(None)

        with pytest.raises(RedisClusterException):
            pipe.transaction(None)

    def test_blocked_arguments(self, r):
        """
        Currently some arguments is blocked when using in cluster mode.
        They maybe implemented in the future.
        """
        with pytest.raises(RedisClusterException) as ex:
            r.pipeline(transaction=True)

        assert unicode(ex.value).startswith("transaction is deprecated in cluster mode"), True

        with pytest.raises(RedisClusterException) as ex:
            r.pipeline(shard_hint=True)

        assert unicode(ex.value).startswith("shard_hint is deprecated in cluster mode"), True

    def test_mget_disabled(self, r):
        with r.pipeline(transaction=False) as pipe:
            with pytest.raises(RedisClusterException):
                pipe.mget(['a'])

    def test_mset_disabled(self, r):
        with r.pipeline(transaction=False) as pipe:
            with pytest.raises(RedisClusterException):
                pipe.mset({'a': 1, 'b': 2})

    def test_rename_disabled(self, r):
        with r.pipeline(transaction=False) as pipe:
            with pytest.raises(RedisClusterException):
                pipe.rename('a', 'b')

    def test_renamenx_disabled(self, r):
        with r.pipeline(transaction=False) as pipe:
            with pytest.raises(RedisClusterException):
                pipe.renamenx('a', 'b')

    def test_delete_single(self, r):
        r['a'] = 1
        with r.pipeline(transaction=False) as pipe:
            pipe.delete('a')
            assert pipe.execute(), True

    def test_multi_delete_unsupported(self, r):
        with r.pipeline(transaction=False) as pipe:
            r['a'] = 1
            r['b'] = 2
            with pytest.raises(RedisClusterException):
                pipe.delete('a', 'b')

    def test_brpoplpush_disabled(self, r):
        with r.pipeline(transaction=False) as pipe:
            with pytest.raises(RedisClusterException):
                pipe.brpoplpush()

    def test_rpoplpush_disabled(self, r):
        with r.pipeline(transaction=False) as pipe:
            with pytest.raises(RedisClusterException):
                pipe.rpoplpush()

    def test_sort_disabled(self, r):
        with r.pipeline(transaction=False) as pipe:
            with pytest.raises(RedisClusterException):
                pipe.sort()

    def test_sdiff_disabled(self, r):
        with r.pipeline(transaction=False) as pipe:
            with pytest.raises(RedisClusterException):
                pipe.sdiff()

    def test_sdiffstore_disabled(self, r):
        with r.pipeline(transaction=False) as pipe:
            with pytest.raises(RedisClusterException):
                pipe.sdiffstore()

    def test_sinter_disabled(self, r):
        with r.pipeline(transaction=False) as pipe:
            with pytest.raises(RedisClusterException):
                pipe.sinter()

    def test_sinterstore_disabled(self, r):
        with r.pipeline(transaction=False) as pipe:
            with pytest.raises(RedisClusterException):
                pipe.sinterstore()

    def test_smove_disabled(self, r):
        with r.pipeline(transaction=False) as pipe:
            with pytest.raises(RedisClusterException):
                pipe.smove()

    def test_sunion_disabled(self, r):
        with r.pipeline(transaction=False) as pipe:
            with pytest.raises(RedisClusterException):
                pipe.sunion()

    def test_sunionstore_disabled(self, r):
        with r.pipeline(transaction=False) as pipe:
            with pytest.raises(RedisClusterException):
                pipe.sunionstore()

    def test_spfmerge_disabled(self, r):
        with r.pipeline(transaction=False) as pipe:
            with pytest.raises(RedisClusterException):
                pipe.pfmerge()

    def test_multi_key_operation_with_shared_shards(self, r):
        pipe = r.pipeline(transaction=False)
        pipe.set('a{foo}', 1)
        pipe.set('b{foo}', 2)
        pipe.set('c{foo}', 3)
        pipe.set('bar', 4)
        pipe.set('bazz', 5)
        pipe.get('a{foo}')
        pipe.get('b{foo}')
        pipe.get('c{foo}')
        pipe.get('bar')
        pipe.get('bazz')
        res = pipe.execute()
        assert res == [True, True, True, True, True, b'1', b'2', b'3', b'4', b'5']

    @pytest.mark.xfail(reson="perform_execute_pipeline is not used any longer")
    def test_connection_error(self, r):
        test = self
        test._calls = []

        def perform_execute_pipeline(pipe):
            if not test._calls:
                e = ConnectionError('test')
                test._calls.append({'exception': e})
                return [e]
            result = pipe.execute(raise_on_error=False)
            test._calls.append({'result': result})
            return result

        pipe = r.pipeline(transaction=False)
        orig_perform_execute_pipeline = pipe.perform_execute_pipeline
        pipe.perform_execute_pipeline = perform_execute_pipeline

        try:
            pipe.set('foo', 1)
            res = pipe.execute()
            assert res, [True]
            assert isinstance(test._calls[0]['exception'], ConnectionError)
            if len(test._calls) == 2:
                assert test._calls[1] == {'result': [True]}
            else:
                assert isinstance(test._calls[1]['result'][0], ResponseError)
                assert test._calls[2] == {'result': [True]}
        finally:
            pipe.perform_execute_pipeline = orig_perform_execute_pipeline
            del test._calls

    @pytest.mark.xfail(reson="perform_execute_pipeline is not used any longer")
    def test_asking_error(self, r):
        test = self
        test._calls = []

        def perform_execute_pipeline(pipe):
            if not test._calls:

                e = ResponseError("ASK {0} 127.0.0.1:7003".format(r.keyslot('foo')))
                test._calls.append({'exception': e})
                return [e, e]
            result = pipe.execute(raise_on_error=False)
            test._calls.append({'result': result})
            return result

        pipe = r.pipeline(transaction=False)
        orig_perform_execute_pipeline = pipe.perform_execute_pipeline
        pipe.perform_execute_pipeline = perform_execute_pipeline

        try:
            pipe.set('foo', 1)
            pipe.get('foo')
            res = pipe.execute()
            assert res == [True, b'1']
            assert isinstance(test._calls[0]['exception'], ResponseError)
            assert re.match("ASK", str(test._calls[0]['exception']))
            assert isinstance(test._calls[1]['result'][0], ResponseError)
            assert re.match("MOVED", str(test._calls[1]['result'][0]))
            assert test._calls[2] == {'result': [True, b'1']}
        finally:
            pipe.perform_execute_pipeline = orig_perform_execute_pipeline
            del test._calls

    def test_empty_stack(self, r):
        """
        If pipeline is executed with no commands it should
        return a empty list.
        """
        p = r.pipeline()
        result = p.execute()
        assert result == []


class TestReadOnlyPipeline(object):

    def test_pipeline_readonly(self, r, ro):
        """
        On readonly mode, we supports get related stuff only.
        """
        r.set('foo71', 'a1')   # we assume this key is set on 127.0.0.1:7001
        r.zadd('foo88', z1=1)  # we assume this key is set on 127.0.0.1:7002
        r.zadd('foo88', z2=4)

        with ro.pipeline() as readonly_pipe:
            readonly_pipe.get('foo71').zrange('foo88', 0, 5, withscores=True)
            assert readonly_pipe.execute() == [
                b('a1'),
                [(b('z1'), 1.0), (b('z2'), 4)],
            ]

    def assert_moved_redirection_on_slave(self, connection_pool_cls, cluster_obj):
        with patch.object(connection_pool_cls, 'get_node_by_slot') as return_slave_mock:
            with patch.object(ClusterConnectionPool, 'get_master_node_by_slot') as return_master_mock:
                def get_mock_node(role, port):
                    return {
                        'name': '127.0.0.1:{0}'.format(port),
                        'host': '127.0.0.1',
                        'port': port,
                        'server_type': role,
                    }

                return_slave_mock.return_value = get_mock_node('slave', 7005)
                return_master_mock.return_value = get_mock_node('slave', 7001)

                with cluster_obj.pipeline() as pipe:
                    # we assume this key is set on 127.0.0.1:7001(7004)
                    pipe.get('foo87').get('foo88').execute() == [None, None]
                    assert return_master_mock.call_count == 2

    def test_moved_redirection_on_slave_with_default(self):
        """
        On Pipeline, we redirected once and finally get from master with
        readonly client when data is completely moved.
        """
        self.assert_moved_redirection_on_slave(
            ClusterConnectionPool,
            StrictRedisCluster(host="127.0.0.1", port=7000, reinitialize_steps=1)
        )

    def test_moved_redirection_on_slave_with_readonly_mode_client(self):
        """
        Ditto with READONLY mode.
        """
        self.assert_moved_redirection_on_slave(
            ClusterReadOnlyConnectionPool,
            StrictRedisCluster(host="127.0.0.1", port=7000, readonly_mode=True, reinitialize_steps=1)
        )

    def test_access_correct_slave_with_readonly_mode_client(self, sr):
        """
        Test that the client can get value normally with readonly mode
        when we connect to correct slave.
        """

        # we assume this key is set on 127.0.0.1:7001
        sr.set('foo87', 'foo')
        sr.set('foo88', 'bar')
        import time
        time.sleep(1)

        with patch.object(ClusterReadOnlyConnectionPool, 'get_node_by_slot') as return_slave_mock:
            return_slave_mock.return_value = {
                'name': '127.0.0.1:7004',
                'host': '127.0.0.1',
                'port': 7004,
                'server_type': 'slave',
            }

            master_value = {'host': '127.0.0.1', 'name': '127.0.0.1:7001', 'port': 7001, 'server_type': 'master'}
            with patch.object(
                    ClusterConnectionPool,
                    'get_master_node_by_slot',
                    return_value=master_value) as return_master_mock:
                readonly_client = StrictRedisCluster(host="127.0.0.1", port=7000, readonly_mode=True)
                with readonly_client.pipeline() as readonly_pipe:
                    assert readonly_pipe.get('foo88').get('foo87').execute() == [b('bar'), b('foo')]
                    assert return_master_mock.call_count == 0

# -*- coding: utf-8 -*-

# python std lib
from __future__ import with_statement
import re

# rediscluster imports
from rediscluster.exceptions import RedisClusterException

# 3rd party imports
import pytest
from redis._compat import b, u, unichr, unicode
from redis.exceptions import WatchError, ResponseError, ConnectionError


@pytest.mark.xfail(reason="Pipelines is not converted yet")
class TestPipeline(object):
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

            expected = unicode('Command # 1 (LLEN %s) of pipeline caused '
                               'error: ') % key
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
        assert(res == [True, True, True, True, True, b'1', b'2', b'3', b'4', b'5'])

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
            assert(res, [True])
            assert(isinstance(test._calls[0]['exception'], ConnectionError))
            if len(test._calls) == 2:
                assert(test._calls[1] == {'result': [True]})
            else:
                assert(isinstance(test._calls[1]['result'][0], ResponseError))
                assert(test._calls[2] == {'result': [True]})
        finally:
            pipe.perform_execute_pipeline = orig_perform_execute_pipeline
            del test._calls

    def test_asking_error(self, r):
        test = self
        test._calls = []

        def perform_execute_pipeline(pipe):
            if not test._calls:

                e = ResponseError("ASK %s 127.0.0.1:7003" % (r.keyslot('foo')))
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
            assert(res == [True, b'1'])
            assert(isinstance(test._calls[0]['exception'], ResponseError))
            assert(re.match("ASK", str(test._calls[0]['exception'])))
            assert(isinstance(test._calls[1]['result'][0], ResponseError))
            assert(re.match("MOVED", str(test._calls[1]['result'][0])))
            assert(test._calls[2] == {'result': [True, b'1']})
        finally:
            pipe.perform_execute_pipeline = orig_perform_execute_pipeline
            del test._calls

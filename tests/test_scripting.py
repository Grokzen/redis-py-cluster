# -*- coding: utf-8 -*-

# python std lib
from __future__ import with_statement

# rediscluster imports
from rediscluster.exceptions import RedisClusterException

# 3rd party imports
from redis import exceptions
from redis._compat import b
import pytest


multiply_script = """
local value = redis.call('GET', KEYS[1])
value = tonumber(value)
return value * ARGV[1]"""

msgpack_hello_script = """
local message = cmsgpack.unpack(ARGV[1])
local name = message['name']
return "hello " .. name
"""
msgpack_hello_script_broken = """
local message = cmsgpack.unpack(ARGV[1])
local names = message['name']
return "hello " .. name
"""


class TestScripting(object):
    @pytest.fixture(autouse=True)
    def reset_scripts(self, r):
        r.script_flush()

    def test_eval(self, r):
        r.set('a', 2)
        # 2 * 3 == 6
        assert r.eval(multiply_script, 1, 'a', 3) == 6

    def test_eval_same_slot(self, r):
        r.set('A{foo}', 2)
        r.set('B{foo}', 4)
        # 2 * 4 == 8

        script = """
        local value = redis.call('GET', KEYS[1])
        local value2 = redis.call('GET', KEYS[2])
        return value * value2
        """
        result = r.eval(script, 2, 'A{foo}', 'B{foo}')
        assert result == 8

    def test_eval_crossslot(self, r):
        """
        This test assumes that {foo} and {bar} will not go to the same
        server when used. In 3 masters + 3 slaves config this should pass.
        """
        r.set('A{foo}', 2)
        r.set('B{bar}', 4)
        # 2 * 4 == 8

        script = """
        local value = redis.call('GET', KEYS[1])
        local value2 = redis.call('GET', KEYS[2])
        return value * value2
        """
        with pytest.raises(RedisClusterException):
            r.eval(script, 2, 'A{foo}', 'B{bar}')

    def test_evalsha(self, r):
        r.set('a', 2)
        sha = r.script_load(multiply_script)
        # 2 * 3 == 6
        assert r.evalsha(sha, 1, 'a', 3) == 6

    def test_evalsha_script_not_loaded(self, r):
        r.set('a', 2)
        sha = r.script_load(multiply_script)
        # remove the script from Redis's cache
        r.script_flush()
        with pytest.raises(exceptions.NoScriptError):
            r.evalsha(sha, 1, 'a', 3)

    def test_script_loading(self, r):
        # get the sha, then clear the cache
        sha = r.script_load(multiply_script)
        r.script_flush()
        assert r.script_exists(sha) == [False]
        r.script_load(multiply_script)
        assert r.script_exists(sha) == [True]

    def test_script_object(self, r):
        r.set('a', 2)
        multiply = r.register_script(multiply_script)
        assert not multiply.sha
        # test evalsha fail -> script load + retry
        assert multiply(keys=['a'], args=[3]) == 6
        assert multiply.sha
        assert r.script_exists(multiply.sha) == [True]
        # test first evalsha
        assert multiply(keys=['a'], args=[3]) == 6

    @pytest.mark.xfail(reason="Not Yet Implemented")
    def test_script_object_in_pipeline(self, r):
        multiply = r.register_script(multiply_script)
        assert not multiply.sha
        pipe = r.pipeline()
        pipe.set('a', 2)
        pipe.get('a')
        multiply(keys=['a'], args=[3], client=pipe)
        # even though the pipeline wasn't executed yet, we made sure the
        # script was loaded and got a valid sha
        assert multiply.sha
        assert r.script_exists(multiply.sha) == [True]
        # [SET worked, GET 'a', result of multiple script]
        assert pipe.execute() == [True, b('2'), 6]

        # purge the script from redis's cache and re-run the pipeline
        # the multiply script object knows it's sha, so it shouldn't get
        # reloaded until pipe.execute()
        r.script_flush()
        pipe = r.pipeline()
        pipe.set('a', 2)
        pipe.get('a')
        assert multiply.sha
        multiply(keys=['a'], args=[3], client=pipe)
        assert r.script_exists(multiply.sha) == [False]
        # [SET worked, GET 'a', result of multiple script]
        assert pipe.execute() == [True, b('2'), 6]

    @pytest.mark.xfail(reason="Not Yet Implemented")
    def test_eval_msgpack_pipeline_error_in_lua(self, r):
        msgpack_hello = r.register_script(msgpack_hello_script)
        assert not msgpack_hello.sha

        pipe = r.pipeline()

        # avoiding a dependency to msgpack, this is the output of
        # msgpack.dumps({"name": "joe"})
        msgpack_message_1 = b'\x81\xa4name\xa3Joe'

        msgpack_hello(args=[msgpack_message_1], client=pipe)

        assert r.script_exists(msgpack_hello.sha) == [True]
        assert pipe.execute()[0] == b'hello Joe'

        msgpack_hello_broken = r.register_script(msgpack_hello_script_broken)

        msgpack_hello_broken(args=[msgpack_message_1], client=pipe)
        with pytest.raises(exceptions.ResponseError) as excinfo:
            pipe.execute()
        assert excinfo.type == exceptions.ResponseError

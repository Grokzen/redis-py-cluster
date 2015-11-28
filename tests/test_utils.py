# -*- coding: utf-8 -*-

# python std lib
from __future__ import with_statement

# rediscluster imports
from rediscluster.exceptions import (
    RedisClusterException, ClusterDownError
)
from rediscluster.utils import (
    string_keys_to_dict,
    dict_merge,
    blocked_command,
    merge_result,
    first_key,
    clusterdown_wrapper,
)

# 3rd party imports
import pytest
from redis._compat import unicode


def test_string_keys_to():
    l = lambda: True
    assert string_keys_to_dict(["FOO", "BAR"], l) == {"FOO": l, "BAR": l}


def test_dict_merge():
    a = {"a": 1}
    b = {"b": 2}
    c = {"c": 3}
    assert dict_merge(a, b, c) == {"a": 1, "b": 2, "c": 3}


def test_dict_merge_value_error():
    with pytest.raises(ValueError):
        dict_merge([])


def test_blocked_command():
    with pytest.raises(RedisClusterException) as ex:
        blocked_command(None, "SET")
    assert unicode(ex.value) == "Command: SET is blocked in redis cluster mode"


def test_merge_result():
    assert merge_result("foobar", {"a": [1, 2, 3], "b": [4, 5, 6]}) == [1, 2, 3, 4, 5, 6]
    assert merge_result("foobar", {"a": [1, 2, 3], "b": [1, 2, 3]}) == [1, 2, 3]


def test_merge_result_value_error():
    with pytest.raises(ValueError):
        merge_result("foobar", [])


def test_first_key():
    assert first_key("foobar", {"foo": 1}) == 1

    with pytest.raises(RedisClusterException) as ex:
        first_key("foobar", {"foo": 1, "bar": 2})
    assert unicode(ex.value).startswith("More then 1 result from command: foobar")


def test_first_key_value_error():
    with pytest.raises(ValueError):
        first_key("foobar", None)


def test_clusterdown_wrapper():
    @clusterdown_wrapper
    def bad_func():
        raise ClusterDownError("CLUSTERDOWN")

    with pytest.raises(ClusterDownError) as cex:
        bad_func()
    assert unicode(cex.value).startswith("CLUSTERDOWN error. Unable to rebuild the cluster")

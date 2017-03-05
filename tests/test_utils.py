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
    parse_cluster_slots,
)

# 3rd party imports
import pytest
from redis._compat import unicode, b


def test_parse_cluster_slots():
    """
    Example raw output from redis cluster. Output is form a redis 3.2.x node
    that includes the id in the reponse. The test below that do not include the id
    is to validate that the code is compatible with redis versions that do not contain
    that value in the response from the server.

    127.0.0.1:10000> cluster slots
    1) 1) (integer) 5461
       2) (integer) 10922
       3) 1) "10.0.0.1"
          2) (integer) 10000
          3) "3588b4cf9fc72d57bb262a024747797ead0cf7ea"
       4) 1) "10.0.0.4"
          2) (integer) 10000
          3) "a72c02c7d85f4ec3145ab2c411eefc0812aa96b0"
    2) 1) (integer) 10923
       2) (integer) 16383
       3) 1) "10.0.0.2"
          2) (integer) 10000
          3) "ffd36d8d7cb10d813f81f9662a835f6beea72677"
       4) 1) "10.0.0.5"
          2) (integer) 10000
          3) "5c15b69186017ddc25ebfac81e74694fc0c1a160"
    3) 1) (integer) 0
       2) (integer) 5460
       3) 1) "10.0.0.3"
          2) (integer) 10000
          3) "069cda388c7c41c62abe892d9e0a2d55fbf5ffd5"
       4) 1) "10.0.0.6"
          2) (integer) 10000
          3) "dc152a08b4cf1f2a0baf775fb86ad0938cb907dc"
    """
    mock_response = [
        [0, 5460, ['172.17.0.2', 7000], ['172.17.0.2', 7003]],
        [5461, 10922, ['172.17.0.2', 7001], ['172.17.0.2', 7004]],
        [10923, 16383, ['172.17.0.2', 7002], ['172.17.0.2', 7005]]
    ]
    parse_cluster_slots(mock_response)

    extended_mock_response = [
        [0, 5460, ['172.17.0.2', 7000, 'ffd36d8d7cb10d813f81f9662a835f6beea72677'], ['172.17.0.2', 7003, '5c15b69186017ddc25ebfac81e74694fc0c1a160']],
        [5461, 10922, ['172.17.0.2', 7001, '069cda388c7c41c62abe892d9e0a2d55fbf5ffd5'], ['172.17.0.2', 7004, 'dc152a08b4cf1f2a0baf775fb86ad0938cb907dc']],
        [10923, 16383, ['172.17.0.2', 7002, '3588b4cf9fc72d57bb262a024747797ead0cf7ea'], ['172.17.0.2', 7005, 'a72c02c7d85f4ec3145ab2c411eefc0812aa96b0']]
    ]

    parse_cluster_slots(extended_mock_response)

    mock_binary_response = [
        [0, 5460, [b('172.17.0.2'), 7000], [b('172.17.0.2'), 7003]],
        [5461, 10922, [b('172.17.0.2'), 7001], [b('172.17.0.2'), 7004]],
        [10923, 16383, [b('172.17.0.2'), 7002], [b('172.17.0.2'), 7005]]
    ]
    parse_cluster_slots(mock_binary_response)

    extended_mock_binary_response = [
        [0, 5460, [b('172.17.0.2'), 7000, b('ffd36d8d7cb10d813f81f9662a835f6beea72677')], [b('172.17.0.2'), 7003, b('5c15b69186017ddc25ebfac81e74694fc0c1a160')]],
        [5461, 10922, [b('172.17.0.2'), 7001, b('069cda388c7c41c62abe892d9e0a2d55fbf5ffd5')], [b('172.17.0.2'), 7004, b('dc152a08b4cf1f2a0baf775fb86ad0938cb907dc')]],
        [10923, 16383, [b('172.17.0.2'), 7002, b('3588b4cf9fc72d57bb262a024747797ead0cf7ea')], [b('172.17.0.2'), 7005, b('a72c02c7d85f4ec3145ab2c411eefc0812aa96b0')]]
    ]

    extended_mock_parsed = {
        (0, 5460): {'master': ('172.17.0.2', 7000), 'slaves': [('172.17.0.2', 7003)]},
        (5461, 10922): {'master': ('172.17.0.2', 7001),
                        'slaves': [('172.17.0.2', 7004)]},
        (10923, 16383): {'master': ('172.17.0.2', 7002),
                         'slaves': [('172.17.0.2', 7005)]}
    }

    assert parse_cluster_slots(extended_mock_binary_response) == extended_mock_parsed


def test_string_keys_to():
    def mock_true():
        return True
    assert string_keys_to_dict(["FOO", "BAR"], mock_true) == {"FOO": mock_true, "BAR": mock_true}


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

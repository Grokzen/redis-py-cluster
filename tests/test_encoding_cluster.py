from __future__ import unicode_literals
import pytest
import redis

from rediscluster import RedisCluster

from redis._compat import unichr, unicode
from .conftest import _get_client, _init_client


class TestEncodingCluster(object):
    """
    We must import the entire class due to the seperate fixture that uses RedisCluster as client
    class instead of the normal Redis instance.

    FIXME: If possible, monkeypatching TestEncoding class would be preffered but kinda impossible in reality
    """
    @pytest.fixture()
    def r(self, request):
        return _get_client(RedisCluster, request=request, decode_responses=True)

    @pytest.fixture()
    def r_no_decode(self, request):
        return _get_client(
            RedisCluster,
            request=request,
            decode_responses=False,
        )

    def test_simple_encoding(self, r_no_decode):
        unicode_string = unichr(3456) + 'abcd' + unichr(3421)
        r_no_decode['unicode-string'] = unicode_string.encode('utf-8')
        cached_val = r_no_decode['unicode-string']
        assert isinstance(cached_val, bytes)
        assert unicode_string == cached_val.decode('utf-8')

    def test_simple_encoding_and_decoding(self, r):
        unicode_string = unichr(3456) + 'abcd' + unichr(3421)
        r['unicode-string'] = unicode_string
        cached_val = r['unicode-string']
        assert isinstance(cached_val, unicode)
        assert unicode_string == cached_val

    def test_memoryview_encoding(self, r_no_decode):
        unicode_string = unichr(3456) + 'abcd' + unichr(3421)
        unicode_string_view = memoryview(unicode_string.encode('utf-8'))
        r_no_decode['unicode-string-memoryview'] = unicode_string_view
        cached_val = r_no_decode['unicode-string-memoryview']
        # The cached value won't be a memoryview because it's a copy from Redis
        assert isinstance(cached_val, bytes)
        assert unicode_string == cached_val.decode('utf-8')

    def test_memoryview_encoding_and_decoding(self, r):
        unicode_string = unichr(3456) + 'abcd' + unichr(3421)
        unicode_string_view = memoryview(unicode_string.encode('utf-8'))
        r['unicode-string-memoryview'] = unicode_string_view
        cached_val = r['unicode-string-memoryview']
        assert isinstance(cached_val, unicode)
        assert unicode_string == cached_val

    def test_list_encoding(self, r):
        unicode_string = unichr(3456) + 'abcd' + unichr(3421)
        result = [unicode_string, unicode_string, unicode_string]
        r.rpush('a', *result)
        assert r.lrange('a', 0, -1) == result


class TestEncodingErrors(object):
    def test_ignore(self, request):
        r = _get_client(RedisCluster, request=request, decode_responses=True,
                        encoding_errors='ignore')
        r.set('a', b'foo\xff')
        assert r.get('a') == 'foo'

    def test_replace(self, request):
        r = _get_client(RedisCluster, request=request, decode_responses=True,
                        encoding_errors='replace')
        r.set('a', b'foo\xff')
        assert r.get('a') == 'foo\ufffd'

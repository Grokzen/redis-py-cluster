# -*- coding: utf-8 -*-

# python std lib
import random
import string
import time

# rediscluster imports
from rediscluster.connection import ClusterConnectionPool
from rediscluster.exceptions import RedisClusterException
from rediscluster.decorators import block_command, send_eval_to_connection
from rediscluster.pipeline import BaseClusterPipeline

# 3rd party imports
from redis import StrictRedis
from redis.client import list_or_args, PubSub
from redis._compat import iteritems, basestring, b, izip, nativestr
from redis.exceptions import RedisError, ResponseError, TimeoutError, DataError, ConnectionError, BusyLoadingError


def string_keys_to_dict(key_strings, callback):
    """
    Borrowed from StrictRedis
    """
    return dict.fromkeys(key_strings, callback)


def dict_merge(*dicts):
    """
    Borrowed from StrictRedis
    """
    merged = {}
    [merged.update(d) for d in dicts]
    return merged


def blocked_command(self, command):
    raise RedisClusterException("Command: {} is blocked in redis cluster mode".format(command))


def merge_result(command, res):
    # TODO: Simplify/optimize
    result = set([])
    for k, v in res.items():
        for value in v:
            result.add(value)
    return list(result)


def first_key(command, res):
    if len(res.keys()) != 1:
        raise RedisClusterException("More then 1 result from command: {0}".format(command))
    return list(res.values())[0]


class RedisCluster(StrictRedis):
    """
    If a command is implemented over the one in StrictRedis then it requires some changes compared to
    the regular implementation of the method.
    """
    RedisClusterRequestTTL = 16

    NODES_CALLBACKS = dict_merge(
        string_keys_to_dict([
            "CLIENT SETNAME", "SENTINEL GET-MASTER-ADDR-BY-NAME", 'SENTINEL MASTER', 'SENTINEL MASTERS',
            'SENTINEL MONITOR', 'SENTINEL REMOVE', 'SENTINEL SENTINELS', 'SENTINEL SET',
            'SENTINEL SLAVES', 'SHUTDOWN', 'SLAVEOF', 'EVALSHA', 'SCRIPT EXISTS', 'SCRIPT KILL',
            'SCRIPT LOAD', 'MOVE', 'BITOP',
        ], blocked_command),
        string_keys_to_dict([
            "ECHO", "CONFIG GET", "CONFIG SET", "SLOWLOG GET", "CLIENT KILL", "INFO",
            "BGREWRITEAOF", "BGSAVE", "CLIENT LIST", "CLIENT GETNAME", "CONFIG RESETSTAT",
            "CONFIG REWRITE", "DBSIZE", "LASTSAVE", "PING", "SAVE", "SLOWLOG LEN", "SLOWLOG RESET",
            "TIME", "SCRIPT FLUSH", "SCAN",
        ], lambda self, command: self.connection_pool.nodes.all_nodes()),
        string_keys_to_dict([
            "FLUSHALL", "FLUSHDB",
        ], lambda self, command: self.connection_pool.nodes.all_masters()),
        string_keys_to_dict([
            "KEYS",
        ], lambda self, command: self.connection_pool.nodes.all_nodes()),
        string_keys_to_dict([
            "PUBLISH", "SUBSCRIBE",
        ], lambda self, command: [self.connection_pool.nodes.pubsub_node]),
        string_keys_to_dict([
            "RANDOMKEY",
        ], lambda self, command: [self.connection_pool.nodes.random_node()]),
    )

    RESULT_CALLBACKS = dict_merge(
        string_keys_to_dict([
            "ECHO", "CONFIG GET", "CONFIG SET", "SLOWLOG GET", "CLIENT KILL", "INFO",
            "BGREWRITEAOF", "BGSAVE", "CLIENT LIST", "CLIENT GETNAME", "CONFIG RESETSTAT",
            "CONFIG REWRITE", "DBSIZE", "LASTSAVE", "PING", "SAVE", "SLOWLOG LEN", "SLOWLOG RESET",
            "TIME", "SCRIPT FLUSH", "SCAN",
        ], lambda command, res: res),
        string_keys_to_dict([
            "FLUSHALL", "FLUSHDB",
        ], lambda command, res: res),
        string_keys_to_dict([
            "KEYS",
        ], merge_result),
        string_keys_to_dict([
            "SSCAN", "HSCAN", "ZSCAN",
        ], first_key),
        string_keys_to_dict([
            "RANDOMKEY",
        ], first_key),
    )

    def __init__(self, host=None, port=None, startup_nodes=None, max_connections=32, init_slot_cache=True, **kwargs):
        """
        startup_nodes    --> List of nodes that initial bootstrapping can be done from
        host             --> Can be used to point to a startup node
        port             --> Can be used to point to a startup node
        max_connections  --> Maximum number of connections that should be kept open at one time
        **kwargs         --> Extra arguments that will be sent into StrictRedis instance when created
                             (See Official redis-py doc for supported kwargs [https://github.com/andymccurdy/redis-py/blob/master/redis/client.py])
                             Some kwargs is not supported and will raise RedisClusterException
                              - db (Redis do not support database SELECT in cluster mode)
        """
        super(RedisCluster, self).__init__(**kwargs)

        # Tweaks to StrictRedis client arguments when running in cluster mode
        if "db" in kwargs:
            raise RedisClusterException("Argument 'db' is not possible to use in cluster mode")

        startup_nodes = [] if startup_nodes is None else startup_nodes

        # Support host/port as argument
        if host:
            startup_nodes.append({"host": host, "port": port if port else 7000})

        self.connection_pool = ClusterConnectionPool(
            startup_nodes=startup_nodes,
            init_slot_cache=init_slot_cache,
            max_connections=max_connections,
            **kwargs
        )

        self.refresh_table_asap = False

        self.nodes_callbacks = self.__class__.NODES_CALLBACKS.copy()
        self.result_callbacks = self.__class__.RESULT_CALLBACKS.copy()

    def __repr__(self):
        servers = list(set(['{}:{}'.format(nativestr(info['host']), info['port']) for info in self.connection_pool.nodes.startup_nodes]))
        servers.sort()
        return "{}<{}>".format(type(self).__name__, ','.join(servers))

    def handle_cluster_command_exception(self, e):
        info = self.parse_redirection_exception(e)
        if not info:
            raise e

        if info['action'] == "MOVED":
            self.refresh_table_asap = True
            self.slots[info['slot']] = {'host': info['host'], 'port': info['port']}
            return None
        elif info['action'] == "ASK":
            return {'host': info['host'], 'port': info['port']}
        else:
            return None

    def parse_redirection_exception(self, e):
        errv = getattr(e, "args", None)
        if not errv:
            errv = getattr(e, "message", None)
            if not errv:
                return None
        else:
            errv = errv[0]

        errv = errv.split(" ")

        if errv[0] != "MOVED" and errv[0] != "ASK":
            return None

        a = errv[2].split(":")
        return {"action": errv[0], "slot": int(errv[1]), "host": a[0], "port": int(a[1])}

    def pubsub(self, *args, **kwargs):
        return ClusterPubSub(self.connection_pool, **kwargs)

    def pipeline(self, transaction=None, shard_hint=None):
        """
        Cluster impl: Pipelines do not work in cluster mode the same way they do in normal mode.
                      Create a clone of this object so that simulating pipelines will work correctly.
                      Each command will be called directly when used and when calling execute() will only return the result stack.
        """
        if shard_hint:
            raise RedisClusterException("shard_hint is deprecated in cluster mode")

        if transaction:
            raise RedisClusterException("transaction is deprecated in cluster mode")

        return StrictClusterPipeline(
            connection_pool=self.connection_pool,
            startup_nodes=self.connection_pool.nodes.startup_nodes,
            refresh_table_asap=self.refresh_table_asap,
        )

    def transaction(self, func, *watches, **kwargs):
        raise RedisClusterException("method RedisCluster.transaction() is not implemented")

    def _determine_nodes(self, *args, **kwargs):
        """
        Determine what nodes to talk to for a specific command
        """
        command = args[0]

        if not command:
            raise RedisClusterException("Unable to determine command to use")

        if command in self.nodes_callbacks:
            return self.nodes_callbacks[command](self, command)

        # Default way to determine node
        key = args[1]

        if not key:
            raise RedisClusterException("No way to dispatch this command to Redis Cluster")

        slot = self.connection_pool.nodes.keyslot(key)
        return [self.connection_pool.get_node_by_slot(slot)]

    def _merge_result(self, command, res):
        """
        `res` is a dict with the following structure Dict(NodeName, CommandResult)
        """
        if command in self.result_callbacks:
            return self.result_callbacks[command](command, res)

        # Default way to handle result
        return first_key(command, res)

    def execute_command(self, *args, **kwargs):
        """
        Send a command to a node in the cluster
        """
        if self.refresh_table_asap:
            self.initialize_slots_cache()

        try_random_node = False
        asking = None

        res = {}
        command = args[0]
        nodes = self._determine_nodes(*args, **kwargs)

        for node in nodes:
            # Reset ttl for each node
            ttl = self.RedisClusterRequestTTL

            while ttl > 0:
                ttl -= 1
                if asking:
                    # TODO: Currently broken
                    r = self.get_redis_link(asking["host"], asking["port"])
                elif try_random_node:
                    # TODO: Untested
                    r = self.connection_pool.get_random_connection()
                    try_random_node = False
                else:
                    r = self.connection_pool.get_connection_by_node(node)

                try:
                    if asking:
                        # TODO: Currently broken as hell
                        return self.connection_pool.execute_asking_command_via_connection(r, *args, **kwargs)
                    else:
                        r.send_command(*args)
                        res[node["name"]] = self.parse_response(r, command, **kwargs)

                        # If command was successfully sent then we can break out from this while
                        # and continue with next node
                        break
                except RedisClusterException:
                    raise
                except BusyLoadingError:
                    raise
                except (ConnectionError, TimeoutError):
                    print(" *** Connection error")
                    try_random_node = True
                    if ttl < self.RedisClusterRequestTTL / 2:
                        time.sleep(0.1)
                except Exception:
                    raise
                    # TODO: Currently broken
                    # asking = self.handle_cluster_command_exception(e)
                finally:
                    self.connection_pool.release(r)

            if ttl == 0:
                raise Exception("To many Cluster redirections?")

        return self._merge_result(command, res)

    ##########
    # All methods that must have custom implementation

    def scan_iter(self, match=None, count=None):
        """
        Make an iterator using the SCAN command so that the client doesn't
        need to remember the cursor position.

        ``match`` allows for filtering the keys by pattern
        ``count`` allows for hint the minimum number of returns

        Cluster impl: Result from SCAN is different in cluster mode.
                      This method had to be adapted to fit the new result.
        """
        cursor = '0'
        while cursor != 0:
            for node, node_data in self.scan(cursor=cursor, match=match, count=count).items():
                cursor, data = node_data
                for item in data:
                    yield item

    def mget(self, keys, *args):
        """
        Returns a list of values ordered identically to ``keys``

        Cluster impl: Itterate all keys and send GET for each key.
                      This will go alot slower than a normal mget call in StrictRedis.
                      This method is no longer atomic.
        """
        return [self.get(arg) for arg in list_or_args(keys, args)]

    def mset(self, *args, **kwargs):
        """
        Sets key/values based on a mapping. Mapping can be supplied as a single
        dictionary argument or as kwargs.

        Cluster impl: Itterate over all items and do SET on each (k,v) pair
        """
        if args:
            if len(args) != 1 or not isinstance(args[0], dict):
                raise RedisError('MSET requires **kwargs or a single dict arg')
            kwargs.update(args[0])
        for pair in iteritems(kwargs):
            self.set(pair[0], pair[1])
        return True

    def msetnx(self, *args, **kwargs):
        """
        Sets key/values based on a mapping if none of the keys are already set.
        Mapping can be supplied as a single dictionary argument or as kwargs.
        Returns a boolean indicating if the operation was successful.

        Clutser impl: Itterate over all items and do GET to determine if all keys do not exists.
                      If true then call mset() on all keys.
        """
        if args:
            if len(args) != 1 or not isinstance(args[0], dict):
                raise RedisError('MSETNX requires **kwargs or a single dict arg')
            kwargs.update(args[0])

        # Itterate over all items and fail fast if one value is True.
        for k, v in kwargs.items():
            if self.get(k):
                return False

        return self.mset(**kwargs)

    def rename(self, src, dst):
        """
        Rename key ``src`` to ``dst``

        Cluster impl: This operation is no longer atomic because each key must be querried
                      then set in separate calls because they maybe will change cluster node
        """
        if src == dst:
            raise ResponseError("source and destination objects are the same")

        data = self.dump(src)
        if data is None:
            raise ResponseError("no such key")
        ttl = self.pttl(src)
        if ttl is None or ttl < 1:
            ttl = 0
        self.delete(dst)
        self.restore(dst, ttl, data)
        self.delete(src)
        return True

    def delete(self, *names):
        """
        "Delete one or more keys specified by ``names``"

        Cluster impl: Iterate all keys and send DELETE for each key.
                      This will go a lot slower than a normal delete call in StrictRedis.
                      This method is no longer atomic.
        """
        count = 0
        for arg in names:
            count += self.execute_command('DEL', arg)
        return count

    def renamenx(self, src, dst):
        """
        Rename key ``src`` to ``dst`` if ``dst`` doesn't already exist

        Cluster impl: Check if dst key do not exists, then calls rename().
                      Method is no longer atomic.
        """
        if not self.exists(dst):
            self.rename(src, dst)
        else:
            return False

    ####
    # List commands

    def brpoplpush(self, src, dst, timeout=0):
        """
        Pop a value off the tail of ``src``, push it on the head of ``dst``
        and then return it.

        This command blocks until a value is in ``src`` or until ``timeout``
        seconds elapse, whichever is first. A ``timeout`` value of 0 blocks
        forever.

        Cluster impl: Call brpop() then send the result into lpush()
                      This method is no longer atomic.
        """
        try:
            value = self.brpop(src, timeout=timeout)
            if value is None:
                return None
        except TimeoutError:
            # Timeout was reached
            return None

        self.lpush(dst, value[1])
        return value[1]

    def rpoplpush(self, src, dst):
        """
        RPOP a value off of the ``src`` list and atomically LPUSH it
        on to the ``dst`` list.  Returns the value.

        Cluster impl: Call rpop() then send the result into lpush()
                      This method is no longer atomic.
        """
        value = self.rpop(src)
        if value:
            self.lpush(dst, value)
            return value
        return None

    def sort(self, name, start=None, num=None, by=None, get=None, desc=False, alpha=False, store=None, groups=None):
        """Sort and return the list, set or sorted set at ``name``.

        ``start`` and ``num`` allow for paging through the sorted data

        ``by`` allows using an external key to weight and sort the items.
            Use an "*" to indicate where in the key the item value is located

        ``get`` allows for returning items from external keys rather than the
            sorted data itself.  Use an "*" to indicate where int he key
            the item value is located

        ``desc`` allows for reversing the sort

        ``alpha`` allows for sorting lexicographically rather than numerically

        ``store`` allows for storing the result of the sort into
            the key ``store``

        ClusterImpl: A full implementation of the server side sort mechanics because many of the
                     options work on multiple keys that can exist on multiple servers.
        """
        if (start is None and num is not None) or \
           (start is not None and num is None):
            raise RedisError("RedisError: ``start`` and ``num`` must both be specified")
        try:
            data_type = b(self.type(name))

            if data_type == b("none"):
                return []
            elif data_type == b("set"):
                data = list(self.smembers(name))[:]
            elif data_type == b("list"):
                data = self.lrange(name, 0, -1)
            else:
                raise RedisClusterException("Unable to sort data type : {}".format(data_type))
            if by is not None:
                # _sort_using_by_arg mutates data so we don't
                # need need a return value.
                self._sort_using_by_arg(data, by, alpha)
            elif not alpha:
                data.sort(key=self._strtod_key_func)
            else:
                data.sort()
            if desc:
                data = data[::-1]
            if not (start is None and num is None):
                data = data[start:start + num]

            if get:
                data = self._retrive_data_from_sort(data, get)

            if store is not None:
                if data_type == b("set"):
                    self.delete(store)
                    self.rpush(store, *data)
                elif data_type == b("list"):
                    self.delete(store)
                    self.rpush(store, *data)
                else:
                    raise RedisClusterException("Unable to store sorted data for data type : {}".format(data_type))

                return len(data)

            if groups:
                if not get or isinstance(get, basestring) or len(get) < 2:
                    raise DataError('when using "groups" the "get" argument '
                                    'must be specified and contain at least '
                                    'two keys')
                n = len(get)
                return list(izip(*[data[i::n] for i in range(n)]))
            else:
                return data
        except KeyError:
            return []

    def _retrive_data_from_sort(self, data, get):
        """
        Used by sort()
        """
        if get is not None:
            if isinstance(get, basestring):
                get = [get]
            new_data = []
            for k in data:
                for g in get:
                    single_item = self._get_single_item(k, g)
                    new_data.append(single_item)
            data = new_data
        return data

    def _get_single_item(self, k, g):
        """
        Used by sort()
        """
        if getattr(k, "decode", None):
            k = k.decode("utf-8")

        if '*' in g:
            g = g.replace('*', k)
            if '->' in g:
                key, hash_key = g.split('->')
                single_item = self.get(key, {}).get(hash_key)
            else:
                single_item = self.get(g)
        elif '#' in g:
            single_item = k
        else:
            single_item = None
        return b(single_item)

    def _strtod_key_func(self, arg):
        """
        Used by sort()
        """
        return float(arg)

    def _sort_using_by_arg(self, data, by, alpha):
        """
        Used by sort()
        """
        if getattr(by, "decode", None):
            by = by.decode("utf-8")

        def _by_key(arg):
            if getattr(arg, "decode", None):
                arg = arg.decode("utf-8")

            key = by.replace('*', arg)
            if '->' in by:
                key, hash_key = key.split('->')
                v = self.hget(key, hash_key)
                if alpha:
                    return v
                else:
                    return float(v)
            else:
                return self.get(key)
        data.sort(key=_by_key)

    ###
    # Set commands

    def sdiff(self, keys, *args):
        """
        Return the difference of sets specified by ``keys``

        Cluster impl: Querry all keys and diff all sets and return result
        """
        k = list_or_args(keys, args)
        res = self.smembers(k[0])
        for arg in k[1:]:
            res = res - self.smembers(arg)
        return res

    def sdiffstore(self, dest, keys, *args):
        """
        Store the difference of sets specified by ``keys`` into a new
        set named ``dest``.  Returns the number of keys in the new set.
        Overwrites dest key if it exists.

        Cluster impl: Use sdiff() --> Delete dest key --> store result in dest key
        """
        res = self.sdiff(keys, *args)
        self.delete(dest)
        return self.sadd(dest, *res)

    def sinter(self, keys, *args):
        """
        Return the intersection of sets specified by ``keys``

        Cluster impl: Querry all keys, intersection and return result
        """
        k = list_or_args(keys, args)
        res = self.smembers(k[0])
        for arg in k[1:]:
            res = res & self.smembers(arg)
        return res

    def sinterstore(self, dest, keys, *args):
        """
        Store the intersection of sets specified by ``keys`` into a new
        set named ``dest``.  Returns the number of keys in the new set.

        Cluster impl: Use sinter() --> Delete dest key --> store result in dest key
        """
        res = self.sinter(keys, *args)
        self.delete(dest)
        if len(res) != 0:
            self.sadd(dest, *res)
            return len(res)
        else:
            return 0

    def smove(self, src, dst, value):
        """
        Move ``value`` from set ``src`` to set ``dst`` atomically

        Cluster impl: SMEMBERS --> SREM --> SADD. Function is no longer atomic.
        """
        res = self.srem(src, value)

        # Only add the element if existed in src set
        if res == 1:
            self.sadd(dst, value)

        return res

    def sunion(self, keys, *args):
        """
        Return the union of sets specified by ``keys``

        Cluster impl: Querry all keys, union and return result
        """
        k = list_or_args(keys, args)
        res = self.smembers(k[0])
        for arg in k[1:]:
            res = res | self.smembers(arg)
        return res

    def sunionstore(self, dest, keys, *args):
        """
        Store the union of sets specified by ``keys`` into a new
        set named ``dest``.  Returns the number of keys in the new set.

        Cluster impl: Use sunion() --> Dlete dest key --> store result in dest key
        """
        res = self.sunion(keys, *args)
        self.delete(dest)
        return self.sadd(dest, *res)

    def pfmerge(self, dest, *sources):
        """
        Merge N different HyperLogLogs into a single one.

        Cluster impl: Very special implementation is required to make pfmerge() work
                      But it works :]
                      It works by first fetching all HLL objects that should be merged and
                      move them to one hashslot so that pfmerge operation can be performed without
                      any 'CROSSSLOT' error.
                      After the PFMERGE operation is done then it will be moved to the correct location
                      within the cluster and cleanup is done.

                      This operation is no longer atomic because of all the operations that has to be done.
        """
        all_k = []

        # Fetch all HLL objects via GET and store them client side as strings
        all_hll_objects = [self.get(hll_key) for hll_key in sources]

        # Randomize a keyslot hash that should be used inside {} when doing SET
        random_hash_slot = self._random_id()

        # Special handling of dest variable if it allready exists, then it shold be included in the HLL merge
        # dest can exists anywhere in the cluster.
        dest_data = self.get(dest)
        if dest_data:
            all_hll_objects.append(dest_data)

        # SET all stored HLL objects with SET {RandomHash}RandomKey hll_obj
        for hll_object in all_hll_objects:
            k = self._random_good_hashslot_key(random_hash_slot)
            all_k.append(k)
            self.set(k, hll_object)

        # Do regular PFMERGE operation and store value in random key in {RandomHash}
        tmp_dest = self._random_good_hashslot_key(random_hash_slot)
        self.execute_command("PFMERGE", tmp_dest, *all_k)

        # Do GET and SET so that result will be stored in the destination object any where in the cluster
        parsed_dest = self.get(tmp_dest)
        self.set(dest, parsed_dest)

        # Cleanup tmp variables
        self.delete(tmp_dest)
        for k in all_k:
            self.delete(k)

        return True

    def _random_good_hashslot_key(self, hashslot):
        """
        Generate a good random key with a low probability of collision between any other key.
        """
        # TODO: Check if the key exists or not. continue to randomize until a empty key is found
        random_id = "{%s}%s" % (hashslot, self._random_id())
        return random_id

    def _random_id(self, size=16, chars=string.ascii_uppercase + string.digits):
        return ''.join(random.choice(chars) for _ in range(size))

#####
# Path all methods that requires it. This will avoid reimplement some methods in RedisCluster class

# All commands that shold be blocked
RedisCluster.watch = block_command(StrictRedis.watch)
RedisCluster.unwatch = block_command(StrictRedis.unwatch)
RedisCluster.register_script = block_command(StrictRedis.register_script)

# A custom command handler for eval. It's interface is different from most other redis commands.
# (keys show up after the first 2 args and are variable)
# Verifies all keys belong to the same hashed key slot and fetches the connection based on that slot.
RedisCluster.eval = send_eval_to_connection(StrictRedis.eval)


class StrictClusterPipeline(BaseClusterPipeline, RedisCluster):
    """Pipeline for the StrictRedis class"""
    pass


class ClusterPubSub(PubSub):

    def __init__(self, *args, **kwargs):
        super(ClusterPubSub, self).__init__(*args, **kwargs)

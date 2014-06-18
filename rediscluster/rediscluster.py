# -*- coding: utf-8 -*-

# python std lib
import random

# rediscluster imports
from .crc import crc16
from .exceptions import RedisClusterException, RedisClusterError
from .decorators import (send_to_connection_by_key, 
                         send_to_all_master_nodes, 
                         send_to_all_masters_merge_list, 
                         send_to_all_nodes, 
                         send_to_all_nodes_merge_list, 
                         get_connection_from_node_obj, 
                         block_command)

# 3rd party imports
import redis
from redis import StrictRedis
from redis.client import list_or_args
from redis._compat import iteritems, basestring, b, izip
from redis.exceptions import RedisError, ResponseError, TimeoutError, DataError
from redis.connection import Token


class RedisCluster(StrictRedis):
    """
    If a command is implemented over the one in StrictRedis then it requires some changes compared to
    the regular implementation of the method.
    """
    RedisClusterHashSlots = 16384
    RedisClusterRequestTTL = 16
    RedisClusterDefaultTimeout = 1

    def __init__(self, startup_nodes=[], max_connections=32, init_slot_cache=True, **kwargs):
        """
        startup_nodes     --> List of nodes that initial bootstrapping can be done from
        max_connections   --> Maximum number of connections that should be kept open at one time
        **kwargs          --> Extra arguments that will be sent into StrictRedis instance when created
                              (See Official redis-py doc for supported kwargs [https://github.com/andymccurdy/redis-py/blob/master/redis/client.py])
                              Some kwargs is not supported and will raise RedisClusterException
                               - db    (Redis do not support database SELECT in cluster mode)
                               - host  (Redis provides this when bootstrapping the cluster)
                               - port  (Redis provides this when bootstrapping the cluster)
        """
        super(RedisCluster, self).__init__(**kwargs)

        self.startup_nodes = startup_nodes
        self.max_connections = max_connections
        self.connections = {}
        self.opt = kwargs
        self.refresh_table_asap = False
        self.result_stack = []

        # Tweaks to StrictRedis client arguments when running in cluster mode
        if "socket_timeout" not in self.opt:
            self.opt["socket_timeout"] = RedisCluster.RedisClusterDefaultTimeout
        if "db" in self.opt:
            raise RedisClusterException("(error) [Remove 'db' from kwargs]")
        if "host" in self.opt:
            raise RedisClusterException("(error) [Remove 'host' from kwargs]")
        if "port" in self.opt:
            raise RedisClusterException("(error) [Remove 'port' from kwargs]")

        if init_slot_cache:
            self.initialize_slots_cache()

    def get_redis_link_from_node(self, node_obj):
        return self.get_redis_link(node_obj["host"], node_obj["port"])

    def get_redis_link(self, host, port):
        """
        Open new connection to a redis server and return the connection object
        """
        try:
            return redis.StrictRedis(host=host, port=port, **self.opt)
        except Exception as e:
            raise RedisClusterException(repr(e))

    def set_node_name(self, n):
        """
        Format the name for the given node object
        """
        if "name" not in n:
            n["name"] = "{0}:{1}".format(n["host"], n["port"])

    def initialize_slots_cache(self):
        """
        Init the slots cache by asking all startup nodes what the current cluster configuration is
        """
        for node in self.startup_nodes:
            try:
                self.slots = {}
                self.nodes = []

                r = self.get_redis_link(node["host"], node["port"])
                resp = r.execute_command("cluster", "nodes")

                if getattr(resp, "decode", None):
                    resp = resp.decode("utf-8")

                for line in resp.split("\n"):
                    fields = line.split(" ")
                    if len(fields) == 1:
                        # We have an empty row so do not parse it
                        continue

                    addr = fields[1]
                    slots = fields[8:]
                    server_type = fields[2]
                    if addr == ":0":  # this is self
                        addr = "{0}:{1}".format(node["host"], node["port"])
                    addr_ip, addr_port = addr.split(":")
                    addr_port = int(addr_port)

                    s = server_type.split(",")
                    addr = {"host": addr_ip, "port": addr_port, "name": addr, "server_type": server_type if len(s) == 1 else s[1]}
                    self.nodes.append(addr)

                    for range_ in slots:
                        if "-" in range_:
                            first, last = range_.split("-")
                        else:
                            first = last = range_
                        for i in range(int(first), int(last) + 1):
                            self.slots[i] = addr

                self.populate_startup_nodes()
                self.refresh_table_asap = False
            except RedisClusterException:
                raise
            except Exception as e:
                print(" EXCEPTION : {}".format(e))
                raise

    def populate_startup_nodes(self):
        """
        Do something with all startup nodes and filters out any duplicates
        """
        for item in self.startup_nodes:
            self.set_node_name(item)
        for n in self.nodes:
            if n not in self.startup_nodes:
                self.startup_nodes.append(n)
        # freeze it so we can set() it
        uniq = set([frozenset(node.items()) for node in self.startup_nodes])
        # then thaw it back out into a list of dicts
        self.startup_nodes = [dict(node) for node in uniq]

    def flush_slots_cache(self):
        """
        Reset slots cache back to empty dict
        """
        self.slots = {}

    def keyslot(self, key):
        """
        Calculate keyslot for a given key
        """
        start = key.find("{")
        if start > -1:
            end = key.find("}", start + 1)
            if end > -1 and end != start + 1:
                key = key[start + 1:end]
        return crc16(key) % self.RedisClusterHashSlots

    def close_existing_connection(self):
        """
        Close random connections until open connections >= max_connections
        """
        # TODO: It could be possible that this code will get stuck in a infinite loop. It must be fixed
        while len(self.connections) >= self.max_connections:
            # Shuffle all connections and close the first one in the list.
            random.shuffle(self.startup_nodes)
            connection = self.connections.get(self.startup_nodes[0]["name"], None)
            if connection:
                self.close_redis_connection(connection)
                del self.connections[self.startup_nodes[0]["name"]]

    def close_redis_connection(self, connection):
        """
        Close a redis connection by disconnecting all connections in connection_pool
        """
        try:
            connection.connection_pool.disconnect()
        except Exception as e:
            raise RedisClusterException("Error when closing random connection... {}".format(repr(e)))

    def get_random_connection(self):
        """
        Open new connection to random redis server.
        """
        random.shuffle(self.startup_nodes)
        for node in self.startup_nodes:
            try:
                self.set_node_name(node)
                conn = self.connections.get(node["name"], None)

                if not conn:
                    conn = self.get_redis_link(node["host"], int(node["port"]))
                    if conn.ping() is True:
                        self.close_existing_connection()
                        self.connections[node["name"]] = conn
                        return conn
                    else:
                        # TODO: This do not work proper yet
                        # conn.connection.disconnect()
                        pass
                else:
                    if conn.ping() is True:
                        return conn
            except RedisClusterException:
                raise
            except Exception:
                # Just try with the next node
                pass

        raise Exception("Cant reach a single startup node.")

    def get_connection_by_key(self, key):
        if not key:
            raise Exception("No way to dispatch this command to Redis Cluster.")
        return self.get_connection_by_slot(self.keyslot(key))

    def get_connection_by_slot(self, slot):
        """
        Determine what server a specific slot belongs to and return a redis object that is connected
        """
        node = self.slots[slot]
        if not node:
            return self.get_random_connection()
        self.set_node_name(node)
        if not self.connections.get(node["name"], None):
            try:
                self.close_existing_connection()
                self.connections[node["name"]] = self.get_redis_link(node["host"], node["port"])
            except RedisClusterException:
                raise
            except Exception:
                # This will probably never happen with recent redis-rb
                # versions because the connection is enstablished in a lazy
                # way only when a command is called. However it is wise to
                # handle an instance creation error of some kind.
                return self.get_random_connection()
        return self.connections[node["name"]]

    def send_cluster_command(self, *argv, **kwargs):
        """
        Send a cluster command to the redis cluster.
        """
        if self.refresh_table_asap:
            self.initialize_slots_cache()

        ttl = self.RedisClusterRequestTTL
        asking = False
        try_random_node = False
        while ttl > 0:
            ttl -= 1
            if try_random_node:
                r = self.get_random_connection()
                try_random_node = False
            else:
                key = argv[1]
                if not key:
                    raise Exception("No way to dispatch this command to Redis Cluster.")
                slot = self.keyslot(key)
                r = self.get_connection_by_slot(slot)

            try:
                asking = False
                return r.execute_command(*argv, **kwargs)
            # TODO: Convert this from Ruby
            # rescue Errno::ECONNREFUSED, Redis::TimeoutError, Redis::CannotConnectError, Errno::EACCES
            #     try_random_node = true
            #     sleep(0.1) if ttl < RedisClusterRequestTTL/2
            except Exception as e:
                # try_random_node = True
                # if ttl < self.RedisClusterRequestTTL / 2:
                #     time.sleep(0.1)

                errv = getattr(e, "args", None)
                if not errv:
                    errv = getattr(e, "message", None)
                    if not errv:
                        raise RedisClusterException("Missing attribute : 'args' or 'message' in exception : {}".format(e))
                else:
                    errv = errv[0]

                errv = errv.split(" ")
                if errv[0] == "MOVED" or errv[0] == "ASK":
                    if errv[0] == "ASK":
                        # TODO: Implement asking, whatever that is Oo
                        print(" ** ASKING...")
                        asking = True
                    else:
                        # Serve replied with MOVED. It's better for us to
                        # ask for CLUSTER NODES the next time.
                        self.refresh_table_asap = True

                    a = errv[2].split(":")
                    self.slots[int(errv[1])] = {"host": a[0], "port": int(a[1])}
                else:
                    raise

        raise Exception("To many Cluster redirections?")

    ##########
    # Pipeline methods

    def __len__(self):
        """
        Cluster impl: Used by pipelines
        """
        return len(self.result_stack)

    def __del__(self):
        """
        Cluster impl: Used by pipelines
        """
        try:
            self.reset()
        except Exception:
            pass

    def __enter__(self):
        """
        Cluster impl: Used by pipelines to enable 'with' usage
        """
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Cluster impl: Used by pipelines
        """
        self.reset()

    def reset(self):
        """
        Cluster impl: Used by pipelines
        """
        self.result_stack = []

    def execute(self, *args, **kwargs):
        """
        Cluster impl: Used by pipelines
        """
        # TODO: Should execute() reset the result_stack variable?
        return self.result_stack

    def pipeline(self):
        """
        Cluster impl: Pipelines do not work in cluster mode the same way they do in normal mode.
                      Create a clone of this object so that simulating pipelines will work correctly.
                      Each command will be called directly when used and when calling execute() will only return the result stack.
        """
        r = RedisCluster(startup_nodes=self.startup_nodes,
                         max_connections=self.max_connections,
                         init_slot_cache=False)
        r.connections = self.connections
        r.opt = self.opt
        r.refresh_table_asap = self.refresh_table_asap
        r.slots = self.slots
        r.nodes = self.nodes
        return r

    def execute_command(self, *args, **kwargs):
        """
        Cluster impl: Overwrite method in StrictRedis so that we can use the functions that works from StrictRedis
        """
        res = self.send_cluster_command(*args, **kwargs)
        self.result_stack.append(res)
        return res

    ##########
    # All methods that must have custom implementation

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

    def randomkey(self):
        """
        Returns the name of a random key from a random node in the cluster

        Cluster impl: Pick a random connection and send 'RANDOMKEY'
        """
        return self.get_random_connection().execute_command('RANDOMKEY')

    # TODO: Some more work is required.
    def rename(self, src, dst):
        """
        Rename key ``src`` to ``dst``

        Cluster impl: This operation is no longer atomic because each key must be querried
                      then set in separate calls because they maybe will change cluster node

        Currently works with

         - Normal keys (GET --> SET)
         - Hash keys (HGETALL --> HMSET)
         - Sets (SMEMBERS --> SADD)
         - Sorted Sets (ZRANGE --> ZADD)
         - Lists (LRANGE --> RPUSH)
         - TODO: HyperLogLog objects
        """
        if src == dst:
            raise RedisClusterException("src and dst cannot be the same key...")

        if not self.exists(src):
            raise ResponseError("no such key")

        t = self.type(src)

        if t == b("string"):
            v = self.get(src)
            self.delete(src)
            self.delete(dst)
            self.set(dst, v)
        elif t == b("hash"):
            values = self.hgetall(src)
            self.delete(src)
            self.delete(dst)
            self.hmset(dst, values)
        elif t == b("set"):
            values = self.smembers(src)
            self.delete(src)
            self.delete(dst)
            self.sadd(dst, values)
        elif t == b("zset"):
            values = self.zrange("myzset", 0, -1, withscores=True)
            self.delete(src)
            self.delete(dst)
            # Remap values so they can be sent into ZADD
            self.zadd(dst, *[j for i in values for j in i[::-1]])
        elif t == b("list"):
            values = self.lrange(src, 0, -1)
            self.delete(src)
            self.delete(dst)
            self.rpush(dst, *values)
        else:
            raise RedisClusterException("Unknown keytype when calling cluster version of rename method : {}".format(t))

        return True

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
    # Scan commands

    def scan_iter(self, match=None, count=None):
        """
        Make an iterator using the SCAN command so that the client doesn't
        need to remember the cursor position.

        ``match`` allows for filtering the keys by pattern

        ``count`` allows for hint the minimum number of returns

        Cluster impl: Itterate over all connections and yield each item one after another
        """
        for node in self.startup_nodes:
            if node.get("server_type", "master") != "master":
                continue

            conn = get_connection_from_node_obj(self, node)
            cursor = '0'
            while cursor != 0:
                cursor, data = conn.scan(cursor=cursor, match=match, count=count)
                for item in data:
                    yield item

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


#####
# Path all methods that requires it. This will avoid reimplement some methods in RedisCluster class

# All commands that should be sent to all nodes and return result as a dict
RedisCluster.bgrewriteaof = send_to_all_nodes(StrictRedis.bgrewriteaof)
RedisCluster.bgsave = send_to_all_nodes(StrictRedis.bgsave)
RedisCluster.client_kill = send_to_all_nodes(StrictRedis.client_kill)
RedisCluster.client_list = send_to_all_nodes(StrictRedis.client_list)
RedisCluster.client_getname = send_to_all_nodes(StrictRedis.client_getname)
RedisCluster.config_get = send_to_all_nodes(StrictRedis.config_get)
RedisCluster.config_set = send_to_all_nodes(StrictRedis.config_set)
RedisCluster.config_resetstat = send_to_all_nodes(StrictRedis.config_resetstat)
RedisCluster.config_rewrite = send_to_all_nodes(StrictRedis.config_rewrite)
RedisCluster.dbsize = send_to_all_nodes(StrictRedis.dbsize)
RedisCluster.echo = send_to_all_nodes(StrictRedis.echo)
RedisCluster.info = send_to_all_nodes(StrictRedis.info)
RedisCluster.lastsave = send_to_all_nodes(StrictRedis.lastsave)
RedisCluster.ping = send_to_all_nodes(StrictRedis.ping)
RedisCluster.save = send_to_all_nodes(StrictRedis.save)
RedisCluster.slowlog_get = send_to_all_nodes(StrictRedis.slowlog_get)
RedisCluster.slowlog_len = send_to_all_nodes(StrictRedis.slowlog_len)
RedisCluster.slowlog_reset = send_to_all_nodes(StrictRedis.slowlog_reset)
RedisCluster.time = send_to_all_nodes(StrictRedis.time)

# All commands that shold be sent to all nodes and return result as a unified list and not dict
RedisCluster.keys = send_to_all_nodes_merge_list(StrictRedis.keys)

# All commands that should be sent to only master nodes
RedisCluster.flushall = send_to_all_master_nodes(StrictRedis.flushall)
RedisCluster.flushdb = send_to_all_master_nodes(StrictRedis.flushdb)
RedisCluster.scan = send_to_all_master_nodes(StrictRedis.scan)

# All commands that should fetch the connection object based on a key and then call command in StrictRedis
RedisCluster.sscan = send_to_connection_by_key(StrictRedis.sscan)
RedisCluster.sscan_iter = send_to_connection_by_key(StrictRedis.sscan_iter)
RedisCluster.hscan = send_to_connection_by_key(StrictRedis.hscan)
RedisCluster.hscan_iter = send_to_connection_by_key(StrictRedis.hscan_iter)
RedisCluster.zscan = send_to_connection_by_key(StrictRedis.zscan)
RedisCluster.zscan_iter = send_to_connection_by_key(StrictRedis.zscan_iter)

# All commands that shold be blocked
RedisCluster.client_setname = block_command(StrictRedis.client_setname)
RedisCluster.sentinel = block_command(StrictRedis.sentinel)
RedisCluster.sentinel_get_master_addr_by_name = block_command(StrictRedis.sentinel_get_master_addr_by_name)
RedisCluster.sentinel_master = block_command(StrictRedis.sentinel_master)
RedisCluster.sentinel_masters = block_command(StrictRedis.sentinel_masters)
RedisCluster.sentinel_monitor = block_command(StrictRedis.sentinel_monitor)
RedisCluster.sentinel_remove = block_command(StrictRedis.sentinel_remove)
RedisCluster.sentinel_sentinels = block_command(StrictRedis.sentinel_sentinels)
RedisCluster.sentinel_set = block_command(StrictRedis.sentinel_set)
RedisCluster.sentinel_slaves = block_command(StrictRedis.sentinel_slaves)
RedisCluster.shutdown = block_command(StrictRedis.shutdown)  # Danger to shutdown entire cluster at same time
RedisCluster.slaveof = block_command(StrictRedis.slaveof)  # Cluster management should be done via redis-trib.rb manually
RedisCluster.restore = block_command(StrictRedis.restore)
RedisCluster.watch = block_command(StrictRedis.watch)
RedisCluster.unwatch = block_command(StrictRedis.unwatch)
RedisCluster.pfmerge = block_command(StrictRedis.pfmerge)  # Will not work because merging HLL in python is extremly complex currently...
RedisCluster.publish = block_command(StrictRedis.publish)
RedisCluster.eval = block_command(StrictRedis.eval)
RedisCluster.evalsha = block_command(StrictRedis.evalsha)
RedisCluster.script_exists = block_command(StrictRedis.script_exists)
RedisCluster.script_flush = block_command(StrictRedis.script_flush)
RedisCluster.script_kill = block_command(StrictRedis.script_kill)
RedisCluster.script_load = block_command(StrictRedis.script_load)
RedisCluster.register_script = block_command(StrictRedis.register_script)
RedisCluster.move = block_command(StrictRedis.move)  # It is not possible to move a key from one db to another in cluster mode
RedisCluster.bitop = block_command(StrictRedis.bitop)  # Currently to hard to implement a solution in python space
RedisCluster.zinterstore = block_command(StrictRedis.zinterstore)  # TODO: Need impl
RedisCluster.zunionstore = block_command(StrictRedis.zunionstore)  # TODO: Need impl

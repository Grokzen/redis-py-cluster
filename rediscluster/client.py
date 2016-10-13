# -*- coding: utf-8 -*-

# python std lib
import datetime
import random
import string
import time

# rediscluster imports
from .connection import ClusterConnectionPool, ClusterReadOnlyConnectionPool
from .exceptions import (
    RedisClusterException, AskError, MovedError, ClusterDownError,
    ClusterError, TryAgainError,
)
from .pubsub import ClusterPubSub
from .utils import (
    bool_ok,
    string_keys_to_dict,
    dict_merge,
    blocked_command,
    merge_result,
    first_key,
    clusterdown_wrapper,
    parse_cluster_slots,
    parse_cluster_nodes,
)
# 3rd party imports
from redis import StrictRedis
from redis.client import list_or_args, parse_info
from redis.connection import Token
from redis._compat import iteritems, basestring, b, izip, nativestr, long
from redis.exceptions import RedisError, ResponseError, TimeoutError, DataError, ConnectionError, BusyLoadingError


class StrictRedisCluster(StrictRedis):
    """
    If a command is implemented over the one in StrictRedis then it requires some changes compared to
    the regular implementation of the method.
    """
    RedisClusterRequestTTL = 16

    NODES_FLAGS = dict_merge(
        string_keys_to_dict([
            "CLIENT SETNAME", "SENTINEL GET-MASTER-ADDR-BY-NAME", 'SENTINEL MASTER', 'SENTINEL MASTERS',
            'SENTINEL MONITOR', 'SENTINEL REMOVE', 'SENTINEL SENTINELS', 'SENTINEL SET',
            'SENTINEL SLAVES', 'SHUTDOWN', 'SLAVEOF', 'SCRIPT KILL',
            'MOVE', 'BITOP',
        ], 'blocked'),
        string_keys_to_dict([
            "ECHO", "CONFIG GET", "CONFIG SET", "SLOWLOG GET", "CLIENT KILL", "INFO",
            "BGREWRITEAOF", "BGSAVE", "CLIENT LIST", "CLIENT GETNAME", "CONFIG RESETSTAT",
            "CONFIG REWRITE", "DBSIZE", "LASTSAVE", "PING", "SAVE", "SLOWLOG LEN", "SLOWLOG RESET",
            "TIME", "KEYS", "CLUSTER INFO",
        ], 'all-nodes'),
        string_keys_to_dict([
            "FLUSHALL", "FLUSHDB", "SCRIPT LOAD", "SCRIPT FLUSH", "SCRIPT EXISTS", "SCAN",
        ], 'all-masters'),
        string_keys_to_dict([
            "RANDOMKEY", "CLUSTER NODES", 'CLUSTER SLOTS',
        ], 'random'),
        string_keys_to_dict([
            "CLUSTER COUNTKEYSINSLOT",
        ], 'slot-id'),
    )

    RESULT_CALLBACKS = dict_merge(
        string_keys_to_dict([
            "ECHO", "CONFIG GET", "CONFIG SET", "SLOWLOG GET", "CLIENT KILL", "INFO",
            "BGREWRITEAOF", "BGSAVE", "CLIENT LIST", "CLIENT GETNAME", "CONFIG RESETSTAT",
            "CONFIG REWRITE", "DBSIZE", "LASTSAVE", "PING", "SAVE", "SLOWLOG LEN", "SLOWLOG RESET",
            "TIME", "SCAN", "CLUSTER INFO", 'CLUSTER ADDSLOTS', 'CLUSTER COUNT-FAILURE-REPORTS',
            'CLUSTER DELSLOTS', 'CLUSTER FAILOVER', 'CLUSTER FORGET', "FLUSHALL", "FLUSHDB",
        ], lambda command, res: res),
        string_keys_to_dict([
            "SCRIPT LOAD",
        ], lambda command, res: list(res.values()).pop()),
        string_keys_to_dict([
            "SCRIPT EXISTS",
        ], lambda command, res: [all(k) for k in zip(*res.values())]),
        string_keys_to_dict([
            "SCRIPT FLUSH",
        ], lambda command, res: all(res.values())),
        string_keys_to_dict([
            "KEYS",
        ], merge_result),
        string_keys_to_dict([
            "SSCAN", "HSCAN", "ZSCAN", "RANDOMKEY",
        ], first_key),
    )

    CLUSTER_COMMANDS_RESPONSE_CALLBACKS = {
        'CLUSTER ADDSLOTS': bool_ok,
        'CLUSTER COUNT-FAILURE-REPORTS': int,
        'CLUSTER COUNTKEYSINSLOT': int,
        'CLUSTER DELSLOTS': bool_ok,
        'CLUSTER FAILOVER': bool_ok,
        'CLUSTER FORGET': bool_ok,
        'CLUSTER GETKEYSINSLOT': int,
        'CLUSTER INFO': parse_info,
        'CLUSTER KEYSLOT': int,
        'CLUSTER MEET': bool_ok,
        'CLUSTER NODES': parse_cluster_nodes,
        'CLUSTER REPLICATE': bool_ok,
        'CLUSTER RESET': bool_ok,
        'CLUSTER SAVECONFIG': bool_ok,
        'CLUSTER SET-CONFIG-EPOCH': bool_ok,
        'CLUSTER SETSLOT': bool_ok,
        'CLUSTER SLAVES': parse_cluster_nodes,
        'CLUSTER SLOTS': parse_cluster_slots,
        'ASKING': bool_ok,
        'READONLY': bool_ok,
        'READWRITE': bool_ok,
    }

    def __init__(self, host=None, port=None, startup_nodes=None, max_connections=32, max_connections_per_node=False, init_slot_cache=True,
                 readonly_mode=False, reinitialize_steps=None, **kwargs):
        """
        :startup_nodes:
            List of nodes that initial bootstrapping can be done from
        :host:
            Can be used to point to a startup node
        :port:
            Can be used to point to a startup node
        :max_connections:
            Maximum number of connections that should be kept open at one time
        :readonly_mode:
            enable READONLY mode. You can read possibly stale data from slave.
        :**kwargs:
            Extra arguments that will be sent into StrictRedis instance when created
            (See Official redis-py doc for supported kwargs
            [https://github.com/andymccurdy/redis-py/blob/master/redis/client.py])
            Some kwargs is not supported and will raise RedisClusterException
            - db (Redis do not support database SELECT in cluster mode)
        """
        # Tweaks to StrictRedis client arguments when running in cluster mode
        if "db" in kwargs:
            raise RedisClusterException("Argument 'db' is not possible to use in cluster mode")

        if "connection_pool" in kwargs:
            pool = kwargs.pop('connection_pool')
        else:
            startup_nodes = [] if startup_nodes is None else startup_nodes

            # Support host/port as argument
            if host:
                startup_nodes.append({"host": host, "port": port if port else 7000})

            if readonly_mode:
                connection_pool_cls = ClusterReadOnlyConnectionPool
            else:
                connection_pool_cls = ClusterConnectionPool

            pool = connection_pool_cls(
                startup_nodes=startup_nodes,
                init_slot_cache=init_slot_cache,
                max_connections=max_connections,
                reinitialize_steps=reinitialize_steps,
                max_connections_per_node=max_connections_per_node,
                **kwargs
            )

        super(StrictRedisCluster, self).__init__(connection_pool=pool, **kwargs)

        self.refresh_table_asap = False
        self.nodes_flags = self.__class__.NODES_FLAGS.copy()
        self.result_callbacks = self.__class__.RESULT_CALLBACKS.copy()
        self.response_callbacks = self.__class__.RESPONSE_CALLBACKS.copy()
        self.response_callbacks = dict_merge(self.response_callbacks, self.CLUSTER_COMMANDS_RESPONSE_CALLBACKS)

    def __repr__(self):
        """
        """
        servers = list({'{0}:{1}'.format(nativestr(info['host']), info['port']) for info in self.connection_pool.nodes.startup_nodes})
        servers.sort()
        return "{0}<{1}>".format(type(self).__name__, ', '.join(servers))

    def pubsub(self, **kwargs):
        """
        """
        return ClusterPubSub(self.connection_pool, **kwargs)

    def pipeline(self, transaction=None, shard_hint=None):
        """
        Cluster impl:
            Pipelines do not work in cluster mode the same way they do in normal mode.
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
            result_callbacks=self.result_callbacks,
            response_callbacks=self.response_callbacks,
        )

    def transaction(self, *args, **kwargs):
        """
        Transaction is not implemented in cluster mode yet.
        """
        raise RedisClusterException("method StrictRedisCluster.transaction() is not implemented")

    def _determine_slot(self, *args):
        """
        figure out what slot based on command and args
        """
        if len(args) <= 1:
            raise RedisClusterException("No way to dispatch this command to Redis Cluster. Missing key.")
        command = args[0]

        if command in ['EVAL', 'EVALSHA']:
            numkeys = args[2]
            keys = args[3: 3 + numkeys]
            slots = {self.connection_pool.nodes.keyslot(key) for key in keys}
            if len(slots) != 1:
                raise RedisClusterException("{0} - all keys must map to the same key slot".format(command))
            return slots.pop()

        key = args[1]

        return self.connection_pool.nodes.keyslot(key)

    def _merge_result(self, command, res):
        """
        `res` is a dict with the following structure Dict(NodeName, CommandResult)
        """
        if command in self.result_callbacks:
            return self.result_callbacks[command](command, res)

        # Default way to handle result
        return first_key(command, res)

    def determine_node(self, *args, **kwargs):
        """
        """
        command = args[0]
        node_flag = self.nodes_flags.get(command)

        if node_flag == 'blocked':
            return blocked_command(self, command)
        elif node_flag == 'random':
            return [self.connection_pool.nodes.random_node()]
        elif node_flag == 'all-masters':
            return self.connection_pool.nodes.all_masters()
        elif node_flag == 'all-nodes':
            return self.connection_pool.nodes.all_nodes()
        elif node_flag == 'slot-id':
            return [self.connection_pool.nodes.node_from_slot(args[1])]
        else:
            return None

    @clusterdown_wrapper
    def execute_command(self, *args, **kwargs):
        """
        Send a command to a node in the cluster
        """
        if not args:
            raise RedisClusterException("Unable to determine command to use")

        command = args[0]

        node = self.determine_node(*args, **kwargs)
        if node:
            return self._execute_command_on_nodes(node, *args, **kwargs)

        # If set externally we must update it before calling any commands
        if self.refresh_table_asap:
            self.connection_pool.nodes.initialize()
            self.refresh_table_asap = False

        redirect_addr = None
        asking = False

        try_random_node = False
        slot = self._determine_slot(*args)
        ttl = int(self.RedisClusterRequestTTL)

        while ttl > 0:
            ttl -= 1

            if asking:
                node = self.connection_pool.nodes.nodes[redirect_addr]
                r = self.connection_pool.get_connection_by_node(node)
            elif try_random_node:
                r = self.connection_pool.get_random_connection()
                try_random_node = False
            else:
                if self.refresh_table_asap:
                    # MOVED
                    node = self.connection_pool.get_master_node_by_slot(slot)
                else:
                    node = self.connection_pool.get_node_by_slot(slot)
                r = self.connection_pool.get_connection_by_node(node)

            try:
                if asking:
                    r.send_command('ASKING')
                    self.parse_response(r, "ASKING", **kwargs)
                    asking = False

                r.send_command(*args)
                return self.parse_response(r, command, **kwargs)
            except (RedisClusterException, BusyLoadingError):
                raise
            except (ConnectionError, TimeoutError):
                try_random_node = True

                if ttl < self.RedisClusterRequestTTL / 2:
                    time.sleep(0.1)
            except ClusterDownError as e:
                self.connection_pool.disconnect()
                self.connection_pool.reset()
                self.refresh_table_asap = True

                raise e
            except MovedError as e:
                # Reinitialize on ever x number of MovedError.
                # This counter will increase faster when the same client object
                # is shared between multiple threads. To reduce the frequency you
                # can set the variable 'reinitialize_steps' in the constructor.
                self.refresh_table_asap = True
                self.connection_pool.nodes.increment_reinitialize_counter()

                node = self.connection_pool.nodes.set_node(e.host, e.port, server_type='master')
                self.connection_pool.nodes.slots[e.slot_id][0] = node
            except TryAgainError as e:
                if ttl < self.RedisClusterRequestTTL / 2:
                    time.sleep(0.05)
            except AskError as e:
                redirect_addr, asking = "{0}:{1}".format(e.host, e.port), True
            finally:
                self.connection_pool.release(r)

        raise ClusterError('TTL exhausted.')

    def _execute_command_on_nodes(self, nodes, *args, **kwargs):
        """
        """
        command = args[0]
        res = {}

        for node in nodes:
            connection = self.connection_pool.get_connection_by_node(node)

            # copy from redis-py
            try:
                connection.send_command(*args)
                res[node["name"]] = self.parse_response(connection, command, **kwargs)
            except (ConnectionError, TimeoutError) as e:
                connection.disconnect()

                if not connection.retry_on_timeout and isinstance(e, TimeoutError):
                    raise

                connection.send_command(*args)
                res[node["name"]] = self.parse_response(connection, command, **kwargs)
            finally:
                self.connection_pool.release(connection)

        return self._merge_result(command, res)

    ##########
    # Cluster management commands

    def _nodes_slots_to_slots_nodes(self, mapping):
        """
        Converts a mapping of
        {id: <node>, slots: (slot1, slot2)}
        to
        {slot1: <node>, slot2: <node>}

        Operation is expensive so use with caution
        """
        out = {}
        for node in mapping:
            for slot in node['slots']:
                out[str(slot)] = node['id']
        return out

    def cluster_addslots(self, node_id, *slots):
        """
        Assign new hash slots to receiving node

        Sends to specefied node
        """
        return self.execute_command('CLUSTER ADDSLOTS', *slots, node_id=node_id)

    def cluster_countkeysinslot(self, slot_id):
        """
        Return the number of local keys in the specified hash slot

        Send to node based on specefied slot_id
        """
        return self.execute_command('CLUSTER COUNTKEYSINSLOT', slot_id)

    def cluster_count_failure_report(self, node_id):
        """
        Return the number of failure reports active for a given node

        Sends to specefied node
        """
        return self.execute_command('CLUSTER COUNT-FAILURE-REPORTS', node_id=node_id)

    def cluster_delslots(self, *slots):
        """
        Set hash slots as unbound in the cluster.
        It determines by it self what node the slot is in and sends it there

        Returns a list of the results for each processed slot.
        """
        cluster_nodes = self._nodes_slots_to_slots_nodes(self.cluster_nodes())

        return [
            self.execute_command('CLUSTER DELSLOTS', slot, node_id=cluster_nodes[slot])
            for slot in slots
        ]

    def cluster_failover(self, node_id, option):
        """
        Forces a slave to perform a manual failover of its master

        Sends to specefied node
        """
        assert option.upper() in ('FORCE', 'TAKEOVER')  # TODO: change this option handling
        return self.execute_command('CLUSTER FAILOVER', Token(option))

    def cluster_info(self):
        """
        Provides info about Redis Cluster node state

        Sends to random node in the cluster
        """
        return self.execute_command('CLUSTER INFO')

    def cluster_keyslot(self, name):
        """
        Returns the hash slot of the specified key

        Sends to random node in the cluster
        """
        return self.execute_command('CLUSTER KEYSLOT', name)

    def cluster_meet(self, node_id, host, port):
        """
        Force a node cluster to handshake with another node.

        Sends to specefied node
        """
        return self.execute_command('CLUSTER MEET', host, port, node_id=node_id)

    def cluster_nodes(self):
        """
        Force a node cluster to handshake with another node

        Sends to random node in the cluster
        """
        return self.execute_command('CLUSTER NODES')

    def cluster_replicate(self, target_node_id):
        """
        Reconfigure a node as a slave of the specified master node

        Sends to specefied node
        """
        return self.execute_command('CLUSTER REPLICATE', target_node_id)

    def cluster_reset(self, node_id, soft=True):
        """
        Reset a Redis Cluster node

        If 'soft' is True then it will send 'SOFT' argument
        If 'soft' is False then it will send 'HARD' argument

        Sends to specefied node
        """
        return self.execute_command('CLUSTER RESET', Token('SOFT' if soft else 'HARD'), node_id=node_id)

    def cluster_reset_all_nodes(self, soft=True):
        """
        Send CLUSTER RESET to all nodes in the cluster

        If 'soft' is True then it will send 'SOFT' argument
        If 'soft' is False then it will send 'HARD' argument

        Sends to all nodes in the cluster
        """
        return [
            self.execute_command(
                'CLUSTER RESET',
                Token('SOFT' if soft else 'HARD'),
                node_id=node['id'],
            )
            for node in self.cluster_nodes()
        ]

    def cluster_save_config(self):
        """
        Forces the node to save cluster state on disk

        Sends to all nodes in the cluster
        """
        return self.execute_command('CLUSTER SAVECONFIG')

    def cluster_set_config_epoch(self, node_id, epoch):
        """
        Set the configuration epoch in a new node

        Sends to specefied node
        """
        return self.execute_command('CLUSTER SET-CONFIG-EPOCH', epoch, node_id=node_id)

    # TODO: Determine what the purpose of bind_to_node_ip is going to be
    def cluster_setslot(self, node_id, slot_id, state, bind_to_node_id=None):
        """
        Bind an hash slot to a specific node

        Sends to specefied node
        """
        if state.upper() in ('IMPORTING', 'MIGRATING', 'NODE') and node_id is not None:
            return self.execute_command('CLUSTER SETSLOT', slot_id, Token(state), node_id)
        elif state.upper() == 'STABLE':
            return self.execute_command('CLUSTER SETSLOT', slot_id, Token('STABLE'))
        else:
            raise RedisError('Invalid slot state: {0}'.format(state))

    def cluster_slaves(self, target_node_id):
        """
        Force a node cluster to handshake with another node

        Sends to targeted cluster node
        """
        return self.execute_command('CLUSTER SLAVES', target_node_id)

    def cluster_slots(self):
        """
        Get array of Cluster slot to node mappings

        Sends to random node in the cluster
        """
        return self.execute_command('CLUSTER SLOTS')

    ##########
    # All methods that must have custom implementation

    def _parse_scan(self, response, **options):
        """
        Borrowed from redis-py::client.py
        """
        cursor, r = response
        return long(cursor), r

    def scan_iter(self, match=None, count=None):
        """
        Make an iterator using the SCAN command so that the client doesn't
        need to remember the cursor position.

        ``match`` allows for filtering the keys by pattern
        ``count`` allows for hint the minimum number of returns

        Cluster impl:
            Result from SCAN is different in cluster mode.
        """
        cursors = {}
        nodeData = {}
        for master_node in self.connection_pool.nodes.all_masters():
            cursors[master_node["name"]] = "0"
            nodeData[master_node["name"]] = master_node

        while not all(cursors[node] == 0 for node in cursors):
            for node in cursors:
                if cursors[node] == 0:
                    continue

                conn = self.connection_pool.get_connection_by_node(nodeData[node])

                pieces = ['SCAN', cursors[node]]
                if match is not None:
                    pieces.extend([Token('MATCH'), match])
                if count is not None:
                    pieces.extend([Token('COUNT'), count])

                conn.send_command(*pieces)

                raw_resp = conn.read_response()

                # if you don't release the connection, the driver will make another, and you will hate your life
                self.connection_pool.release(conn)
                cur, resp = self._parse_scan(raw_resp)
                cursors[node] = cur

                for r in resp:
                    yield r

    def mget(self, keys, *args):
        """
        Returns a list of values ordered identically to ``keys``

        Cluster impl:
            Itterate all keys and send GET for each key.
            This will go alot slower than a normal mget call in StrictRedis.

            Operation is no longer atomic.
        """
        return [self.get(arg) for arg in list_or_args(keys, args)]

    def mset(self, *args, **kwargs):
        """
        Sets key/values based on a mapping. Mapping can be supplied as a single
        dictionary argument or as kwargs.

        Cluster impl:
            Itterate over all items and do SET on each (k,v) pair

            Operation is no longer atomic.
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

        Clutser impl:
            Itterate over all items and do GET to determine if all keys do not exists.
            If true then call mset() on all keys.
        """
        if args:
            if len(args) != 1 or not isinstance(args[0], dict):
                raise RedisError('MSETNX requires **kwargs or a single dict arg')
            kwargs.update(args[0])

        # Itterate over all items and fail fast if one value is True.
        for k, _ in kwargs.items():
            if self.get(k):
                return False

        return self.mset(**kwargs)

    def rename(self, src, dst):
        """
        Rename key ``src`` to ``dst``

        Cluster impl:
            This operation is no longer atomic because each key must be querried
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

        Cluster impl:
            Iterate all keys and send DELETE for each key.
            This will go a lot slower than a normal delete call in StrictRedis.

            Operation is no longer atomic.
        """
        count = 0

        for arg in names:
            count += self.execute_command('DEL', arg)

        return count

    def renamenx(self, src, dst):
        """
        Rename key ``src`` to ``dst`` if ``dst`` doesn't already exist

        Cluster impl:
            Check if dst key do not exists, then calls rename().

            Operation is no longer atomic.
        """
        if not self.exists(dst):
            return self.rename(src, dst)

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

        Cluster impl:
            Call brpop() then send the result into lpush()

            Operation is no longer atomic.
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

        Cluster impl:
            Call rpop() then send the result into lpush()

            Operation is no longer atomic.
        """
        value = self.rpop(src)

        if value:
            self.lpush(dst, value)
            return value

        return None

    def sort(self, name, start=None, num=None, by=None, get=None, desc=False, alpha=False, store=None, groups=None):
        """Sort and return the list, set or sorted set at ``name``.

        :start: and :num:
            allow for paging through the sorted data

        :by:
            allows using an external key to weight and sort the items.
            Use an "*" to indicate where in the key the item value is located

        :get:
            allows for returning items from external keys rather than the
            sorted data itself.  Use an "*" to indicate where int he key
            the item value is located

        :desc:
            allows for reversing the sort

        :alpha:
            allows for sorting lexicographically rather than numerically

        :store:
            allows for storing the result of the sort into the key `store`

        ClusterImpl:
            A full implementation of the server side sort mechanics because many of the
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
                raise RedisClusterException("Unable to sort data type : {0}".format(data_type))
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
                    raise RedisClusterException("Unable to store sorted data for data type : {0}".format(data_type))

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

        Cluster impl:
            Querry all keys and diff all sets and return result
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

        Cluster impl:
            Use sdiff() --> Delete dest key --> store result in dest key
        """
        res = self.sdiff(keys, *args)
        self.delete(dest)

        if not res:
            return 0
        return self.sadd(dest, *res)

    def sinter(self, keys, *args):
        """
        Return the intersection of sets specified by ``keys``

        Cluster impl:
            Querry all keys, intersection and return result
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

        Cluster impl:
            Use sinter() --> Delete dest key --> store result in dest key
        """
        res = self.sinter(keys, *args)
        self.delete(dest)

        if res:
            self.sadd(dest, *res)
            return len(res)
        else:
            return 0

    def smove(self, src, dst, value):
        """
        Move ``value`` from set ``src`` to set ``dst`` atomically

        Cluster impl:
            SMEMBERS --> SREM --> SADD. Function is no longer atomic.
        """
        res = self.srem(src, value)

        # Only add the element if existed in src set
        if res == 1:
            self.sadd(dst, value)

        return res

    def sunion(self, keys, *args):
        """
        Return the union of sets specified by ``keys``

        Cluster impl:
            Querry all keys, union and return result

            Operation is no longer atomic.
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

        Cluster impl:
            Use sunion() --> Dlete dest key --> store result in dest key

            Operation is no longer atomic.
        """
        res = self.sunion(keys, *args)
        self.delete(dest)

        return self.sadd(dest, *res)

    def pfcount(self, *sources):
        """
        pfcount only works when all sources point to the same hash slot.
        """
        return super(self.__class__, self).pfcount(*sources)

    def pfmerge(self, dest, *sources):
        """
        Merge N different HyperLogLogs into a single one.

        Cluster impl:
            Very special implementation is required to make pfmerge() work
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
        random_id = "{{0}}{1}".format(hashslot, self._random_id())
        return random_id

    def _random_id(self, size=16, chars=string.ascii_uppercase + string.digits):
        """
        Generates a random id based on `size` and `chars` variable.

        By default it will generate a 16 character long string based on
        ascii uppercase letters and digits.
        """
        return ''.join(random.choice(chars) for _ in range(size))


class RedisCluster(StrictRedisCluster):
    """
    Provides backwards compatibility with older versions of redis-py that
    changed arguments to some commands to be more Pythonic, sane, or by
    accident.
    """
    # Overridden callbacks
    RESPONSE_CALLBACKS = dict_merge(
        StrictRedis.RESPONSE_CALLBACKS,
        {
            'TTL': lambda r: r >= 0 and r or None,
            'PTTL': lambda r: r >= 0 and r or None,
        }
    )

    def pipeline(self, transaction=True, shard_hint=None):
        """
        Return a new pipeline object that can queue multiple commands for
        later execution. ``transaction`` indicates whether all commands
        should be executed atomically. Apart from making a group of operations
        atomic, pipelines are useful for reducing the back-and-forth overhead
        between the client and server.
        """
        if shard_hint:
            raise RedisClusterException("shard_hint is deprecated in cluster mode")

        if transaction:
            raise RedisClusterException("transaction is deprecated in cluster mode")

        return StrictClusterPipeline(
            connection_pool=self.connection_pool,
            startup_nodes=self.connection_pool.nodes.startup_nodes,
            response_callbacks=self.response_callbacks
        )

    def setex(self, name, value, time):
        """
        Set the value of key ``name`` to ``value`` that expires in ``time``
        seconds. ``time`` can be represented by an integer or a Python
        timedelta object.
        """
        if isinstance(time, datetime.timedelta):
            time = time.seconds + time.days * 24 * 3600

        return self.execute_command('SETEX', name, time, value)

    def lrem(self, name, value, num=0):
        """
        Remove the first ``num`` occurrences of elements equal to ``value``
        from the list stored at ``name``.
        The ``num`` argument influences the operation in the following ways:
            num > 0: Remove elements equal to value moving from head to tail.
            num < 0: Remove elements equal to value moving from tail to head.
            num = 0: Remove all elements equal to value.
        """
        return self.execute_command('LREM', name, num, value)

    def zadd(self, name, *args, **kwargs):
        """
        NOTE: The order of arguments differs from that of the official ZADD
        command. For backwards compatability, this method accepts arguments
        in the form of name1, score1, name2, score2, while the official Redis
        documents expects score1, name1, score2, name2.
        If you're looking to use the standard syntax, consider using the
        StrictRedis class. See the API Reference section of the docs for more
        information.
        Set any number of element-name, score pairs to the key ``name``. Pairs
        can be specified in two ways:
        As *args, in the form of: name1, score1, name2, score2, ...
        or as **kwargs, in the form of: name1=score1, name2=score2, ...
        The following example would add four values to the 'my-key' key:
        redis.zadd('my-key', 'name1', 1.1, 'name2', 2.2, name3=3.3, name4=4.4)
        """
        pieces = []

        if args:
            if len(args) % 2 != 0:
                raise RedisError("ZADD requires an equal number of values and scores")
            pieces.extend(reversed(args))

        for pair in iteritems(kwargs):
            pieces.append(pair[1])
            pieces.append(pair[0])

        return self.execute_command('ZADD', name, *pieces)


from rediscluster.pipeline import StrictClusterPipeline

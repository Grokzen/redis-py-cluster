# -*- coding: utf-8 -*-
from __future__ import unicode_literals

# python std lib
import json
import logging
import random
import string
import time

# rediscluster imports
from .connection import (
    ClusterConnection,
    ClusterConnectionPool,
    ClusterReadOnlyConnectionPool,
    ClusterWithReadReplicasConnectionPool,
    SSLClusterConnection,
)
from .exceptions import (
    AskError,
    ClusterDownError,
    ClusterError,
    MovedError,
    RedisClusterException,
    SlotNotCoveredError,
    TryAgainError,
)
from .pubsub import ClusterPubSub
from .utils import (
    blocked_command,
    bool_ok,
    dict_merge,
    first_key,
    merge_result,
    parse_cluster_nodes,
    parse_cluster_slots,
    parse_pubsub_channels,
    parse_pubsub_numpat,
    parse_pubsub_numsub,
    string_keys_to_dict,
)

# 3rd party imports
from redis import Redis
from redis.client import list_or_args, parse_info
from redis.connection import Connection, SSLConnection
from redis._compat import iteritems, nativestr, long
from redis.exceptions import (
    BusyLoadingError,
    ConnectionError,
    RedisError,
    ResponseError,
    TimeoutError,
)


log = logging.getLogger(__name__)


class CaseInsensitiveDict(dict):
    "Case insensitive dict implementation. Assumes string keys only."

    def __init__(self, data):
        for k, v in iteritems(data):
            self[k.upper()] = v

    def __contains__(self, k):
        return super(CaseInsensitiveDict, self).__contains__(k.upper())

    def __delitem__(self, k):
        super(CaseInsensitiveDict, self).__delitem__(k.upper())

    def __getitem__(self, k):
        return super(CaseInsensitiveDict, self).__getitem__(k.upper())

    def get(self, k, default=None):
        return super(CaseInsensitiveDict, self).get(k.upper(), default)

    def __setitem__(self, k, v):
        super(CaseInsensitiveDict, self).__setitem__(k.upper(), v)

    def update(self, data):
        data = CaseInsensitiveDict(data)
        super(CaseInsensitiveDict, self).update(data)


class RedisCluster(Redis):
    """
    If a command is implemented over the one in Redis then it requires some changes compared to
    the regular implementation of the method.
    """
    RedisClusterRequestTTL = 16

    NODES_FLAGS = dict_merge(
        string_keys_to_dict([
            'ACL CAT',
            'ACL DELUSER',
            'ACL GENPASS',
            'ACL GETUSER',
            'ACL HELP',
            'ACL LIST',
            'ACL LOAD',
            'ACL LOG',
            'ACL SAVE',
            'ACL SETUSER',
            'ACL USERS',
            'ACL WHOAMI',
            'BITOP',
            'MOVE',
            'SCRIPT KILL',
            'SENTINEL GET-MASTER-ADDR-BY-NAME',
            'SENTINEL MASTER',
            'SENTINEL MASTERS',
            'SENTINEL MONITOR',
            'SENTINEL REMOVE',
            'SENTINEL SENTINELS',
            'SENTINEL SET',
            'SENTINEL SLAVES',
            'SHUTDOWN',
            'SLAVEOF',
            'WAIT',
        ], 'blocked'),
        string_keys_to_dict([
            "BGREWRITEAOF",
            "BGSAVE",
            "CLIENT GETNAME",
            "CLIENT ID",
            "CLIENT KILL",
            "CLIENT LIST",
            "CLIENT SETNAME",
            "CLUSTER INFO",
            "CONFIG GET",
            "CONFIG RESETSTAT",
            "CONFIG REWRITE",
            "CONFIG SET",
            "DBSIZE",
            "ECHO",
            "INFO",
            "KEYS",
            "LASTSAVE",
            "PING",
            "PUBSUB CHANNELS",
            "PUBSUB NUMPAT",
            "PUBSUB NUMSUB",
            "SAVE",
            "SLOWLOG GET",
            "SLOWLOG LEN",
            "SLOWLOG RESET",
            "TIME",
        ], 'all-nodes'),
        string_keys_to_dict([
            "FLUSHALL",
            "FLUSHDB",
            "SCAN",
            "SCRIPT EXISTS",
            "SCRIPT FLUSH",
            "SCRIPT LOAD",
            "SCRIPT DEBUG",
        ], 'all-masters'),
        string_keys_to_dict([
            "CLUSTER NODES",
            "CLUSTER SLOTS",
            "RANDOMKEY",
        ], 'random'),
        string_keys_to_dict([
            "CLUSTER COUNTKEYSINSLOT",
            "CLUSTER GETKEYSINSLOT",
        ], 'slot-id'),
    )

    # Not complete, but covers the major ones
    # https://redis.io/commands
    READ_COMMANDS = [
        "BITCOUNT",
        "BITPOS",
        "EXISTS",
        "GEODIST",
        "GEOHASH",
        "GEOPOS",
        "GEORADIUS",
        "GEORADIUSBYMEMBER",
        "GET",
        "GETBIT",
        "GETRANGE",
        "HEXISTS",
        "HGET",
        "HGETALL",
        "HKEYS",
        "HLEN",
        "HMGET",
        "HSTRLEN",
        "HVALS",
        "KEYS",
        "LINDEX",
        "LLEN",
        "LRANGE",
        "MGET",
        "PTTL",
        "RANDOMKEY",
        "SCARD",
        "SDIFF",
        "SINTER",
        "SISMEMBER",
        "SMEMBERS",
        "SRANDMEMBER",
        "STRLEN",
        "SUNION",
        "TTL",
        "ZCARD",
        "ZCOUNT",
        "ZRANGE",
        "ZSCORE",
    ]

    RESULT_CALLBACKS = dict_merge(
        string_keys_to_dict([
            "BGREWRITEAOF",
            "BGSAVE",
            "CLIENT GETNAME",
            "CLIENT ID",
            "CLIENT KILL",
            "CLIENT LIST",
            "CLIENT SETNAME",
            "CLUSTER INFO",
            "CONFIG GET",
            "CONFIG RESETSTAT",
            "CONFIG REWRITE",
            "CONFIG SET",
            "DBSIZE",
            "ECHO",
            "FLUSHALL",
            "FLUSHDB",
            "INFO",
            "LASTSAVE",
            "PING",
            "SAVE",
            "SCAN",
            "SLOWLOG GET",
            "SLOWLOG LEN",
            "SLOWLOG RESET",
            "TIME",
            'CLUSTER ADDSLOTS',
            'CLUSTER COUNT-FAILURE-REPORTS',
            'CLUSTER DELSLOTS',
            'CLUSTER FAILOVER',
            'CLUSTER FORGET',
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
            "HSCAN",
            "RANDOMKEY",
            "SSCAN",
            "ZSCAN",
        ], first_key),
        string_keys_to_dict([
            "PUBSUB CHANNELS",
        ], parse_pubsub_channels),
        string_keys_to_dict([
            "PUBSUB NUMSUB",
        ], parse_pubsub_numsub),
        string_keys_to_dict([
            "PUBSUB NUMPAT",
        ], parse_pubsub_numpat),
    )

    CLUSTER_COMMANDS_RESPONSE_CALLBACKS = {
        'CLUSTER ADDSLOTS': bool_ok,
        'CLUSTER COUNT-FAILURE-REPORTS': int,
        'CLUSTER COUNTKEYSINSLOT': int,
        'CLUSTER DELSLOTS': bool_ok,
        'CLUSTER FAILOVER': bool_ok,
        'CLUSTER FORGET': bool_ok,
        'CLUSTER GETKEYSINSLOT': list,
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

    def __init__(self, host=None, port=None, startup_nodes=None, max_connections=None, max_connections_per_node=False, init_slot_cache=True,
                 readonly_mode=False, reinitialize_steps=None, skip_full_coverage_check=False, nodemanager_follow_cluster=False,
                 connection_class=None, read_from_replicas=False, cluster_down_retry_attempts=3, host_port_remap=None, **kwargs):
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
        :skip_full_coverage_check:
            Skips the check of cluster-require-full-coverage config, useful for clusters
            without the CONFIG command (like aws)
        :nodemanager_follow_cluster:
            The node manager will during initialization try the last set of nodes that
            it was operating on. This will allow the client to drift along side the cluster
            if the cluster nodes move around alot.
        :**kwargs:
            Extra arguments that will be sent into Redis instance when created
            (See Official redis-py doc for supported kwargs
            [https://github.com/andymccurdy/redis-py/blob/master/redis/client.py])
            Some kwargs is not supported and will raise RedisClusterException
            - db (Redis do not support database SELECT in cluster mode)
        """
        # Tweaks to Redis client arguments when running in cluster mode
        log.info("Created new instance of RedisCluster client instance")
        log.debug("startup_nodes : " + json.dumps(startup_nodes, indent=2))

        if "db" in kwargs:
            raise RedisClusterException("Argument 'db' is not possible to use in cluster mode")

        # Needs to be removed to avoid exception in redis Connection init
        if kwargs.pop('ssl', False):
            log.info("Patching connection_class to SSLClusterConnection")
            connection_class = SSLClusterConnection

        if "connection_pool" in kwargs:
            log.info("Using custom created connection pool")
            pool = kwargs.pop('connection_pool')
        else:
            startup_nodes = [] if startup_nodes is None else startup_nodes

            # Support host/port as argument
            if host:
                startup_nodes.append({"host": host, "port": port if port else 7000})

            if readonly_mode:
                connection_pool_cls = ClusterReadOnlyConnectionPool
                log.info("Using ClusterReadOnlyConnectionPool")
            elif read_from_replicas:
                connection_pool_cls = ClusterWithReadReplicasConnectionPool
                log.info("Using ClusterWithReadReplicasConnectionPool")
            else:
                connection_pool_cls = ClusterConnectionPool
                log.info("Using ClusterConnectionPool")

            log.debug("Connection pool class " + str(connection_pool_cls))

            # If connection pool fails to initialize, parent class (Redis) __del__
            # will try to access self.connection before it's defined
            # throwing an AttributeError.
            self.connection = None

            pool = connection_pool_cls(
                startup_nodes=startup_nodes,
                init_slot_cache=init_slot_cache,
                max_connections=max_connections,
                reinitialize_steps=reinitialize_steps,
                max_connections_per_node=max_connections_per_node,
                skip_full_coverage_check=skip_full_coverage_check,
                nodemanager_follow_cluster=nodemanager_follow_cluster,
                connection_class=connection_class,
                host_port_remap=host_port_remap,
                **kwargs
            )

        super(RedisCluster, self).__init__(connection_pool=pool, **kwargs)

        self.refresh_table_asap = False
        self.nodes_flags = self.__class__.NODES_FLAGS.copy()
        self.result_callbacks = self.__class__.RESULT_CALLBACKS.copy()
        self.response_callbacks = CaseInsensitiveDict(self.__class__.RESPONSE_CALLBACKS)
        self.response_callbacks = CaseInsensitiveDict(dict_merge(self.response_callbacks, self.CLUSTER_COMMANDS_RESPONSE_CALLBACKS))
        self.read_from_replicas = read_from_replicas
        self.cluster_down_retry_attempts = cluster_down_retry_attempts

    @classmethod
    def from_url(cls, url, db=None, skip_full_coverage_check=False, readonly_mode=False, read_from_replicas=False, **kwargs):
        """
        Return a Redis client object configured from the given URL, which must
        use either `the ``redis://`` scheme
        <http://www.iana.org/assignments/uri-schemes/prov/redis>`_ for RESP
        connections or the ``unix://`` scheme for Unix domain sockets.
        For example::
            redis://[:password]@localhost:6379/0
            unix://[:password]@/path/to/socket.sock?db=0
        There are several ways to specify a database number. The parse function
        will return the first specified option:
            1. A ``db`` querystring option, e.g. redis://localhost?db=0
            2. If using the redis:// scheme, the path argument of the url, e.g.
               redis://localhost/0
            3. The ``db`` argument to this function.
        If none of these options are specified, db=0 is used.
        Any additional querystring arguments and keyword arguments will be
        passed along to the ConnectionPool class's initializer. In the case
        of conflicting arguments, querystring arguments always win.
        """
        if url.lower().startswith('unix://'):
            raise RedisClusterException('Unix sockets do not work in a cluster environment')

        if readonly_mode:
            connection_pool_cls = ClusterReadOnlyConnectionPool
        elif read_from_replicas:
            connection_pool_cls = ClusterWithReadReplicasConnectionPool
        else:
            connection_pool_cls = ClusterConnectionPool

        connection_pool = connection_pool_cls.from_url(url, db=db, skip_full_coverage_check=skip_full_coverage_check, **kwargs)

        if connection_pool.connection_class == SSLConnection:
            connection_pool.connection_class = SSLClusterConnection

        if connection_pool.connection_class == Connection:
            connection_pool.connection_class = ClusterConnection

        return cls(connection_pool=connection_pool, skip_full_coverage_check=skip_full_coverage_check)

    def __repr__(self):
        """
        """
        servers = list({'{0}:{1}'.format(nativestr(info['host']), info['port']) for info in self.connection_pool.nodes.startup_nodes})
        servers.sort()
        return "{0}<{1}>".format(type(self).__name__, ', '.join(servers))

    def set_result_callback(self, command, callback):
        "Set a custom Result Callback"
        self.result_callbacks[command] = callback

    def pubsub(self, **kwargs):
        """
        """
        return ClusterPubSub(self.connection_pool, **kwargs)

    def pipeline(self, transaction=None, shard_hint=None, read_from_replicas=False):
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

        return ClusterPipeline(
            connection_pool=self.connection_pool,
            startup_nodes=self.connection_pool.nodes.startup_nodes,
            result_callbacks=self.result_callbacks,
            response_callbacks=self.response_callbacks,
            cluster_down_retry_attempts=self.cluster_down_retry_attempts,
            read_from_replicas=read_from_replicas,
        )

    def transaction(self, *args, **kwargs):
        """
        Transaction is not implemented in cluster mode yet.
        """
        raise RedisClusterException("method RedisCluster.transaction() is not implemented")

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

        if command in ['XREADGROUP', 'XREAD']:
            stream_idx = args.index(b'STREAMS')
            keys_ids = list(args[stream_idx + 1:])
            idx_split = len(keys_ids) // 2
            keys = keys_ids[: idx_split]
            slots = {self.connection_pool.nodes.keyslot(key) for key in keys}
            if len(slots) != 1:
                raise RedisClusterException("{0} - all keys must map to the same key slot".format(command))
            return slots.pop()

        key = args[1]

        # OBJECT command uses a special keyword as first positional argument
        if command == 'OBJECT':
            key = args[2]

        return self.connection_pool.nodes.keyslot(key)

    def _merge_result(self, command, res, **kwargs):
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

    def execute_command(self, *args, **kwargs):
        """
        Wrapper for CLUSTERDOWN error handling.

        If the cluster reports it is down it is assumed that:
         - connection_pool was disconnected
         - connection_pool was reseted
         - refereh_table_asap set to True

        It will try the number of times specified by the config option "self.cluster_down_retry_attempts"
        which defaults to 3 unless manually configured.

        If it reaches the number of times, the command will raises ClusterDownException.
        """
        for _ in range(0, self.cluster_down_retry_attempts):
            try:
                return self._execute_command(*args, **kwargs)
            except ClusterDownError:
                # Try again with the new cluster setup. All other errors
                # should be raised.
                pass

        # If it fails the configured number of times then raise exception back to caller of this method
        raise ClusterDownError("CLUSTERDOWN error. Unable to rebuild the cluster")

    def _execute_command(self, *args, **kwargs):
        """
        Send a command to a node in the cluster
        """
        if not args:
            raise RedisClusterException("Unable to determine command to use")

        command = args[0]
        log.debug("Command to execute : " + str(command) + " : " + str(args) + " : " + str(kwargs))

        # If set externally we must update it before calling any commands
        if self.refresh_table_asap:
            self.connection_pool.nodes.initialize()
            self.refresh_table_asap = False

        node = self.determine_node(*args, **kwargs)
        if node:
            return self._execute_command_on_nodes(node, *args, **kwargs)

        redirect_addr = None
        asking = False
        is_read_replica = False

        try_random_node = False
        slot = self._determine_slot(*args)
        ttl = int(self.RedisClusterRequestTTL)
        connection_error_retry_counter = 0

        while ttl > 0:
            ttl -= 1
            connection = None

            try:
                if asking:
                    node = self.connection_pool.nodes.nodes[redirect_addr]
                    connection = self.connection_pool.get_connection_by_node(node)
                elif try_random_node:
                    connection = self.connection_pool.get_random_connection()
                    try_random_node = False
                else:
                    if self.refresh_table_asap:
                        # MOVED
                        node = self.connection_pool.get_master_node_by_slot(slot)
                        self.refresh_table_asap = False
                    else:
                        node = self.connection_pool.get_node_by_slot(
                            slot,
                            self.read_from_replicas and (command in self.READ_COMMANDS)
                        )
                        is_read_replica = node['server_type'] == 'slave'

                    connection = self.connection_pool.get_connection_by_node(node)

                log.debug("Determined node to execute : " + str(node))

                if asking:
                    connection.send_command('ASKING')
                    self.parse_response(connection, "ASKING", **kwargs)
                    asking = False
                if is_read_replica:
                    # Ask read replica to accept reads (see https://redis.io/commands/readonly)
                    # TODO: do we need to handle errors from this response?
                    connection.send_command('READONLY')
                    self.parse_response(connection, 'READONLY', **kwargs)
                    is_read_replica = False

                connection.send_command(*args)
                return self.parse_response(connection, command, **kwargs)
            except SlotNotCoveredError as e:
                log.exception("SlotNotCoveredError")

                # In some cases during failover to a replica is happening
                # a slot sometimes is not covered by the cluster layout and
                # we need to attempt to refresh the cluster layout and try again
                self.refresh_table_asap = True
                time.sleep(0.1)

                # This is the last attempt before we run out of TTL, raise the exception
                if ttl == 1:
                    raise e
            except (RedisClusterException, BusyLoadingError):
                log.exception("RedisClusterException || BusyLoadingError")
                raise
            except ConnectionError:
                log.exception("ConnectionError")

                connection.disconnect()
                connection_error_retry_counter += 1

                # Give the node 0.1 seconds to get back up and retry again with same
                # node and configuration. After 5 attempts then try to reinitialize
                # the cluster and see if the nodes configuration has changed or not
                if connection_error_retry_counter < 5:
                    time.sleep(0.25)
                else:
                    # Reset the counter back to 0 as it should have 5 new attempts
                    # after the client tries to reinitailize the cluster setup to the
                    # new configuration.
                    connection_error_retry_counter = 0
                    self.refresh_table_asap = True

                    # Hard force of reinitialize of the node/slots setup
                    self.connection_pool.nodes.increment_reinitialize_counter(
                        count=self.connection_pool.nodes.reinitialize_steps,
                    )
            except TimeoutError:
                log.exception("TimeoutError")
                connection.disconnect()

                if ttl < self.RedisClusterRequestTTL / 2:
                    time.sleep(0.05)
                else:
                    try_random_node = True
            except ClusterDownError as e:
                log.exception("ClusterDownError")

                self.connection_pool.disconnect()
                self.connection_pool.reset()
                self.refresh_table_asap = True
                connection = None

                raise e
            except MovedError as e:
                # Reinitialize on ever x number of MovedError.
                # This counter will increase faster when the same client object
                # is shared between multiple threads. To reduce the frequency you
                # can set the variable 'reinitialize_steps' in the constructor.
                log.exception("MovedError")

                self.refresh_table_asap = True
                self.connection_pool.nodes.increment_reinitialize_counter()

                node = self.connection_pool.nodes.set_node(e.host, e.port, server_type='master')
                self.connection_pool.nodes.slots[e.slot_id][0] = node
            except TryAgainError:
                log.exception("TryAgainError")

                if ttl < self.RedisClusterRequestTTL / 2:
                    time.sleep(0.05)
            except AskError as e:
                log.exception("AskError")

                redirect_addr, asking = "{0}:{1}".format(e.host, e.port), True
            except BaseException as e:
                log.exception("BaseException")
                connection.disconnect()
                raise e
            finally:
                if connection is not None:
                    self.connection_pool.release(connection)

            log.debug("TTL loop : " + str(ttl))

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
            except ClusterDownError:
                self.connection_pool.disconnect()
                self.connection_pool.reset()
                self.refresh_table_asap = True

                raise
            finally:
                self.connection_pool.release(connection)

        return self._merge_result(command, res, **kwargs)

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

    def cluster_failover(self, node_id, option=None):
        """
        Forces a slave to perform a manual failover of its master

        Sends to specefied node
        """
        if option:
            if option.upper() not in ['FORCE', 'TAKEOVER']:
                raise RedisError('Invalid option for CLUSTER FAILOVER command: {0}'.format(option))
            else:
                return self.execute_command('CLUSTER FAILOVER', option, node_id=node_id)
        else:
            return self.execute_command('CLUSTER FAILOVER', node_id=node_id)

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
        return self.execute_command('CLUSTER RESET', b'SOFT' if soft else b'HARD', node_id=node_id)

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
                'SOFT' if soft else 'HARD',
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

    def cluster_get_keys_in_slot(self, slot, num_keys):
        """
        Returns the number of keys in the specefied cluster slot
        """
        return self.execute_command('CLUSTER GETKEYSINSLOT', slot, num_keys)

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
            return self.execute_command('CLUSTER SETSLOT', slot_id, state, node_id)
        elif state.upper() == 'STABLE':
            return self.execute_command('CLUSTER SETSLOT', slot_id, 'STABLE')
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

    def client_kill_filter(self, _id=None, _type=None, addr=None, skipme=None):
        raise NotImplementedError('Method not yet implemented')

    def _parse_scan(self, response, **options):
        """
        Borrowed from redis-py::client.py
        """
        cursor, r = response
        return long(cursor), r

    def scan_iter(self, match=None, count=None, _type=None):
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
                    pieces.extend([b'MATCH', match])
                if count is not None:
                    pieces.extend([b'COUNT', count])
                if _type is not None:
                    pieces.extend([b'TYPE', _type])

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
            This will go alot slower than a normal mget call in Redis.

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

    def rename(self, src, dst, replace=False):
        """
        Rename key ``src`` to ``dst``

        Cluster impl:
            If the src and dsst keys is in the same slot then send a plain RENAME
            command to that node to do the rename inside the server.

            If the keys is in crossslots then use the client side implementation
            as fallback method. In this case this operation is no longer atomic as
            the key is dumped and posted back to the server through the client.
        """
        if src == dst:
            raise ResponseError("source and destination objects are the same")

        #
        # Optimization where if both keys is in the same slot then we can use the
        # plain upstream rename method.
        #
        src_slot = self.connection_pool.nodes.keyslot(src)
        dst_slot = self.connection_pool.nodes.keyslot(dst)

        if src_slot == dst_slot:
            return self.execute_command('RENAME', src, dst)

        #
        # To provide cross slot support we implement rename by doing the internal command
        # redis server runs but in the client instead.
        #
        data = self.dump(src)

        if data is None:
            raise ResponseError("no such key")

        ttl = self.pttl(src)

        if ttl is None or ttl < 1:
            ttl = 0

        self.delete(dst)
        self.restore(dst, ttl, data, replace)
        self.delete(src)

        return True

    def delete(self, *names):
        """
        "Delete one or more keys specified by ``names``"

        Cluster impl:
            Iterate all keys and send DELETE for each key.
            This will go a lot slower than a normal delete call in Redis.

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

    def pubsub_channels(self, pattern='*', aggregate=True):
        """
        Return a list of channels that have at least one subscriber.
        Aggregate toggles merging of response.
        """
        return self.execute_command('PUBSUB CHANNELS', pattern, aggregate=aggregate)

    def pubsub_numpat(self, aggregate=True):
        """
        Returns the number of subscriptions to patterns.
        Aggregate toggles merging of response.
        """
        return self.execute_command('PUBSUB NUMPAT', aggregate=aggregate)

    def pubsub_numsub(self, *args, **kwargs):
        """
        Return a list of (channel, number of subscribers) tuples
        for each channel given in ``*args``.

        ``aggregate`` keyword argument toggles merging of response.
        """
        options = {'aggregate': kwargs.get('aggregate', True)}
        return self.execute_command('PUBSUB NUMSUB', *args, **options)

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


from rediscluster.pipeline import ClusterPipeline

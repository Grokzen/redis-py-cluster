# -*- coding: utf-8 -*-

# python std lib
import os
import random
import threading
from contextlib import contextmanager
from itertools import chain
import random

# rediscluster imports
from .nodemanager import NodeManager
from .exceptions import (
    RedisClusterException, AskError, MovedError,
    TryAgainError, ClusterDownError, ClusterCrossSlotError,
    MasterDownError,
)

# 3rd party imports
from redis._compat import nativestr
from redis.client import dict_merge
from redis.connection import ConnectionPool, Connection, DefaultParser, SSLConnection
from redis.exceptions import ConnectionError


class ClusterParser(DefaultParser):
    """
    """
    EXCEPTION_CLASSES = dict_merge(
        DefaultParser.EXCEPTION_CLASSES, {
            'ASK': AskError,
            'TRYAGAIN': TryAgainError,
            'MOVED': MovedError,
            'CLUSTERDOWN': ClusterDownError,
            'CROSSSLOT': ClusterCrossSlotError,
            'MASTERDOWN': MasterDownError,
        })


class ClusterConnection(Connection):
    "Manages TCP communication to and from a Redis server"
    description_format = "ClusterConnection<host=%(host)s,port=%(port)s>"

    def __init__(self, *args, **kwargs):
        self.readonly = kwargs.pop('readonly', False)
        kwargs['parser_class'] = ClusterParser
        super(ClusterConnection, self).__init__(*args, **kwargs)

    def on_connect(self):
        '''
        Initialize the connection, authenticate and select a database and send READONLY if it is
        set during object initialization.
        '''
        super(ClusterConnection, self).on_connect()

        if self.readonly:
            self.send_command('READONLY')

            if nativestr(self.read_response()) != 'OK':
                raise ConnectionError('READONLY command failed')


class SSLClusterConnection(SSLConnection):
    """
    Manages TCP communication over TLS/SSL to and from a Redis cluster
    Usage:
        pool = ClusterConnectionPool(connection_class=SSLClusterConnection, ...)
        client = StrictRedisCluster(connection_pool=pool)
    """
    description_format = "SSLClusterConnection<host=%(host)s,port=%(port)s,db=%(db)s>"

    def __init__(self, **kwargs):
        self.readonly = kwargs.pop('readonly', False)
        kwargs['parser_class'] = ClusterParser
        kwargs.pop('ssl', None)  # Needs to be removed to avoid exception in redis Connection init
        super(SSLClusterConnection, self).__init__(**kwargs)

    def on_connect(self):
        '''
        Initialize the connection, authenticate and select a database and send READONLY if it is
        set during object initialization.
        '''
        super(SSLClusterConnection, self).on_connect()

        if self.readonly:
            self.send_command('READONLY')

            if nativestr(self.read_response()) != 'OK':
                raise ConnectionError('READONLY command failed')


class UnixDomainSocketConnection(Connection):
    """
    """
    description_format = "ClusterUnixDomainSocketConnection<path=%(path)s>"


class ClusterConnectionPool(ConnectionPool):
    """
    Custom connection pool for rediscluster
    """
    RedisClusterDefaultTimeout = None

    def __init__(self, startup_nodes=None, init_slot_cache=True, connection_class=None,
                 max_connections=None, max_connections_per_node=False, reinitialize_steps=None,
                 skip_full_coverage_check=False, nodemanager_follow_cluster=False, **connection_kwargs):
        """
        :skip_full_coverage_check:
            Skips the check of cluster-require-full-coverage config, useful for clusters
            without the CONFIG command (like aws)
        :nodemanager_follow_cluster:
            The node manager will during initialization try the last set of nodes that
            it was operating on. This will allow the client to drift along side the cluster
            if the cluster nodes move around alot.
        """
        if connection_class is None:
            connection_class = ClusterConnection
        super(ClusterConnectionPool, self).__init__(connection_class=connection_class, max_connections=max_connections)

        # Special case to make from_url method compliant with cluster setting.
        # from_url method will send in the ip and port through a different variable then the
        # regular startup_nodes variable.
        if startup_nodes is None:
            if 'port' in connection_kwargs and 'host' in connection_kwargs:
                startup_nodes = [{
                    'host': connection_kwargs.pop('host'),
                    'port': str(connection_kwargs.pop('port')),
                }]

        self.max_connections = max_connections or 2 ** 31
        self.max_connections_per_node = max_connections_per_node

        if connection_class == SSLClusterConnection:
            connection_kwargs['ssl'] = True  # needed in StrictRedis init

        self.nodes = NodeManager(
            startup_nodes,
            reinitialize_steps=reinitialize_steps,
            skip_full_coverage_check=skip_full_coverage_check,
            max_connections=self.max_connections,
            nodemanager_follow_cluster=nodemanager_follow_cluster,
            **connection_kwargs
        )

        if init_slot_cache:
            self.nodes.initialize()

        self.connections = {}
        self.connection_kwargs = connection_kwargs
        self.reset()

        if "socket_timeout" not in self.connection_kwargs:
            self.connection_kwargs["socket_timeout"] = ClusterConnectionPool.RedisClusterDefaultTimeout

    def __repr__(self):
        """
        Return a string with all unique ip:port combinations that this pool is connected to.
        """
        nodes = [{'host': i['host'], 'port': i['port']} for i in self.nodes.startup_nodes]

        return "{0}<{1}>".format(
            type(self).__name__,
            ", ".join([self.connection_class.description_format % dict(node, **self.connection_kwargs) for node in nodes])
        )

    def reset(self):
        """
        Resets the connection pool back to a clean state.
        """
        self.pid = os.getpid()
        self._created_connections = 0
        self._created_connections_per_node = {}  # Dict(Node, Int)
        self._available_connections = {}  # Dict(Node, List)
        self._in_use_connections = {}  # Dict(Node, Set)
        self._check_lock = threading.Lock()

    def _checkpid(self):
        """
        """
        if self.pid != os.getpid():
            with self._check_lock:
                if self.pid == os.getpid():
                    # another thread already did the work while we waited
                    # on the lockself.
                    return
                self.disconnect()
                self.reset()

    def get_connection(self, command_name, *keys, **options):
        """
        # TODO: Default method entrypoint.
        Keys, options is not in use by any of the standard code.
        """
        # Only pubsub command/connection should be allowed here
        if command_name != "pubsub":
            raise RedisClusterException("Only 'pubsub' commands can be used by get_connection()")

        channel = options.pop('channel', None)

        if not channel:
            return self.get_random_connection()

        slot = self.nodes.keyslot(channel)
        node = self.get_master_node_by_slot(slot)

        self._checkpid()

        try:
            connection = self._available_connections.get(node["name"], []).pop()
        except IndexError:
            connection = self.make_connection(node)

        if node['name'] not in self._in_use_connections:
            self._in_use_connections[node['name']] = set()

        self._in_use_connections[node['name']].add(connection)

        return connection

    def make_connection(self, node):
        """
        Create a new connection
        """
        if self.count_all_num_connections(node) >= self.max_connections:
            if self.max_connections_per_node:
                raise RedisClusterException("Too many connection ({0}) for node: {1}".format(self.count_all_num_connections(node), node['name']))

            raise RedisClusterException("Too many connections")

        self._created_connections_per_node.setdefault(node['name'], 0)
        self._created_connections_per_node[node['name']] += 1
        connection = self.connection_class(host=node["host"], port=node["port"], **self.connection_kwargs)

        # Must store node in the connection to make it eaiser to track
        connection.node = node

        return connection

    def release(self, connection):
        """
        Releases the connection back to the pool
        """
        self._checkpid()
        if connection.pid != self.pid:
            return

        # Remove the current connection from _in_use_connection and add it back to the available pool
        # There is cases where the connection is to be removed but it will not exist and there
        # must be a safe way to remove
        i_c = self._in_use_connections.get(connection.node["name"], set())

        if connection in i_c:
            i_c.remove(connection)
        else:
            pass
            # TODO: Log.warning("Tried to release connection that did not exist any longer : {0}".format(connection))

        self._available_connections.setdefault(connection.node["name"], []).append(connection)

    def disconnect(self):
        """
        Nothing that requires any overwrite.
        """
        all_conns = chain(
            self._available_connections.values(),
            self._in_use_connections.values(),
        )

        for node_connections in all_conns:
            for connection in node_connections:
                connection.disconnect()

    def count_all_num_connections(self, node):
        """
        """
        if self.max_connections_per_node:
            return self._created_connections_per_node.get(node['name'], 0)

        return sum([i for i in self._created_connections_per_node.values()])

    def get_random_connection(self):
        """
        Open new connection to random redis server.
        """
        # TODO: Should this open a new random connection or shuld it look if there is any
        #       open available connections and return that instead?
        for node in self.nodes.random_startup_node_ittr():
            connection = self.get_connection_by_node(node)

            if connection:
                return connection

        raise Exception("Cant reach a single startup node.")

    def get_connection_by_key(self, key, command):
        """
        """
        if not key:
            raise RedisClusterException("No way to dispatch this command to Redis Cluster.")

        return self.get_connection_by_slot(self.nodes.keyslot(key))

    def get_connection_by_slot(self, slot):
        """
        Determine what server a specific slot belongs to and return a redis object that is connected
        """
        self._checkpid()

        try:
            return self.get_master_connection_by_slot()
        except KeyError:
            return self.get_random_connection()

    def get_connection_by_node(self, node):
        """
        get a connection by node
        """
        self._checkpid()
        self.nodes.set_node_name(node)

        try:
            # Try to get connection from existing pool
            connection = self._available_connections.get(node["name"], []).pop()
        except IndexError:
            connection = self.make_connection(node)

        self._in_use_connections.setdefault(node["name"], set()).add(connection)

        return connection

    def get_master_node_by_slot(self, slot):
        """
        """
        return self.nodes.slots[slot][0]

    def get_random_node_by_slot(self, slot):
        """
        Get a random node from the slot, including master
        """
        nodes_in_slot = self.nodes.slots[slot]
        random_index = random.randrange(0,len(nodes_in_slot))
        is_read_replica = random_index > 0
        return nodes_in_slot[random_index], is_read_replica

    def get_node_by_slot(self, slot, read_from_replicas):
        """
        """
        if read_from_replicas:
            return self.get_random_node_by_slot(slot)
        else:
            return self.get_master_node_by_slot(slot), False


class ClusterReadOnlyConnectionPool(ClusterConnectionPool):
    """
    Readonly connection pool for rediscluster
    """

    def __init__(self, startup_nodes=None, init_slot_cache=True, connection_class=None,
                 max_connections=None, nodemanager_follow_cluster=False, **connection_kwargs):
        """
        """
        if connection_class is None:
            connection_class = ClusterConnection
        super(ClusterReadOnlyConnectionPool, self).__init__(
            startup_nodes=startup_nodes,
            init_slot_cache=init_slot_cache,
            connection_class=connection_class,
            max_connections=max_connections,
            readonly=True,
            nodemanager_follow_cluster=nodemanager_follow_cluster,
            **connection_kwargs)

        self.master_node_commands = ('SCAN', 'SSCAN', 'HSCAN', 'ZSCAN')

    def get_connection_by_key(self, key, command):
        """
        """
        if not key:
            raise RedisClusterException("No way to dispatch this command to Redis Cluster.")

        if command in self.master_node_commands:
            return self.get_master_connection_by_slot(self.nodes.keyslot(key))
        else:
            return self.get_random_master_slave_connection_by_slot(self.nodes.keyslot(key))

    def get_master_connection_by_slot(self, slot):
        """
        Returns a connection for the Master node for the specefied slot.

        Do not return a random node if master node is not available for any reason.
        """
        self._checkpid()
        return self.get_connection_by_node(self.get_master_node_by_slot(slot))

    def get_random_master_slave_connection_by_slot(self, slot):
        """
        Returns a random connection from the set of (master + slaves) for the
        specefied slot. If connection is not reachable then return a random connection.
        """
        self._checkpid()

        try:
            node, is_read_replica = self.get_random_node_by_slot(slot)
            return node
        except KeyError:
            return self.get_random_connection()

    def get_node_by_slot_random(self, slot):
        """
        Return a random node for the specified slot.
        """
        return random.choice(self.nodes.slots[slot])


@contextmanager
def by_node_context(pool, node):
    """
    Get a connection from the pool and automatically release it back
    """
    connection = pool.get_connection_by_node(node)
    yield connection
    pool.release(connection)

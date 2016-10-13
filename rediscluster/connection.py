# -*- coding: utf-8 -*-

# python std lib
import os
import random
import threading
from contextlib import contextmanager
from itertools import chain

# rediscluster imports
from .nodemanager import NodeManager
from .exceptions import (
    RedisClusterException, AskError, MovedError,
    TryAgainError, ClusterDownError, ClusterCrossSlotError,
)

# 3rd party imports
from redis._compat import nativestr
from redis.client import dict_merge
from redis.connection import ConnectionPool, Connection, DefaultParser
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


class UnixDomainSocketConnection(Connection):
    """
    """
    description_format = "ClusterUnixDomainSocketConnection<path=%(path)s>"


class ClusterConnectionPool(ConnectionPool):
    """
    Custom connection pool for rediscluster
    """
    RedisClusterDefaultTimeout = None

    def __init__(self, startup_nodes=None, init_slot_cache=True, connection_class=ClusterConnection,
                 max_connections=None, max_connections_per_node=False, reinitialize_steps=None, **connection_kwargs):
        """
        """
        super(ClusterConnectionPool, self).__init__(connection_class=connection_class, max_connections=max_connections)

        self.max_connections = max_connections or 2 ** 31
        self.max_connections_per_node = max_connections_per_node

        self.nodes = NodeManager(startup_nodes, reinitialize_steps=reinitialize_steps, **connection_kwargs)
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

    def get_connection_by_key(self, key):
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
            return self.get_connection_by_node(self.get_node_by_slot(slot))
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

    def get_node_by_slot(self, slot):
        """
        """
        return self.get_master_node_by_slot(slot)


class ClusterReadOnlyConnectionPool(ClusterConnectionPool):
    """
    Readonly connection pool for rediscluster
    """

    def __init__(self, startup_nodes=None, init_slot_cache=True, connection_class=ClusterConnection,
                 max_connections=None, **connection_kwargs):
        """
        """
        super(ClusterReadOnlyConnectionPool, self).__init__(
            startup_nodes=startup_nodes,
            init_slot_cache=init_slot_cache,
            connection_class=connection_class,
            max_connections=max_connections,
            readonly=True,
            **connection_kwargs)

    def get_node_by_slot(self, slot):
        """
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

# -*- coding: utf-8 -*-

# python std lib
from __future__ import unicode_literals
import logging
import os
import random
import threading
from contextlib import contextmanager
from itertools import chain
from collections import defaultdict

# rediscluster imports
from .nodemanager import NodeManager
from .exceptions import (
    RedisClusterException, AskError, MovedError,
    TryAgainError, ClusterDownError, ClusterCrossSlotError,
    MasterDownError, SlotNotCoveredError,
)

# 3rd party imports
from redis._compat import nativestr, LifoQueue, Full, Empty
from redis.client import dict_merge
from redis.connection import ConnectionPool, Connection, DefaultParser, SSLConnection, UnixDomainSocketConnection
from redis.exceptions import ConnectionError

log = logging.getLogger(__name__)


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

    def __init__(self, *args, **kwargs):
        log.debug("Creating new ClusterConnection instance")
        log.debug(str(args) + " : " + str(kwargs))

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
            log.debug("Sending READONLY command to server to configure connection as readonly")
            log.debug(str(self))

            self.send_command('READONLY')

            if nativestr(self.read_response()) != 'OK':
                raise ConnectionError('READONLY command failed')


class SSLClusterConnection(SSLConnection):
    """
    Manages TCP communication over TLS/SSL to and from a Redis cluster
    Usage:
        pool = ClusterConnectionPool(connection_class=SSLClusterConnection, ...)
        client = RedisCluster(connection_pool=pool)
    """

    def __init__(self, *args, **kwargs):
        log.debug("Creating new SSLClusterConnection instance")
        log.debug(str(args) + " : " + str(kwargs))

        self.readonly = kwargs.pop('readonly', False)
        # need to pop this off as the redis/connection.py SSLConnection init doesn't work with ssl passed in
        if 'ssl' in kwargs:
            kwargs.pop('ssl')
        kwargs['parser_class'] = ClusterParser
        super(SSLClusterConnection, self).__init__(**kwargs)

    def on_connect(self):
        '''
        Initialize the connection, authenticate and select a database and send READONLY if it is
        set during object initialization.
        '''
        super(SSLClusterConnection, self).on_connect()

        if self.readonly:
            log.debug("Sending READONLY command to server to configure connection as readonly")

            self.send_command('READONLY')

            if nativestr(self.read_response()) != 'OK':
                raise ConnectionError('READONLY command failed')


class ClusterConnectionPool(ConnectionPool):
    """
    Custom connection pool for rediscluster
    """
    RedisClusterDefaultTimeout = None

    def __init__(self, startup_nodes=None, init_slot_cache=True, connection_class=None,
                 max_connections=None, max_connections_per_node=False, reinitialize_steps=None,
                 skip_full_coverage_check=False, nodemanager_follow_cluster=False, host_port_remap=None,
                 **connection_kwargs):
        """
        :skip_full_coverage_check:
            Skips the check of cluster-require-full-coverage config, useful for clusters
            without the CONFIG command (like aws)
        :nodemanager_follow_cluster:
            The node manager will during initialization try the last set of nodes that
            it was operating on. This will allow the client to drift along side the cluster
            if the cluster nodes move around a lot.
        """
        log.debug("Creating new ClusterConnectionPool instance")

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
            connection_kwargs['ssl'] = True  # needed in Redis init

        self.nodes = NodeManager(
            startup_nodes,
            reinitialize_steps=reinitialize_steps,
            skip_full_coverage_check=skip_full_coverage_check,
            max_connections=self.max_connections,
            nodemanager_follow_cluster=nodemanager_follow_cluster,
            host_port_remap=host_port_remap,
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
        nodes = [
            {'host': i['host'], 'port': i['port']}
            for i in self.nodes.startup_nodes
        ]

        return "{0}<{1}>".format(
            type(self).__name__,
            ", ".join([repr(self.connection_class(**self.connection_kwargs)) for node in nodes])
        )

    def reset(self):
        """
        Resets the connection pool back to a clean state.
        """
        log.debug("Resetting ConnectionPool")

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
                    # on the lock.
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

        try:
            # ensure this connection is connected to Redis
            connection.connect()
            # connections that the pool provides should be ready to send
            # a command. if not, the connection was either returned to the
            # pool before all data has been read or the socket has been
            # closed. either way, reconnect and verify everything is good.
            try:
                if connection.can_read():
                    raise ConnectionError('Connection has data')
            except ConnectionError:
                connection.disconnect()
                connection.connect()
                if connection.can_read():
                    raise ConnectionError('Connection not ready')
        except BaseException:
            # release the connection back to the pool so that we don't
            # leak it
            self.release(connection)
            raise

        return connection

    def make_connection(self, node):
        """
        Create a new connection
        """
        num_connections = self.count_all_num_connections(node)
        if num_connections >= self.max_connections:
            if self.max_connections_per_node:
                raise RedisClusterException("Too many connection ({0}) for node: {1}".format(num_connections, node['name']))

            raise RedisClusterException("Too many connections")

        self._created_connections_per_node.setdefault(node['name'], 0)
        self._created_connections_per_node[node['name']] += 1
        connection = self.connection_class(host=node["host"], port=node["port"], **self.connection_kwargs)

        # Must store node in the connection to make it easier to track
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

        return sum([i for i in list(self._created_connections_per_node.values())])

    def get_random_connection(self):
        """
        Open new connection to random redis server.
        """
        # TODO: Should this open a new random connection or should it look if there is any
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
            return self.get_connection_by_node(self.get_node_by_slot(slot))
        except (KeyError, RedisClusterException):
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
        try:
            return self.nodes.slots[slot][0]
        except KeyError:
            raise SlotNotCoveredError('Slot "{slot}" not covered by the cluster. "skip_full_coverage_check={skip_full_coverage_check}"'.format(
                slot=slot, skip_full_coverage_check=self.nodes._skip_full_coverage_check,
            ))

    def get_node_by_slot(self, slot, *args, **kwargs):
        """
        """
        return self.get_master_node_by_slot(slot)


class ClusterBlockingConnectionPool(ClusterConnectionPool):
    """
    Thread-safe blocking connection pool for Redis Cluster::

        >>> from rediscluster.client import RedisCluster
        >>> client = RedisCluster(connection_pool=ClusterBlockingConnectionPool())

    It performs the same function as the default
    ``:py:class: ~rediscluster.connection.ClusterConnectionPool`` implementation, in that,
    it maintains a pool of reusable connections to a redis cluster that can be shared by
    multiple redis clients (safely across threads if required).

    The difference is that, in the event that a client tries to get a
    connection from the pool when all of connections are in use, rather than
    raising a ``:py:class: ~rediscluster.exceptions.RedisClusterException`` (as the default
    ``:py:class: ~rediscluster.connection.ClusterConnectionPool`` implementation does), it
    makes the client wait ("blocks") for a specified number of seconds until
    a connection becomes available.

    Use ``max_connections`` to set the pool size::

        >>> pool = ClusterBlockingConnectionPool(max_connections=10)

    Use ``timeout`` to tell it either how many seconds to wait for a connection
    to become available when accessing the queue, or to block forever:

        # Block forever.
        >>> pool = ClusterBlockingConnectionPool(timeout=None)

        # Raise a ``ConnectionError`` after five seconds if a connection is
        # not available.
        >>> pool = ClusterBlockingConnectionPool(timeout=5)
    """

    def __init__(self, startup_nodes=None, init_slot_cache=True, connection_class=None,
                 max_connections=None, max_connections_per_node=False, reinitialize_steps=None,
                 skip_full_coverage_check=False, nodemanager_follow_cluster=False,
                 timeout=20, **connection_kwargs):
        self.timeout = timeout

        super(ClusterBlockingConnectionPool, self).__init__(
            startup_nodes=startup_nodes,
            init_slot_cache=init_slot_cache,
            connection_class=connection_class,
            max_connections=max_connections,
            max_connections_per_node=max_connections_per_node,
            reinitialize_steps=reinitialize_steps,
            skip_full_coverage_check=skip_full_coverage_check,
            nodemanager_follow_cluster=nodemanager_follow_cluster,
            **connection_kwargs
        )

    def _blocking_pool_factory(self):
        # Create and fill up a thread safe queue with ``None`` values.
        # We will use ``None`` to denote when to create a new connection rather than to reuse.
        pool = LifoQueue(self.max_connections)
        while True:
            try:
                pool.put_nowait(None)
            except Full:
                break
        return pool

    def _get_pool(self, node):
        return self._pool_by_node[node["name"]] \
            if self.max_connections_per_node or node is None else self._group_pool

    def reset(self):
        self.pid = os.getpid()
        self._check_lock = threading.Lock()

        """
        We could use a conditional branch on ``max_connections_per_node`` to see which pool to initialize,
        but ClusterConnectionPool calls ConnectionPool init which has no concept of ``max_connections_per_node``,
        and also performs ``reset()``. This will lead to an attribute error.

        This could suggest removing inheritance from ConnectionPool, but initializing both should not add much overhead.
        """
        self._pool_by_node = defaultdict(self._blocking_pool_factory)
        self._group_pool = self._blocking_pool_factory()

        # Keep a list of actual connection instances so that we can
        # disconnect them later.
        self._connections = []

    def make_connection(self, node):
        """ Create a new connection """
        connection = self.connection_class(host=node["host"], port=node["port"], **self.connection_kwargs)
        self._connections.append(connection)
        connection.node = node
        return connection

    def get_connection(self, command_name, *keys, **options):
        if command_name != "pubsub":
            raise RedisClusterException("Only 'pubsub' commands can be used by get_connection()")

        channel = options.pop('channel', None)

        if not channel:
            # find random startup node and try to get connection again
            return self.get_random_connection()
        return self.get_connection_by_node(
            self.get_master_node_by_slot(
                self.nodes.keyslot(channel)
            )
        )

    def get_connection_by_node(self, node):
        """
        Get a connection by node
        """
        self._checkpid()
        self.nodes.set_node_name(node)
        connection = None
        connections_to_other_nodes = []
        pool = self._get_pool(node=node)
        try:
            connection = pool.get(block=True, timeout=self.timeout)
            while connection is not None and connection.node != node:
                connections_to_other_nodes.append(connection)
                connection = pool.get(block=True, timeout=self.timeout)

        except Empty:
            # queue is full of connections to other nodes
            if len(connections_to_other_nodes) == self.max_connections:
                # is the earliest released / longest un-used connection
                connection_to_clear = connections_to_other_nodes.pop()
                self._connections.remove(connection_to_clear)
                connection_to_clear.disconnect()
                connection = None  # get a new connection
            else:
                # Note that this is not caught by the redis cluster client and will be
                # raised unless handled by application code.

                # ``ConnectionError`` is raised when timeout is hit on the queue.
                raise ConnectionError("No connection available")

        # Put all the connections belonging to other nodes back,
        # disconnecting the ones we fail to return.
        for idx, other_connection in enumerate(connections_to_other_nodes):
            try:
                pool.put_nowait(other_connection)
            except Full:
                for lost_connection in connections_to_other_nodes[idx:]:
                    self._connections.remove(lost_connection)
                    lost_connection.disconnect()
                break

        if connection is None:
            connection = self.make_connection(node)

        return connection

    def release(self, connection):
        """
        Releases the connection back to the pool
        """
        self._checkpid()
        if connection.pid != self.pid:
            return

        # Put the connection back into the pool.
        try:
            self._get_pool(connection.node).put_nowait(connection)
        except Full:
            # perhaps the pool has been reset() after a fork? regardless,
            # we don't want this connection
            pass

    def disconnect(self):
        """Disconnects all connections in the pool."""
        for connection in self._connections:
            connection.disconnect()


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
            **connection_kwargs
        )

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
        return self.get_connection_by_node(self.get_node_by_slot(slot))

    def get_random_master_slave_connection_by_slot(self, slot):
        """
        Returns a random connection from the set of (master + slaves) for the
        specefied slot. If connection is not reachable then return a random connection.
        """
        self._checkpid()

        try:
            return self.get_node_by_slot_random(self.get_node_by_slot(slot))
        except KeyError:
            return self.get_random_connection()

    def get_node_by_slot_random(self, slot):
        """
        Return a random node for the specified slot.
        """
        return random.choice(self.nodes.slots[slot])


class ClusterWithReadReplicasConnectionPool(ClusterConnectionPool):
    """
    Custom connection pool for rediscluster with load balancing across read replicas
    """

    def get_node_by_slot(self, slot, read_command=False):
        """
        Get a random node from the slot, including master
        """
        nodes_in_slot = self.nodes.slots[slot]
        if read_command:
            random_index = random.randrange(0, len(nodes_in_slot))
            return nodes_in_slot[random_index]
        else:
            return nodes_in_slot[0]


@contextmanager
def by_node_context(pool, node):
    """
    Get a connection from the pool and automatically release it back
    """
    connection = pool.get_connection_by_node(node)
    yield connection
    pool.release(connection)

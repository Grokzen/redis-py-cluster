# -*- coding: utf-8 -*-

# python std lib
import os
import threading
from itertools import chain

# rediscluster imports
from rediscluster.nodemanager import NodeManager
from rediscluster.exceptions import RedisClusterException

# 3rd party imports
from redis.connection import ConnectionPool, Connection


class ClusterConnectionPool(ConnectionPool):
    """
    Custom connection pool for rediscluster
    """
    RedisClusterDefaultTimeout = None

    def __init__(self, startup_nodes=None, init_slot_cache=True, connection_class=Connection, max_connections=None, **connection_kwargs):
        super(ClusterConnectionPool, self).__init__(connection_class=connection_class, max_connections=max_connections)

        self.nodes = NodeManager(startup_nodes)
        if init_slot_cache:
            self.nodes.initialize()

        self.connections = {}
        self.connection_kwargs = connection_kwargs
        self.reset()

        if "socket_timeout" not in self.connection_kwargs:
            self.connection_kwargs["socket_timeout"] = ClusterConnectionPool.RedisClusterDefaultTimeout

    def __repr__(self):
        """
        TODO: Overwrite default implementation with something that prints how many cluster connections exists
        """
        return super(ClusterConnectionPool, self).__repr__()

    def reset(self):
        """
        # TODO: Should handle new cluster connections, maybe no additions is required.
        """
        # TODO: When resetting, all old connections should be closed and cleaned up
        self.pid = os.getpid()
        self._created_connections = 0
        self._available_connections = {}  # Dict(Node, List)
        self._in_use_connections = {}  # Dict(Node, Set)
        self._check_lock = threading.Lock()

        self._available_pubsub_connections = []
        self._in_use_pubsub_connections = set([])

    def _checkpid(self):
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
            raise Exception("get_connection should not be in use...")

        # TOOD: Pop existing connection if it exists
        connection = self.make_connection(self.nodes.pubsub_node)
        self._in_use_pubsub_connections.add(connection)
        return connection

    def make_connection(self, node):
        """
        Create a new connection
        """
        if self.count_num_connections() >= self.max_connections:
            self.close_existing_connection()
        self._created_connections += 1
        connection = self.connection_class(host=node["host"], port=node["port"], **self.connection_kwargs)

        # Must store node in the connection to make it eaiser to track
        connection._node = node

        return connection

    def release(self, connection):
        """
        Releases the connection back to the pool
        """
        self._checkpid()
        if connection.pid != self.pid:
            return

        if connection in self._in_use_pubsub_connections:
            print(" ? Releasing pubsub back to pool: {0}".format(connection))
            self._in_use_pubsub_connections.remove(connection)
            self._available_pubsub_connections.append(connection)
        else:
            print(" ? Releasing back to pool: {0}".format(connection))
            # Remove the current connection from _in_use_connection and add it back to the available pool
            self._in_use_connections.get(connection._node["name"], set()).remove(connection)
            self._available_connections.setdefault(connection._node["name"], []).append(connection)

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

        all_pubsub_conns = chain(
            self._available_pubsub_connections,
            self._in_use_pubsub_connections,
        )

        for connection in all_pubsub_conns:
            print("Disconnecting pubsub {0}".format(connection))
            connection.disconnect()

    def close_existing_connection(self):
        """
        Close random connections until open connections >= max_connections
        """
        # TODO: It could be possible that this code will get stuck in a infinite loop. It must be fixed
        # while len(self.connections) >= self.max_connections:
        while self.count_num_connections() >= self.max_connections:
            # Shuffle all connections and close the first one in the list.
            # random.shuffle(self.startup_nodes)
            node = self.nodes.random_startup_node()
            # connection = self.connections.get(self.startup_nodes[0]["name"], None)
            connection = self.connections.get(node["name"], None)
            if connection:
                self.release(connection)
                # self.close_redis_connection(connection)
                # del self.connections[self.startup_nodes[0]["name"]]

    def count_num_connections(self):
        i = 0
        for node, connections in self._in_use_connections.items():
            i += len(connections)
        return i

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

        # for node in self.nodes.random_startup_node_ittr():
        #     self.nodes.set_node_name(node)

        #     try:
        #         conn = self.connections.get(node["name"], None)

        #         if not conn:
        #             conn = self.get_connection_by_node(node)
        #             if conn.send_command("PING") is True:
        #                 self.connections[node["name"]] = conn
        #                 return conn
        #             else:
        #                 # TODO: This do not work proper yet
        #                 # conn.connection.disconnect()
        #                 pass
        #         else:
        #             # if conn.ping() is True:
        #             if conn.send_command("PING") is True:
        #                 return conn
        #     except RedisClusterException:
        #         raise

        raise Exception("Cant reach a single startup node.")

    def get_connection_by_key(self, key):
        if not key:
            raise RedisClusterException("No way to dispatch this command to Redis Cluster.")
        return self.get_connection_by_slot(self.keyslot(key))

    def get_connection_by_slot(self, slot):
        """
        Determine what server a specific slot belongs to and return a redis object that is connected
        """
        node = self.nodes.slots[slot]
        if not node:
            return self.get_random_connection()
        return self.get_connection_by_node(node)

    def get_connection_by_node(self, node):
        """
        get a connection by node
        """
        self.nodes.set_node_name(node)

        try:
            # Special case for pubsub node
            if node == self.nodes.pubsub_node:
                return self.get_connection("pubsub")

            # Try to get connection from existing pool
            connection = self._available_connections.get(node["name"], []).pop()
            print(" # Reusing connection: {0}".format(connection))
        except IndexError:
            print(" # Making Brand new connection")
            connection = self.make_connection(node)

        self._in_use_connections.setdefault(node["name"], set()).add(connection)

        return connection

    @staticmethod
    def execute_asking_command_via_connection(r, *argv, **kwargs):
        pipe = r.pipeline(transaction=False)
        pipe.execute_command('ASKING')
        pipe.execute_command(*argv, **kwargs)
        _asking_result, result = pipe.execute(raise_on_error=False)
        if isinstance(result, Exception):
            raise result
        return result

    @staticmethod
    def execute_command_via_connection(r, *argv, **kwargs):
        return r.execute_command(*argv, **kwargs)

    def get_node_by_slot(self, slot):
        return self.nodes.slots[slot]

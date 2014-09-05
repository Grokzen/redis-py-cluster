# -*- coding: utf-8 -*-
from .exceptions import RedisClusterException


def send_to_connection_by_key(func):
    def inner(self, key, *args, **kwargs):
        conn = self.get_connection_by_key(key)
        return func(conn, key, *args, **kwargs)
    return inner


def send_eval_to_connection(func):
    """
    If all the keys route to the same slot we can safely route the script to a node in the cluster.
    """
    def inner(self, script, numkeys, *keys_and_args):
        if numkeys < 1:
            raise RedisClusterException(" ERROR: eval only works with 1 or more keys when running redis in cluster mode...")

        # verify that the keys all map to the same key hash slot.
        # this will be true if there is only one key, or if all the keys are in the form:
        # A{foo} B{foo} C{foo}
        if len(set([self.keyslot(key) for key in keys_and_args[0:numkeys]])) != 1:
            raise RedisClusterException(" ERROR: eval only works if all keys map to the same key slot when running redis in cluster mode...")
        conn = self.get_connection_by_key(keys_and_args[0])
        return func(conn, script, numkeys, *keys_and_args)
    return inner


def send_to_all_master_nodes(func):
    """
    Use the following command only on master nodes
    """
    def inner(self, *args, **kwargs):
        res = {}

        # TODO: Bug, until startup_nodes is refactored "master" must be default because some nodes do not have "server_type"
        for node in self.startup_nodes:
            if node.get("server_type", "master") != "master":
                continue

            conn = get_connection_from_node_obj(self, node)
            res[node["name"]] = func(conn, *args, **kwargs)
        return res
    return inner


def send_to_all_masters_merge_list(func):
    """
    Use the following command only on master nodes and merge result into list
    """
    def inner(self, *args, **kwargs):
        res = set([])

        # TODO: Bug, until startup_nodes is refactored "master" must be default because some nodes do not have "server_type"
        for node in self.startup_nodes:
            if node.get("server_type", "master") != "master":
                continue

            conn = get_connection_from_node_obj(self, node)
            d = func(conn, *args, **kwargs)
            for i in d:
                res.add(i)
        return list(res)
    return inner


def send_to_all_nodes(func):
    """
    Itterate over all connections and call 'func' on each StrictRedis connection object.
    Store and return all items in one dict object.
    """
    def inner(self, *args, **kwargs):
        res = {}
        for node in self.startup_nodes:
            conn = get_connection_from_node_obj(self, node)
            res[node["name"]] = func(conn, *args, **kwargs)
        return res
    return inner


def send_to_all_nodes_merge_list(func):
    """
    Itterate over all connections and call 'func' on each StrictRedis connection object.
    Store and return all items in one list object.
    """
    def inner(self, *args, **kwargs):
        # TODO: Currently there is a bug with startup_nodes that cause one or more nodes to be querried multiple times
        #  and that will corrupt results. Using a set will remove any result duplicates. It should be a list.
        res = set([])
        for node in self.startup_nodes:
            conn = get_connection_from_node_obj(self, node)
            d = func(conn, *args, **kwargs)
            for i in d:
                res.add(i)
        return list(res)
    return inner


def get_connection_from_node_obj(self, node):
    """
    Gets a connection object from a 'node' object
    """
    self.set_node_name(node)
    conn = self.connections.get(node["name"], None)

    if not conn:
        conn = self.get_redis_link(node["host"], int(node["port"]))
        try:
            if conn.ping() is True:
                self.close_existing_connection()
                self.connections[node["name"]] = conn
        except Exception:
            raise RedisClusterException("unable to open new connection to node {0}".format(node))
    return conn


def send_to_random_node(func):
    def inner(self, *args, **kwargs):
        conn = self.get_random_connection()
        return func(conn, *args, **kwargs)
    return inner


def block_command(func):
    """
    Prints error because some commands should be blocked when running in cluster-mode
    """
    def inner(*args, **kwargs):
        raise RedisClusterException(" ERROR: Calling function {} is blocked when running redis in cluster mode...".format(func.__name__))
    return inner


def block_pipe_command(func):
    """
    Prints error because some pipelined commands should be blocked when running in cluster-mode
    """
    def inner(*args, **kwargs):
        raise RedisClusterException(" ERROR: Calling pipelined function {} is blocked when running redis in cluster mode...".format(func.__name__))
    return inner

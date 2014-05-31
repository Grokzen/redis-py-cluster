# -*- coding: utf-8 -*-

# python std lib
import time
import random

# rediscluster imports
from .crc import crc16

# 3rd party imports
import redis


class RedisClusterException(Exception):
    pass


class RedisCluster(object):
    RedisClusterHashSlots = 16384
    RedisClusterRequestTTL = 16
    RedisClusterDefaultTimeout = 1

    def __init__(self, startup_nodes=[], max_connections=32, blocked_commands=None, **kwargs):
        """
        startup_nodes     --> List of nodes that initial bootstrapping can be done from
        max_connections   --> Maximum number of connections that should be kept open at one time
        blocked_commands  --> Provide custom list/tuple of commands that should be blocked by this cluster object
        **kwargs          --> Extra arguments that will be sent into StrictRedis instance when created
                              (See Official redis-py doc for supported kwargs [https://github.com/andymccurdy/redis-py/blob/master/redis/client.py])
                              Some kwargs is not supported and will raise RedisClusterException
                               - db    (Redis do not support database SELECT in cluster mode)
                               - host  (Redis provides this when bootstrapping the cluster)
                               - port  (Redis provides this when bootstrapping the cluster)
        """
        if not blocked_commands:
            self.blocked_commands = ("info", "multi", "exec", "slaveof", "config", "shutdown")
        else:
            self.blocked_commands = blocked_commands

        self.startup_nodes = startup_nodes
        self.max_connections = max_connections
        self.connections = {}
        self.opt = kwargs
        self.refresh_table_asap = False

        # Tweaks to StrictRedis client arguments when running in cluster mode
        if "socket_timeout" not in self.opt:
            self.opt["socket_timeout"] = RedisCluster.RedisClusterDefaultTimeout
        if "db" in self.opt:
            raise RedisClusterException("(error) ERR SELECT is not allowed in cluster mode [Remove 'db' from kwargs]")
        if "host" in self.opt:
            raise RedisClusterException("[Remove 'host' from kwargs]")
        if "port" in self.opt:
            raise RedisClusterException("[Remove 'port' from kwargs]")

        self.initialize_slots_cache()

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

                for line in resp.split("\n"):
                    fields = line.split(" ")
                    if len(fields) == 1:
                        # We have an empty row so do not parse it
                        continue

                    addr = fields[1]
                    slots = fields[8:]
                    if addr == ":0":  # this is self
                        addr = "{0}:{1}".format(node["host"], node["port"])
                    addr_ip, addr_port = addr.split(":")
                    addr_port = int(addr_port)
                    addr = {"host": addr_ip, "port": addr_port, "name": addr}
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
            except Exception:
                pass

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

    def get_key_from_command(self, argv):
        """
        returns the key from argv list if the command is not present in blocked_commands set
        """
        return None if argv[0].lower() in self.blocked_commands else argv[1]

    def close_existing_connection(self):
        """
        Close random connections until open connections >= max_connections
        """
        while len(self.connections) >= self.max_connections:
            # TODO: Close a random connection
            print("Close connections")

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
            key = self.get_key_from_command(argv)
            if not key:
                raise Exception("No way to dispatch this command to Redis Cluster.")
            slot = self.keyslot(key)
            if try_random_node:
                r = self.get_random_connection()
                try_random_node = False
            else:
                r = self.get_connection_by_slot(slot)

            try:
                asking = False
                return r.execute_command(*argv)
            except Exception as e:
                try_random_node = True
                if ttl < self.RedisClusterRequestTTL / 2:
                    time.sleep(0.1)

                errv = e.message.split(" ")
                if errv[0] == "MOVED" or errv[0] == "ASK":
                    if errv[0] == "ASK":
                        # TODO: Implement asking, whatever that is Oo
                        print(" ** ASKING...")
                        asking = True
                    else:
                        self.refresh_table_asap = True

                    a = errv[2].split(":")
                    self.slots[int(errv[1])] = {"host": a[0], "port": int(a[1])}
                else:
                    raise

        raise Exception("To many Cluster redirections?")

    def get(self, key):
        return self.send_cluster_command("GET", key)

    def set(self, key, value):
        return self.send_cluster_command("SET", key, value)

    def smembers(self, key):
        return self.send_cluster_command("SMEMBERS", key)

    def srem(self, key, value):
        return self.send_cluster_command("SREM", key, value)

    def delete(self, key):
        """
        DEL is a reserved word in python so delete instead
        """
        return self.send_cluster_command("DEL", key)

    def sadd(self, key, value):
        return self.send_cluster_command("SADD", key, value)

    def publish(self, key, value):
        return self.send_cluster_command("PUBLISH", key, value)

    def hset(self, key, field, value):
        return self.send_cluster_command("HSET", key, field, value)

    def hget(self, key, field):
        return self.send_cluster_command("HGET", key, field)

    def hdel(self, key, field):
        return self.send_cluster_command("HDEL", key, field)

    def hexists(self, key, field):
        return self.send_cluster_command("HEXISTS", key, field)

    def type(self, key):
        return self.send_cluster_command("TYPE", key)

    def exists(self, key):
        return self.send_cluster_command("EXISTS", key)

    def rename(self, key1, key2):
        raise Exception("MULTI KEY requests NOT SUPPORTED")

    def renamex(self, key1, key2):
        raise Exception("MULTI KEY requests NOT SUPPORTED")

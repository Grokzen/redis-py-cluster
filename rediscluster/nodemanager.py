# -*- coding: utf-8 -*-

# python std lib
import random

# rediscluster imports
from .crc import crc16
from .exceptions import RedisClusterException

# 3rd party imports
from redis import StrictRedis
from redis._compat import unicode
from redis import ConnectionError


class NodeManager(object):
    RedisClusterHashSlots = 16384

    def __init__(self, startup_nodes=None, **connection_kwargs):
        self.connection_kwargs = connection_kwargs
        self.nodes = {}
        self.slots = {}
        self.startup_nodes = [] if startup_nodes is None else startup_nodes
        self.orig_startup_nodes = [node for node in self.startup_nodes]
        self.pubsub_node = None

        if len(self.startup_nodes) == 0:
            raise RedisClusterException("No startup nodes provided")

    def keyslot(self, key):
        """
        Calculate keyslot for a given key.

        This also works for binary keys that is used in python 3.
        """
        k = unicode(key)
        start = k.find("{")

        if start > -1:
            end = k.find("}", start + 1)
            if end > -1 and end != start + 1:
                k = k[start + 1:end]

        return crc16(k) % self.RedisClusterHashSlots

    def all_nodes(self):
        for node in self.nodes.values():
            yield node

    def all_masters(self):
        for node in self.nodes.values():
            if node["server_type"] == "master":
                yield node

    def random_startup_node(self):
        random.shuffle(self.startup_nodes)

        return self.startup_nodes[0]

    def random_startup_node_ittr(self):
        """
        Generator that will return a random startup nodes. Works as a generator.
        """
        while True:
            yield random.choice(self.startup_nodes)

    def random_node(self):
        key = random.choice(list(self.nodes.keys()))

        return self.nodes[key]

    def get_redis_link(self, host, port, decode_responses=False):
        allowed_keys = (
            'host',
            'port',
            'db',
            'password',
            'socket_timeout',
            'socket_connect_timeout',
            'socket_keepalive',
            'socket_keepalive_options',
            'connection_pool',
            'unix_socket_path',
            'encoding',
            'encoding_errors',
            'charset',
            'errors',
            'decode_responses',
            'retry_on_timeout',
            'ssl',
            'ssl_keyfile',
            'ssl_certfile',
            'ssl_cert_reqs',
            'ssl_ca_certs',
            'max_connections',
        )
        disabled_keys = (
            'host',
            'port',
            'decode_responses',
        )
        connection_kwargs = {k:v for k,v in self.connection_kwargs.iteritems() if k in set(allowed_keys) - set(disabled_keys)}
        return StrictRedis(host=host, port=port, decode_responses=decode_responses, **connection_kwargs)

    def initialize(self):
        """
        Init the slots cache by asking all startup nodes what the current cluster configuration is

        TODO: Currently the last node will have the last say about how the configuration is setup.
        Maybe it should stop to try after it have correctly covered all slots or when one node is reached
         and it could execute CLUSTER SLOTS command.
        """
        nodes_cache = {}
        tmp_slots = {}

        all_slots_covered = False
        disagreements = []
        startup_nodes_reachable = False

        for node in self.orig_startup_nodes:
            try:
                r = self.get_redis_link(host=node["host"], port=node["port"], decode_responses=True)
                cluster_slots = r.execute_command("cluster", "slots")
                startup_nodes_reachable = True
            except ConnectionError:
                continue
            except Exception as e:
                raise RedisClusterException("ERROR sending 'cluster slots' command to redis server: {}".format(node))

            all_slots_covered = True

            # If there's only one server in the cluster, its ``host`` is ''
            # Fix it to the host in startup_nodes
            if (len(cluster_slots) == 1 and len(cluster_slots[0][2][0]) == 0 and len(self.startup_nodes) == 1):
                cluster_slots[0][2][0] = self.startup_nodes[0]['host']

            # No need to decode response because StrictRedis should handle that for us...
            for slot in cluster_slots:
                master_node = slot[2]

                if master_node[0] == '':
                    master_node[0] = node['host']
                master_node[1] = int(master_node[1])

                node, node_name = self.make_node_obj(master_node[0], master_node[1], 'master')
                nodes_cache[node_name] = node

                for i in range(int(slot[0]), int(slot[1]) + 1):
                    if i not in tmp_slots:
                        tmp_slots[i] = [node]
                        slave_nodes = [slot[j] for j in range(3, len(slot))]

                        for slave_node in slave_nodes:
                            target_slave_node, slave_node_name = self.make_node_obj(slave_node[0], slave_node[1], 'slave')
                            nodes_cache[slave_node_name] = target_slave_node
                            tmp_slots[i].append(target_slave_node)
                    else:
                        # Validate that 2 nodes want to use the same slot cache setup
                        if tmp_slots[i][0]['name'] != node['name']:
                            disagreements.append("{} vs {} on slot: {}".format(
                                tmp_slots[i][0]['name'], node['name'], i),
                            )

                            if len(disagreements) > 5:
                                raise RedisClusterException("startup_nodes could not agree on a valid slots cache. %s" % ", ".join(disagreements))

                self.populate_startup_nodes()
                self.refresh_table_asap = False

            # Validate if all slots are covered or if we should try next startup node
            for i in range(0, self.RedisClusterHashSlots):
                if i not in tmp_slots:
                    all_slots_covered = False

            if all_slots_covered:
                # All slots are covered and application can continue to execute
                # Parse and determine what node will be pubsub node
                break

        if not startup_nodes_reachable:
            raise RedisClusterException("Redis Cluster cannot be connected. Please provide at least one reachable node.")

        if not all_slots_covered:
            raise RedisClusterException("All slots are not covered after query all startup_nodes. {} of {} covered...".format(
                len(tmp_slots), self.RedisClusterHashSlots))

        # Set the tmp variables to the real variables
        self.slots = tmp_slots
        self.nodes = nodes_cache

        self.determine_pubsub_node()

    def determine_pubsub_node(self):
        """
        Determine what node object should be used for pubsub commands.

        All clients in the cluster will talk to the same pubsub node to ensure
        all code stay compatible. See pubsub doc for more details why.

        Allways use the server with highest port number
        """
        highest = -1
        node = None

        for n in self.nodes.values():
            if n["port"] > highest:
                highest = n["port"]
                node = n

        self.pubsub_node = {"host": node["host"], "port": node["port"], "server_type": node["server_type"], "pubsub": True}

    def set_node_name(self, n):
        """
        Format the name for the given node object

        # TODO: This shold not be constructed this way. It should update the name of the node in the node cache dict
        """
        if "name" not in n:
            n["name"] = "{0}:{1}".format(n["host"], n["port"])

    def make_node_obj(self, host, port, server_type):
        """
        Create a node datastructure.

        Returns the node datastructure and the node name
        """
        node_name = "{0}:{1}".format(host, port)
        node = {
            'host': host,
            'port': port,
            'name': node_name,
            'server_type': server_type
        }

        return (node, node_name)

    def set_node(self, host, port, server_type=None):
        """
        Update data for a node.
        """
        node, node_name = self.make_node_obj(host, port, server_type)
        self.nodes[node_name] = node

        return node

    def populate_startup_nodes(self):
        """
        Do something with all startup nodes and filters out any duplicates
        """
        for item in self.startup_nodes:
            self.set_node_name(item)

        for n in self.nodes.values():
            if n not in self.startup_nodes:
                self.startup_nodes.append(n)

        # freeze it so we can set() it
        uniq = set([frozenset(node.items()) for node in self.startup_nodes])
        # then thaw it back out into a list of dicts
        self.startup_nodes = [dict(node) for node in uniq]

    def reset(self):
        """
        Drop all node data and start over from startup_nodes
        """
        self.initialize()

# -*- coding: utf-8 -*-

# python std lib
import random

# rediscluster imports
from .crc import crc16
from .exceptions import RedisClusterException

# 3rd party imports
from redis import StrictRedis
from redis._compat import unicode, nativestr
from redis import ConnectionError


class NodeManager(object):
    RedisClusterHashSlots = 16384

    def __init__(self, startup_nodes=None):
        self.nodes = []
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
        for node in self.nodes:
            yield node

    def all_masters(self):
        for node in self.nodes:
            if node["server_type"] == "master":
                yield node

    def random_startup_node(self):
        random.shuffle(self.startup_nodes)
        return self.startup_nodes[0]

    def random_startup_node_ittr(self):
        """
        Generator that will return a random startup nodes. Works as a generator.
        """
        # TODO: Make this picka a random connection w/o having to shuffle around all startup nodes
        # return self.startup_nodes[0]
        while True:
            random.shuffle(self.startup_nodes)
            yield self.startup_nodes[0]

    def random_node(self):
        # TODO: Make this get a random node
        return self.nodes[0]

    def get_redis_link(self, host, port, decode_responses=False):
        return StrictRedis(host=host, port=port, decode_responses=decode_responses)

    def initialize(self):
        """
        Init the slots cache by asking all startup nodes what the current cluster configuration is

        TODO: Currently the last node will have the last say about how the configuration is setup.
        Maybe it should stop to try after it have correctly covered all slots or when one node is reached
         and it could execute CLUSTER SLOTS command.
        """
        # Reset variables
        self.flush_nodes_cache()
        self.flush_slots_cache()
        all_slots_covered = False
        for node in self.startup_nodes:
            try:
                r = self.get_redis_link(host=node["host"], port=node["port"], decode_responses=True)
                cluster_slots = r.execute_command("cluster", "slots")
            except ConnectionError:
                continue
            except Exception as e:
                raise RedisClusterException("ERROR sending 'cluster slots' command to redis server: {}".format(node))

            all_slots_covered = True

            # If there's only one server in the cluster, its ``host`` is ''
            # Fix it to the host in startup_nodes
            if (len(cluster_slots) == 1 and len(cluster_slots[0][2][0]) == 0
                    and len(self.startup_nodes) == 1):
                cluster_slots[0][2][0] = self.startup_nodes[0]['host']

            # No need to decode response because StrictRedis should handle that for us...
            for slot in cluster_slots:
                master_node = slot[2]

                # Only store the master node as address for each slot.
                # TODO: Slave nodes have to be fixed/patched in later...
                master_addr = {
                    "host": master_node[0],
                    "port": master_node[1],
                    "name": "{0}:{1}".format(master_node[0], master_node[1]),
                    "server_type": "master",
                }

                self.nodes.append(master_addr)
                for i in range(int(slot[0]), int(slot[1]) + 1):
                    if i not in self.slots:
                        self.slots[i] = master_addr
                    else:
                        # Validate that 2 nodes want to use the same slot cache setup
                        if self.slots[i] != master_addr:
                            raise RedisClusterException("startup_nodes could not agree on a valid slots cache. {} vs {} on slo: {}".format(self.slots[i], master_addr, i))

                slave_nodes = [slot[i] for i in range(3, len(slot))]
                for slave_node in slave_nodes:
                    slave_addr = {
                        "host": slave_node[0],
                        "port": slave_node[1],
                        "name": "{0}:{1}".format(slave_node[0], slave_node[1]),
                        "server_type": "slave",
                    }
                    self.nodes.append(slave_addr)

                self.populate_startup_nodes()
                self.refresh_table_asap = False

            # Validate if all slots are covered or if we should try next startup node
            for i in range(0, self.RedisClusterHashSlots):
                if i not in self.slots:
                    all_slots_covered = False

            if all_slots_covered:
                # All slots are covered and application can continue to execute
                # Parse and determine what node will be pubsub node
                self.determine_pubsub_node()
                return

        if not all_slots_covered:
            raise RedisClusterException("All slots are not covered after query all startup_nodes. {} of {} covered...".format(len(self.slots), self.RedisClusterHashSlots))

    def determine_pubsub_node(self):
        """
        Determine what node object should be used for pubsub commands.

        All clients in the cluster will talk to the same pubsub node to ensure
        all code stay compatible. See pubsub doc for more details why.

        Allways use the server with highest port number
        """
        highest = -1
        node = None
        for n in self.nodes:
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

    def set_slot(self, slot, host=None, port=None, server_type=None):
        """
        Update data for a node on a slot.
        """
        # In case the slot do not exists yet
        self.slots.setdefault(slot, {})

        if host:
            self.slots[slot]['host'] = host
        if port:
            self.slots[slot]['port'] = port
        if host and port:
            self.slots[slot]['name'] = "{0}:{1}".format(host, port)
        if server_type:
            self.slots[slot]['server_type'] = server_type

        return self.slots[slot]

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

    def reset(self):
        """
        Drop all node data and start over from startup_nodes
        """
        self.flush_nodes_cache()
        self.flush_slots_cache()
        self.initialize()

    def flush_slots_cache(self):
        """
        Reset slots cache back to empty dict
        """
        self.slots = {}

    def flush_nodes_cache(self):
        """
        Reset nodes cache back to empty dict
        """
        self.nodes = []

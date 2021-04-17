# -*- coding: utf-8 -*-

# python std lib
import json
import logging
import random
import socket

# rediscluster imports
from .crc import crc16
from .exceptions import RedisClusterException, RedisClusterConfigError

# 3rd party imports
from redis import Redis
from redis.connection import Encoder
from redis import ConnectionError, TimeoutError, ResponseError

log = logging.getLogger(__name__)


class NodeManager(object):
    """
    """
    REDIS_CLUSTER_HASH_SLOTS = 16384

    def __init__(self, startup_nodes=None, reinitialize_steps=None, skip_full_coverage_check=False, nodemanager_follow_cluster=False,
                 host_port_remap=None, **connection_kwargs):
        """
        :skip_full_coverage_check:
            Skips the check of cluster-require-full-coverage config, useful for clusters
            without the CONFIG command (like aws)
        :nodemanager_follow_cluster:
            The node manager will during initialization try the last set of nodes that
            it was operating on. This will allow the client to drift along side the cluster
            if the cluster nodes move around alot.
        """
        log.debug("Creating new NodeManager instance")

        self.connection_kwargs = connection_kwargs
        self.nodes = {}
        self.slots = {}
        self.startup_nodes = [] if startup_nodes is None else startup_nodes
        self.orig_startup_nodes = [node for node in self.startup_nodes]
        self.reinitialize_counter = 0
        self.reinitialize_steps = reinitialize_steps or 25
        self._skip_full_coverage_check = skip_full_coverage_check
        self.nodemanager_follow_cluster = nodemanager_follow_cluster
        self.encoder = Encoder(
            connection_kwargs.get('encoding', 'utf-8'),
            connection_kwargs.get('encoding_errors', 'strict'),
            connection_kwargs.get('decode_responses', False)
        )
        self._validate_host_port_remap(host_port_remap)
        self.host_port_remap = host_port_remap

        if not self.startup_nodes:
            raise RedisClusterException("No startup nodes provided")

    def _validate_host_port_remap(self, host_port_remap):
        """
        Helper method that validates all entries in the host_port_remap config.
        """
        if host_port_remap is None:
            # Nothing to validate if config not set
            return

        if not isinstance(host_port_remap, list):
            raise RedisClusterConfigError("host_port_remap must be a list")

        for item in host_port_remap:
            if not isinstance(item, dict):
                raise RedisClusterConfigError("items inside host_port_remap list must be of dict type")

            if len(set(item.keys()) - {'from_host', 'from_port', 'to_host', 'to_port'}) != 0:
                raise RedisClusterConfigError("Invalid keys provided in host_port_remap rule")

            # If we have from_host, we must have a to_host option to allow for translation to work
            if ('from_host' in item and 'to_host' not in item) or ('from_host' not in item and 'to_host' in item):
                raise RedisClusterConfigError("Both from_host and to_host must be present in host_port_remap rule if either is defined")

            if ('from_port' in item and 'to_port' not in item) or ('from_port' not in item and 'to_port' in item):
                raise RedisClusterConfigError("Both from_port and to_port must be present in host_port_remap rule if either is defined")

            try:
                socket.inet_aton(item.get('from_host', '0.0.0.0').strip())
                socket.inet_aton(item.get('to_host', '0.0.0.0').strip())
            except socket.error:
                raise RedisClusterConfigError("Both from_host and to_host in host_port_remap rule must be a valid ip address")
            if len(item.get('from_host', '0.0.0.0').split('.')) < 4 or len(item.get('to_host', '0.0.0.0').split('.')) < 4:
                raise RedisClusterConfigError(
                    "Both from_host and to_host in host_port_remap rule must must have all octets specified")

            try:
                int(item.get('from_port', 0))
                int(item.get('to_port', 0))
            except ValueError:
                raise RedisClusterConfigError("Both from_port and to_port in host_port_remap rule must be integers")

    def keyslot(self, key):
        """
        Calculate keyslot for a given key.
        Tuned for compatibility with python 2.7.x
        """
        k = self.encoder.encode(key)

        start = k.find(b"{")

        if start > -1:
            end = k.find(b"}", start + 1)
            if end > -1 and end != start + 1:
                k = k[start + 1:end]

        return crc16(k) % self.REDIS_CLUSTER_HASH_SLOTS

    def node_from_slot(self, slot):
        """
        """
        for node in self.slots[slot]:
            if node['server_type'] == 'master':
                return node

    def all_nodes(self):
        """
        """
        for node in self.nodes.values():
            yield node

    def all_masters(self):
        """
        """
        for node in self.nodes.values():
            if node["server_type"] == "master":
                yield node

    def random_startup_node(self):
        """
        """
        random.shuffle(self.startup_nodes)

        return self.startup_nodes[0]

    def random_startup_node_ittr(self):
        """
        Generator that will return a random startup nodes. Works as a generator.
        """
        while True:
            yield random.choice(self.startup_nodes)

    def random_node(self):
        """
        """
        key = random.choice(list(self.nodes.keys()))

        return self.nodes[key]

    def get_redis_link(self, host, port, decode_responses=False):
        """
        """
        allowed_keys = (
            'host',
            'port',
            'db',
            'username',
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
        connection_kwargs = {
            k: v
            for k, v in self.connection_kwargs.items()
            if k in set(allowed_keys) - set(disabled_keys)
        }

        return Redis(
            host=host,
            port=port,
            decode_responses=decode_responses,
            **connection_kwargs
        )

    def initialize(self):
        """
        Init the slots cache by asking all startup nodes what the current cluster configuration is
        """
        log.debug("Running initialize on NodeManager")
        log.debug("Original startup nodes configuration")
        log.debug(json.dumps(self.orig_startup_nodes, indent=2))

        nodes_cache = {}
        tmp_slots = {}

        all_slots_covered = False
        disagreements = []
        startup_nodes_reachable = False

        nodes = self.orig_startup_nodes

        # With this option the client will attempt to connect to any of the previous set of nodes instead of the original set of nodes
        if self.nodemanager_follow_cluster:
            nodes = self.startup_nodes

        for node in nodes:
            try:
                r = self.get_redis_link(host=node["host"], port=node["port"], decode_responses=True)
                cluster_slots = r.execute_command("cluster", "slots")
                startup_nodes_reachable = True
            except (ConnectionError, TimeoutError):
                continue
            except ResponseError as e:
                log.exception("ReseponseError sending 'cluster slots' to redis server")

                # Isn't a cluster connection, so it won't parse these exceptions automatically
                message = e.__str__()
                if 'CLUSTERDOWN' in message or 'MASTERDOWN' in message:
                    continue
                else:
                    raise RedisClusterException("ERROR sending 'cluster slots' command to redis server: {0}".format(node))
            except Exception:
                raise RedisClusterException("ERROR sending 'cluster slots' command to redis server: {0}".format(node))

            all_slots_covered = True

            # If there's only one server in the cluster, its ``host`` is ''
            # Fix it to the host in startup_nodes
            if (len(cluster_slots) == 1 and len(cluster_slots[0][2][0]) == 0 and len(self.startup_nodes) == 1):
                cluster_slots[0][2][0] = self.startup_nodes[0]['host']

            # No need to decode response because Redis should handle that for us...
            for slot in cluster_slots:
                master_node = slot[2]

                if master_node[0] == '':
                    master_node[0] = node['host']
                master_node[1] = int(master_node[1])

                master_node = self.remap_internal_node_object(master_node)

                node, node_name = self.make_node_obj(master_node[0], master_node[1], 'master')
                nodes_cache[node_name] = node

                for i in range(int(slot[0]), int(slot[1]) + 1):
                    if i not in tmp_slots:
                        tmp_slots[i] = [node]
                        slave_nodes = [slot[j] for j in range(3, len(slot))]

                        for slave_node in slave_nodes:
                            slave_node = self.remap_internal_node_object(slave_node)
                            target_slave_node, slave_node_name = self.make_node_obj(slave_node[0], slave_node[1], 'slave')
                            nodes_cache[slave_node_name] = target_slave_node
                            tmp_slots[i].append(target_slave_node)
                    else:
                        # Validate that 2 nodes want to use the same slot cache setup
                        if tmp_slots[i][0]['name'] != node['name']:
                            disagreements.append("{0} vs {1} on slot: {2}".format(
                                tmp_slots[i][0]['name'], node['name'], i),
                            )

                            if len(disagreements) > 5:
                                raise RedisClusterException("startup_nodes could not agree on a valid slots cache. {0}".format(", ".join(disagreements)))

                self.populate_startup_nodes()
                self.refresh_table_asap = False

            if self._skip_full_coverage_check:
                need_full_slots_coverage = False
            else:
                need_full_slots_coverage = self.cluster_require_full_coverage(nodes_cache)

            # Validate if all slots are covered or if we should try next startup node
            for i in range(0, self.REDIS_CLUSTER_HASH_SLOTS):
                if i not in tmp_slots and need_full_slots_coverage:
                    all_slots_covered = False

            if all_slots_covered:
                # All slots are covered and application can continue to execute
                break

        if not startup_nodes_reachable:
            raise RedisClusterException("Redis Cluster cannot be connected. Please provide at least one reachable node.")

        if not all_slots_covered:
            raise RedisClusterException("All slots are not covered after query all startup_nodes. {0} of {1} covered...".format(
                len(tmp_slots), self.REDIS_CLUSTER_HASH_SLOTS))

        # Set the tmp variables to the real variables
        self.slots = tmp_slots
        self.nodes = nodes_cache
        self.reinitialize_counter = 0

        log.debug("NodeManager initialize done : Nodes")
        log.debug(json.dumps(self.nodes, indent=2))

    def remap_internal_node_object(self, node_obj):
        if not self.host_port_remap:
            # No remapping rule set, return object unmodified
            return node_obj

        for remap_rule in self.host_port_remap:
            if self._remap_rule_applies(remap_rule, node_obj):
                # We have found a valid match and can proceed with the remapping
                if 'to_host' in remap_rule:
                    node_obj[0] = remap_rule['to_host']
                if 'to_port' in remap_rule:
                    node_obj[1] = remap_rule['to_port']
                # At this point remapping has occurred, so no further rules should be processed
                break

        return node_obj

    def _remap_rule_applies(self, remap_rule, node_obj):
        # Double check to make sure that the relevant host and/or port fields are present
        if not (('from_host' in remap_rule and 'to_host' in remap_rule) or ('from_port' in remap_rule and 'to_port' in remap_rule)):
            return False
        if 'from_host' in remap_rule and not self._ips_equal(remap_rule['from_host'], node_obj[0]):
            return False
        if 'from_port' in remap_rule and remap_rule['from_port'] != node_obj[1]:
            return False
        # If the previous conditions are not met then this is a valid match.
        return True

    def _ips_equal(self, ip1, ip2):
        split_ip1 = ip1.strip().split(".")
        split_ip2 = ip2.strip().split(".")
        for i, octet in enumerate(split_ip1):
            if int(octet) != int(split_ip2[i]):
                return False
        return True

    def increment_reinitialize_counter(self, ct=1, count=1):
        for i in range(min(ct, self.reinitialize_steps)):
            self.reinitialize_counter += count
            if self.reinitialize_counter % self.reinitialize_steps == 0:
                self.initialize()

    def cluster_require_full_coverage(self, nodes_cache):
        """
        if exists 'cluster-require-full-coverage no' config on redis servers,
        then even all slots are not covered, cluster still will be able to
        respond
        """
        nodes = nodes_cache or self.nodes

        def node_require_full_coverage(node):
            try:
                r_node = self.get_redis_link(
                    host=node["host"],
                    port=node["port"],
                    decode_responses=True,
                )
                return "yes" in r_node.config_get("cluster-require-full-coverage").values()
            except ConnectionError:
                return False
            except Exception:
                raise RedisClusterException("ERROR sending 'config get cluster-require-full-coverage' command to redis server: {0}".format(node))

        # at least one node should have cluster-require-full-coverage yes
        return any(node_require_full_coverage(node) for node in nodes.values())

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
        uniq = {frozenset(node.items()) for node in self.startup_nodes}
        # then thaw it back out into a list of dicts
        self.startup_nodes = [dict(node) for node in uniq]

    def reset(self):
        """
        Drop all node data and start over from startup_nodes
        """
        self.initialize()

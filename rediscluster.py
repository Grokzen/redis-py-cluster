# python std lib
import time
import random

# 3rd party imports
import redis


def crc16(s):
    XMODEMCRC16Lookup = [
        0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50a5, 0x60c6, 0x70e7,
        0x8108, 0x9129, 0xa14a, 0xb16b, 0xc18c, 0xd1ad, 0xe1ce, 0xf1ef,
        0x1231, 0x0210, 0x3273, 0x2252, 0x52b5, 0x4294, 0x72f7, 0x62d6,
        0x9339, 0x8318, 0xb37b, 0xa35a, 0xd3bd, 0xc39c, 0xf3ff, 0xe3de,
        0x2462, 0x3443, 0x0420, 0x1401, 0x64e6, 0x74c7, 0x44a4, 0x5485,
        0xa56a, 0xb54b, 0x8528, 0x9509, 0xe5ee, 0xf5cf, 0xc5ac, 0xd58d,
        0x3653, 0x2672, 0x1611, 0x0630, 0x76d7, 0x66f6, 0x5695, 0x46b4,
        0xb75b, 0xa77a, 0x9719, 0x8738, 0xf7df, 0xe7fe, 0xd79d, 0xc7bc,
        0x48c4, 0x58e5, 0x6886, 0x78a7, 0x0840, 0x1861, 0x2802, 0x3823,
        0xc9cc, 0xd9ed, 0xe98e, 0xf9af, 0x8948, 0x9969, 0xa90a, 0xb92b,
        0x5af5, 0x4ad4, 0x7ab7, 0x6a96, 0x1a71, 0x0a50, 0x3a33, 0x2a12,
        0xdbfd, 0xcbdc, 0xfbbf, 0xeb9e, 0x9b79, 0x8b58, 0xbb3b, 0xab1a,
        0x6ca6, 0x7c87, 0x4ce4, 0x5cc5, 0x2c22, 0x3c03, 0x0c60, 0x1c41,
        0xedae, 0xfd8f, 0xcdec, 0xddcd, 0xad2a, 0xbd0b, 0x8d68, 0x9d49,
        0x7e97, 0x6eb6, 0x5ed5, 0x4ef4, 0x3e13, 0x2e32, 0x1e51, 0x0e70,
        0xff9f, 0xefbe, 0xdfdd, 0xcffc, 0xbf1b, 0xaf3a, 0x9f59, 0x8f78,
        0x9188, 0x81a9, 0xb1ca, 0xa1eb, 0xd10c, 0xc12d, 0xf14e, 0xe16f,
        0x1080, 0x00a1, 0x30c2, 0x20e3, 0x5004, 0x4025, 0x7046, 0x6067,
        0x83b9, 0x9398, 0xa3fb, 0xb3da, 0xc33d, 0xd31c, 0xe37f, 0xf35e,
        0x02b1, 0x1290, 0x22f3, 0x32d2, 0x4235, 0x5214, 0x6277, 0x7256,
        0xb5ea, 0xa5cb, 0x95a8, 0x8589, 0xf56e, 0xe54f, 0xd52c, 0xc50d,
        0x34e2, 0x24c3, 0x14a0, 0x0481, 0x7466, 0x6447, 0x5424, 0x4405,
        0xa7db, 0xb7fa, 0x8799, 0x97b8, 0xe75f, 0xf77e, 0xc71d, 0xd73c,
        0x26d3, 0x36f2, 0x0691, 0x16b0, 0x6657, 0x7676, 0x4615, 0x5634,
        0xd94c, 0xc96d, 0xf90e, 0xe92f, 0x99c8, 0x89e9, 0xb98a, 0xa9ab,
        0x5844, 0x4865, 0x7806, 0x6827, 0x18c0, 0x08e1, 0x3882, 0x28a3,
        0xcb7d, 0xdb5c, 0xeb3f, 0xfb1e, 0x8bf9, 0x9bd8, 0xabbb, 0xbb9a,
        0x4a75, 0x5a54, 0x6a37, 0x7a16, 0x0af1, 0x1ad0, 0x2ab3, 0x3a92,
        0xfd2e, 0xed0f, 0xdd6c, 0xcd4d, 0xbdaa, 0xad8b, 0x9de8, 0x8dc9,
        0x7c26, 0x6c07, 0x5c64, 0x4c45, 0x3ca2, 0x2c83, 0x1ce0, 0x0cc1,
        0xef1f, 0xff3e, 0xcf5d, 0xdf7c, 0xaf9b, 0xbfba, 0x8fd9, 0x9ff8,
        0x6e17, 0x7e36, 0x4e55, 0x5e74, 0x2e93, 0x3eb2, 0x0ed1, 0x1ef0
    ]

    crc = 0
    for ch in s:
        crc = ((crc << 8) & 0xffff) ^ XMODEMCRC16Lookup[((crc >> 8) ^ ord(ch)) & 0xff]

    return crc


class RedisCluster(object):
    RedisClusterHashSlots = 16384
    RedisClusterRequestTTL = 16
    RedisClusterDefaultTimeout = 1

    def __init__(self, startup_nodes, connections, **kwargs):
        self.blocked_commands = ("info", "multi", "exec", "slaveof", "config", "shutdown")
        self.startup_nodes = startup_nodes
        self.max_connections = connections
        self.connections = {}
        self.opt = kwargs
        self.refresh_table_asap = False
        self.initialize_slots_cache()

    def get_redis_link(self, host, port):
        timeout = self.opt.get("timeout") or RedisCluster.RedisClusterDefaultTimeout
        return redis.StrictRedis(host=host, port=port, socket_timeout=timeout)

    def set_node_name(self, n):
        if "name" not in n:
            n["name"] = "{0}:{1}".format(n["host"], n["port"])

    def initialize_slots_cache(self):
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
                        for i in xrange(int(first), int(last) + 1):
                            self.slots[i] = addr

                self.populate_startup_nodes()
                self.refresh_table_asap = False
            except Exception:
                pass

    def populate_startup_nodes(self):
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
        self.slots = {}

    def keyslot(self, key):
        start = key.find("{")
        if start > -1:
            end = key.find("}", start + 1)
            if end > -1 and end != start + 1:
                key = key[start + 1:end]
        return crc16(key) % self.RedisClusterHashSlots

    def get_key_from_command(self, argv):
        return None if argv[0].lower() in self.blocked_commands else argv[1]

    def close_existing_connection(self):
        while len(self.connections) >= self.max_connections:
            # TODO: Close a random connection
            print("Close connections")

    def get_random_connection(self):
        random.shuffle(self.startup_nodes)
        for node in self.startup_nodes:
            try:
                self.set_node_name(node)
                conn = self.connections.get(node["name"], None)

                if not conn:
                    conn = redis.StrictRedis(host=node["host"], port=int(node["port"]))
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
            except Exception:
                # Just try with the next node
                pass

        raise Exception("Cant reach a single startup node.")

    def get_connection_by_slot(self, slot):
        node = self.slots[slot]
        if not node:
            return self.get_random_connection()
        self.set_node_name(node)
        if not self.connections.get(node["name"], None):
            try:
                self.close_existing_connection()
                self.connections[node["name"]] = redis.StrictRedis(host=node["host"], port=node["port"])
            except Exception:
                # This will probably never happen with recent redis-rb
                # versions because the connection is enstablished in a lazy
                # way only when a command is called. However it is wise to
                # handle an instance creation error of some kind.
                return self.get_random_connection()
        return self.connections[node["name"]]

    def send_cluster_command(self, *argv, **kwargs):
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

# -*- coding: utf-8 -*-
from collections import defaultdict

from .connection import ClusterConnectionPool
from .exceptions import RedisClusterException
from .utils import clusterdown_wrapper, first_key, nslookup


class RedisClusterMgt(object):

    blocked_args = ('addslots', 'count_failure_reports',
                    'countkeysinslot', 'delslots', 'failover', 'forget',
                    'getkeysinslot', 'keyslot', 'meet', 'replicate', 'reset',
                    'saveconfig', 'set_config_epoch', 'setslot', 'slaves')

    def __init__(self, startup_nodes=None, **kwargs):
        self.connection_pool = ClusterConnectionPool(
            startup_nodes=startup_nodes,
            init_slot_cache=True, **kwargs
        )

    def __getattr__(self, attr):
        if attr in self.blocked_args:
            raise RedisClusterException('%s is currently not supported' % attr)
        raise RedisClusterException('%s is not a valid Redis cluster argument' % attr)

    @clusterdown_wrapper
    def _execute_command_on_nodes(self, nodes, *args, **kwargs):
        command = args[0]
        res = {}
        for node in nodes:
            c = self.connection_pool.get_connection_by_node(node)
            try:
                c.send_command(*args)
                res[node["name"]] = c.read_response()
            finally:
                self.connection_pool.release(c)
        return first_key(command, res)

    def _execute_cluster_commands(self, *args, **kwargs):
        args = ('cluster',) + args
        node = self.connection_pool.nodes.random_node()
        return self._execute_command_on_nodes([node], *args, **kwargs)

    def info(self):
        raw = self._execute_cluster_commands('info')

        def _split(line):
            k, v = line.split(':')
            yield k
            yield v
        return {k: v for k, v in
                [_split(line) for line in raw.split('\r\n') if line]}

    def _make_host(self, host, port):
        return '%s:%s' % (host, port)

    def slots(self, host_required=False):
        slots_info = self._execute_cluster_commands('slots')
        master_slots = defaultdict(list)
        slave_slots = defaultdict(list)
        for item in slots_info:
            master_ip, master_port = item[2]
            slots = [item[0], item[1]]
            master_host = nslookup(master_ip) if host_required else master_ip
            master_slots[self._make_host(master_host, master_port)].append(slots)
            slaves = item[3:]
            for slave_ip, slave_port in slaves:
                slave_host = nslookup(slave_ip) if host_required else slave_ip
                slave_slots[self._make_host(slave_host, slave_port)].append(slots)

        return {
            'master': master_slots,
            'slave': slave_slots
        }

    def _parse_node_line(self, line):
        line_items = line.split(' ')
        ret = line_items[:8]
        slots = [sl.split('-') for sl in line_items[8:]]
        ret.append(slots)
        return ret

    def nodes(self, host_required=False):
        raw = self._execute_cluster_commands('nodes')
        ret = {}
        for line in raw.split('\n'):
            if not line:
                continue
            node_id, ip_port, flags, master_id, ping, pong, epoch, \
                status, slots = self._parse_node_line(line)
            role = flags
            if ',' in flags:
                _, role = flags.split(',')

            host = nslookup(ip_port) if host_required else ip_port
            ret[host] = {
                'node_id': node_id,
                'role': role,
                'master_id': master_id,
                'last_ping_sent': ping,
                'last_pong_rcvd': pong,
                'epoch': epoch,
                'status': status,
                'slots': slots
            }
        return ret

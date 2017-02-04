# -*- coding: utf-8 -*-
from socket import gethostbyaddr
from functools import wraps

# rediscluster imports
from .exceptions import (
    RedisClusterException, ClusterDownError
)

# 3rd party imports
from redis._compat import basestring, nativestr


def bool_ok(response, *args, **kwargs):
    """
    Borrowed from redis._compat becuase that method to not support extra arguments
    when used in a cluster environment.
    """
    return nativestr(response) == 'OK'


def string_keys_to_dict(key_strings, callback):
    """
    Maps each string in `key_strings` to `callback` function
    and return as a dict.
    """
    return dict.fromkeys(key_strings, callback)


def dict_merge(*dicts):
    """
    Merge all provided dicts into 1 dict.
    """
    merged = {}

    for d in dicts:
        if not isinstance(d, dict):
            raise ValueError('Value should be of dict type')
        else:
            merged.update(d)

    return merged


def blocked_command(self, command):
    """
    Raises a `RedisClusterException` mentioning the command is blocked.
    """
    raise RedisClusterException("Command: {0} is blocked in redis cluster mode".format(command))


def merge_result(command, res):
    """
    Merge all items in `res` into a list.

    This command is used when sending a command to multiple nodes
    and they result from each node should be merged into a single list.
    """
    if not isinstance(res, dict):
        raise ValueError('Value should be of dict type')

    result = set([])

    for _, v in res.items():
        for value in v:
            result.add(value)

    return list(result)


def first_key(command, res):
    """
    Returns the first result for the given command.

    If more then 1 result is returned then a `RedisClusterException` is raised.
    """
    if not isinstance(res, dict):
        raise ValueError('Value should be of dict type')

    if len(res.keys()) != 1:
        raise RedisClusterException("More then 1 result from command: {0}".format(command))

    return list(res.values())[0]


def clusterdown_wrapper(func):
    """
    Wrapper for CLUSTERDOWN error handling.

    If the cluster reports it is down it is assumed that:
     - connection_pool was disconnected
     - connection_pool was reseted
     - refereh_table_asap set to True

    It will try 3 times to rerun the command and raises ClusterDownException if it continues to fail.
    """
    @wraps(func)
    def inner(*args, **kwargs):
        for _ in range(0, 3):
            try:
                return func(*args, **kwargs)
            except ClusterDownError:
                # Try again with the new cluster setup. All other errors
                # should be raised.
                pass

        # If it fails 3 times then raise exception back to caller
        raise ClusterDownError("CLUSTERDOWN error. Unable to rebuild the cluster")
    return inner


def nslookup(node_ip):
    """
    """
    if ':' not in node_ip:
        return gethostbyaddr(node_ip)[0]

    ip, port = node_ip.split(':')

    return '{0}:{1}'.format(gethostbyaddr(ip)[0], port)


def parse_cluster_slots(resp, **options):
    """
    """
    current_host = options.get('current_host', '')

    def fix_server(*args):
        return (args[0] or current_host, args[1])

    slots = {}
    for slot in resp:
        start, end, master = slot[:3]
        slaves = slot[3:]
        slots[start, end] = {
            'master': fix_server(*master),
            'slaves': [fix_server(*slave) for slave in slaves],
        }

    return slots


def parse_cluster_nodes(resp, **options):
    """
    @see: http://redis.io/commands/cluster-nodes  # string
    @see: http://redis.io/commands/cluster-slaves # list of string
    """
    current_host = options.get('current_host', '')

    def parse_slots(s):
        slots, migrations = [], []
        for r in s.split(' '):
            if '->-' in r:
                slot_id, dst_node_id = r[1:-1].split('->-', 1)
                migrations.append({
                    'slot': int(slot_id),
                    'node_id': dst_node_id,
                    'state': 'migrating'
                })
            elif '-<-' in r:
                slot_id, src_node_id = r[1:-1].split('-<-', 1)
                migrations.append({
                    'slot': int(slot_id),
                    'node_id': src_node_id,
                    'state': 'importing'
                })
            elif '-' in r:
                start, end = r.split('-')
                slots.extend(range(int(start), int(end) + 1))
            else:
                slots.append(int(r))

        return slots, migrations

    if isinstance(resp, basestring):
        resp = resp.splitlines()

    nodes = []
    for line in resp:
        parts = line.split(' ', 8)
        self_id, addr, flags, master_id, ping_sent, \
            pong_recv, config_epoch, link_state = parts[:8]

        host, port = addr.rsplit(':', 1)

        node = {
            'id': self_id,
            'host': host or current_host,
            'port': int(port),
            'flags': tuple(flags.split(',')),
            'master': master_id if master_id != '-' else None,
            'ping-sent': int(ping_sent),
            'pong-recv': int(pong_recv),
            'link-state': link_state,
            'slots': [],
            'migrations': [],
        }

        if len(parts) >= 9:
            slots, migrations = parse_slots(parts[8])
            node['slots'], node['migrations'] = tuple(slots), migrations

        nodes.append(node)

    return nodes


def parse_pubsub_channels(command, resp, **options):
    aggregate = options.get('aggregate', True)
    if not aggregate:
        return resp

    nodes = resp.keys()
    channels = set()
    for node in nodes:
        channels.update(resp[node])
    return list(channels)
    

def parse_pubsub_numpat(command, resp, **options):
    aggregate = options.get('aggregate', True)
    if not aggregate:
        return resp

    numpat = 0
    for node, node_numpat in resp.items():
        numpat += node_numpat
    return numpat


def parse_pubsub_numsub(command, resp, **options):
    aggregate = options.get('aggregate', True)
    if not aggregate:
        return resp

    numsub_d = dict()
    for _, numsub_tups in resp.items():
        for channel, numsubbed in numsub_tups:
            try:
                numsub_d[channel] += numsubbed
            except KeyError:
                numsub_d[channel] = numsubbed

    ret_numsub = []
    for channel, numsub in numsub_d.items():
        ret_numsub.append((channel, numsub))
    return ret_numsub

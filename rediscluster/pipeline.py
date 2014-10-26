# -*- coding: utf-8 -*-

# python std lib
import random
import time

# rediscluster imports
from .decorators import block_pipeline_command
from .exceptions import RedisClusterException

# 3rd party imports
from redis import StrictRedis
from redis.exceptions import ResponseError, ConnectionError
from redis._compat import imap, unicode


class BaseClusterPipeline(object):
    """
    """

    def __init__(self, connection_pool, startup_nodes=[], connections=[], opt={}, refresh_table_asap=False, slots={}, nodes=[]):
        self.connection_pool = connection_pool
        self.startup_nodes = startup_nodes
        self.refresh_table_asap = refresh_table_asap
        self.command_stack = []

    def __repr__(self):
        return "%s".format(type(self).__name__)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.reset()

    def __del__(self):
        try:
            self.reset()
        except Exception:
            pass

    def __len__(self):
        return len(self.command_stack)

    def execute_command(self, *args, **kwargs):
        return self.pipeline_execute_command(*args, **kwargs)

    def pipeline_execute_command(self, *args, **options):
        self.command_stack.append((args, options))
        return self

    def raise_first_error(self, commands, response):
        for i, r in enumerate(response):
            if isinstance(r, ResponseError):
                self.annotate_exception(r, i + 1, commands[i][0])
                raise r

    def annotate_exception(self, exception, number, command):
        cmd = unicode(' ').join(imap(unicode, command))
        msg = unicode('Command # %d (%s) of pipeline caused error: %s') % (
            number, cmd, unicode(exception.args[0]))
        exception.args = (msg,) + exception.args[1:]

    def execute(self, raise_on_error=True):
        stack = self.command_stack
        if not stack:
            return []
        try:
            return self.send_cluster_commands(stack, raise_on_error)
        finally:
            self.reset()

    def reset(self):
        self.command_stack = []

    def send_cluster_commands(self, commands, raise_on_error=True):
        """
        Send a bunch of cluster commands to the redis cluster.
        """
        if self.refresh_table_asap:
            self.initialize_slots_cache()

        ttl = self.RedisClusterRequestTTL
        response = {}
        attempt = range(0, len(commands)) if commands else []
        ask_slots = {}
        while attempt and ttl > 0:
            ttl -= 1
            node_commands = {}
            nodes = {}
            for i in attempt:
                c = commands[i]
                slot = self.connection_pool.nodes.keyslot(c[0][1])
                if slot in ask_slots:
                    node = ask_slots[slot]
                else:
                    node = self.connection_pool.nodes.slots[slot]

                self.set_node_name(node)
                node_name = node['name']
                nodes[node_name] = node
                if node_name not in node_commands:
                    node_commands[node_name] = {}
                node_commands[node_name][i] = c

            attempt = []

            for node_name in node_commands:
                node = nodes[node_name]
                cmds = [node_commands[node_name][i] for i in sorted(node_commands[node_name].keys())]
                r = self.set_connection_by_node(node)

                pipe = r.pipeline(transaction=False)
                for args, kwargs in cmds:
                    pipe.execute_command(*args, **kwargs)

                for i, v in zip(sorted(node_commands[node_name].keys()), self.perform_execute_pipeline(pipe)):
                    response[i] = v
            ask_slots = {}
            for i, v in response.items():
                if isinstance(v, Exception):
                    if isinstance(v, ConnectionError):
                        ask_slots[self.connection_pool.nodes.keyslot(commands[i][0][1])] = random.choice(self.startup_nodes)
                        attempt.append(i)
                        if ttl < self.RedisClusterRequestTTL / 2:
                            time.sleep(0.1)
                        continue

                    redir = self.parse_redirection_exception(v)
                    if not redir:
                        continue

                    if redir['action'] == "MOVED":
                        self.refresh_table_asap = True
                        self.slots[redir['slot']] = {'host': redir['host'], 'port': redir['port']}
                        attempt.append(i)
                    elif redir['action'] == "ASK":
                        attempt.append(i)
                        ask_slots[redir['slot']] = {
                            'name': '%s:%s' % (redir['host'], redir['port']),
                            'host': redir['host'],
                            'port': redir['port']}
                        continue

        response = [response[k] for k in sorted(response.keys())]
        if raise_on_error:
            self.raise_first_error(commands, response)
        return response

    @staticmethod
    def perform_execute_pipeline(pipe):
        return pipe.execute(raise_on_error=False)

    def multi(self):
        raise RedisClusterException("method multi() is not implemented")

    def immediate_execute_command(self, *args, **options):
        raise RedisClusterException("method immediate_execute_command() is not implemented")

    def _execute_transaction(self, connection, commands, raise_on_error):
        raise RedisClusterException("method _execute_transaction() is not implemented")

    def load_scripts(self):
        raise RedisClusterException("method load_scripts() is not implemented")

    def watch(self, *names):
        raise RedisClusterException("method watch() is not implemented")

    def unwatch(self):
        raise RedisClusterException("method unwatch() is not implemented")

    def script_load_for_pipeline(self, script):
        raise RedisClusterException("method script_load_for_pipeline() is not implemented")

    def delete(self, *names):
        """
        "Delete a key specified by ``names``"
        """
        if len(names) != 1:
            raise RedisClusterException("deleting multiple keys is not implemented in pipeline command")

        return self.execute_command('DEL', names[0])


# Blocked pipeline commands
BaseClusterPipeline.mget = block_pipeline_command(StrictRedis.mget)
BaseClusterPipeline.mset = block_pipeline_command(StrictRedis.mset)
BaseClusterPipeline.msetnx = block_pipeline_command(StrictRedis.msetnx)
BaseClusterPipeline.rename = block_pipeline_command(StrictRedis.rename)
BaseClusterPipeline.renamenx = block_pipeline_command(StrictRedis.renamenx)
BaseClusterPipeline.brpoplpush = block_pipeline_command(StrictRedis.brpoplpush)
BaseClusterPipeline.rpoplpush = block_pipeline_command(StrictRedis.rpoplpush)
BaseClusterPipeline.sort = block_pipeline_command(StrictRedis.sort)
BaseClusterPipeline.sdiff = block_pipeline_command(StrictRedis.sdiff)
BaseClusterPipeline.sdiffstore = block_pipeline_command(StrictRedis.sdiffstore)
BaseClusterPipeline.sinter = block_pipeline_command(StrictRedis.sinter)
BaseClusterPipeline.sinterstore = block_pipeline_command(StrictRedis.sinterstore)
BaseClusterPipeline.smove = block_pipeline_command(StrictRedis.smove)
BaseClusterPipeline.sunion = block_pipeline_command(StrictRedis.sunion)
BaseClusterPipeline.sunionstore = block_pipeline_command(StrictRedis.sunionstore)
BaseClusterPipeline.pfmerge = block_pipeline_command(StrictRedis.pfmerge)

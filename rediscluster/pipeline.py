# -*- coding: utf-8 -*-

# python std lib
import random
import sys
import time

try:
    import os
    os.environ["GEVENT_RESOLVER"] = "ares"
    import gevent
    import gevent.monkey
    gevent.monkey.patch_socket()
except ImportError:
    gevent = False

# rediscluster imports
from .client import RedisCluster
from .connection import by_node_context
from .exceptions import RedisClusterException, ClusterDownException
from .utils import clusterdown_wrapper

# 3rd party imports
from redis import StrictRedis
from redis.exceptions import ResponseError, ConnectionError
from redis._compat import imap, unicode


class StrictClusterPipeline(RedisCluster):
    """
    """

    def __init__(self, connection_pool, response_callbacks=None, startup_nodes=[], connections=[], opt={}, refresh_table_asap=False, slots={}, nodes=[]):
        self.connection_pool = connection_pool
        self.startup_nodes = startup_nodes
        self.refresh_table_asap = refresh_table_asap
        self.command_stack = []
        self.response_callbacks = response_callbacks

    def __repr__(self):
        return "{}".format(type(self).__name__)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.reset()

    def __del__(self):
        self.reset()

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
        """
        Reset back to empty pipeline.
        """
        self.command_stack = []
        self.refresh_table_asap = False

        self.scripts = set()

        # TODO: Implement
        # make sure to reset the connection state in the event that we were
        # watching something
        # if self.watching and self.connection:
        #     try:
        #         # call this manually since our unwatch or
        #         # immediate_execute_command methods can call reset()
        #         self.connection.send_command('UNWATCH')
        #         self.connection.read_response()
        #     except ConnectionError:
        #         # disconnect will also remove any previous WATCHes
        #         self.connection.disconnect()

        # clean up the other instance attributes
        self.watching = False
        self.explicit_transaction = False

        # TODO: Implement
        # we can safely return the connection to the pool here since we're
        # sure we're no longer WATCHing anything
        # if self.connection:
        #     self.connection_pool.release(self.connection)
        #     self.connection = None

    @clusterdown_wrapper
    def send_cluster_commands(self, stack, raise_on_error=True, allow_redirections=True):
        """
        Send a bunch of cluster commands to the redis cluster.

        `allow_redirections` If the pipeline should follow `ASK` & `MOVED` responses
        automatically. If set to false it will raise RedisClusterException.
        """
        if self.refresh_table_asap:
            self.connection_pool.nodes.initialize()
            self.refresh_table_asap = False

        ttl = self.RedisClusterRequestTTL
        response = {}
        attempt = range(0, len(stack)) if stack else []
        ask_slots = {}

        while attempt and ttl > 0:
            ttl -= 1
            node_commands = {}
            nodes = {}

            # Keep this section so that we can determine what nodes to contact
            for i in attempt:
                c = stack[i]
                slot = self.connection_pool.nodes.keyslot(c[0][1])
                if slot in ask_slots:
                    node = ask_slots[slot]
                else:
                    node = self.connection_pool.nodes.slots[slot]

                self.connection_pool.nodes.set_node_name(node)
                node_name = node['name']
                nodes[node_name] = node
                if node_name not in node_commands:
                    node_commands[node_name] = {}
                node_commands[node_name][i] = c

            # Get one connection at a time from the pool and basiccly copy the logic from
            #  _execute_pipeline() below and do what a normal pipeline does.

            attempt = []
            if gevent:
                jobs = dict()
                for node_name in node_commands:
                    node = nodes[node_name]
                    cmds = [node_commands[node_name][i] for i in sorted(node_commands[node_name].keys())]
                    with by_node_context(self.connection_pool, node) as connection:
                        jobs[node_name] = gevent.spawn(self._execute_pipeline, connection, cmds, False)

                gevent.joinall(jobs.values(), timeout=10)
                for node_name in jobs:
                    job = jobs[node_name]
                    if job.exception:
                        for i in sorted(node_commands[node_name].keys()):
                            response[i] = job.exception
                    else:
                        for i, v in zip(sorted(node_commands[node_name].keys()), job.value):
                            response[i] = v
            else:
                for node_name in node_commands:
                    node = nodes[node_name]
                    cmds = [node_commands[node_name][i] for i in sorted(node_commands[node_name].keys())]
                    with by_node_context(self.connection_pool, node) as connection:
                        result = zip(
                            sorted(node_commands[node_name].keys()),
                            self._execute_pipeline(connection, cmds, False))
                        for i, v in result:
                            response[i] = v

            ask_slots = {}
            for i, v in response.items():
                if not isinstance(v, Exception):
                    continue

                if isinstance(v, ConnectionError):
                    ask_slots[self.connection_pool.nodes.keyslot(stack[i][0][1])] = random.choice(self.startup_nodes)
                    attempt.append(i)
                    if ttl < self.RedisClusterRequestTTL / 2:
                        time.sleep(0.1)
                    continue

                errv = RedisCluster._exception_message(v)
                if errv is None:
                    continue

                if errv.startswith('CLUSTERDOWN'):
                    self.connection_pool.disconnect()
                    self.connection_pool.reset()
                    self.refresh_table_asap = True
                    raise ClusterDownException()

                redir = self.parse_redirection_exception_msg(errv)

                if not redir:
                    continue

                if redir['action'] == "MOVED":
                    self.refresh_table_asap = True
                    self.connection_pool.nodes.set_slot(
                        slot=redir['slot'],
                        host=redir['host'],
                        port=redir['port'],
                    )
                    attempt.append(i)
                    self._fail_on_redirect(allow_redirections)
                elif redir['action'] == "ASK":
                    ask_slots[redir['slot']] = {
                        'name': '{0}:{1}'.format(redir['host'], redir['port']),
                        'host': redir['host'],
                        'port': redir['port'],
                    }
                    attempt.append(i)
                    self._fail_on_redirect(allow_redirections)

        response = [response[k] for k in sorted(response.keys())]
        if raise_on_error:
            self.raise_first_error(stack, response)
        return response

    def _fail_on_redirect(self, allow_redirections):
        """
        """
        if not allow_redirections:
            raise RedisClusterException("ASK & MOVED redirection not allowed in this pipeline")

    def _execute_pipeline(self, connection, commands, raise_on_error):
        """
        Code borrowed from StrictRedis so it can be fixed
        """
        # build up all commands into a single request to increase network perf
        all_cmds = connection.pack_commands([args for args, _ in commands])
        try:
            connection.send_packed_command(all_cmds)
        except ConnectionError as e:
            return [e for _ in xrange(len(commands))]

        response = []
        for args, options in commands:
            try:
                response.append(self.parse_response(connection, args[0], **options))
            except ResponseError:
                response.append(sys.exc_info()[1])

        if raise_on_error:
            self.raise_first_error(commands, response)
        return response

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


def block_pipeline_command(func):
    """
    Prints error because some pipelined commands should be blocked when running in cluster-mode
    """
    def inner(*args, **kwargs):
        raise RedisClusterException("ERROR: Calling pipelined function {} is blocked when running redis in cluster mode...".format(func.__name__))
    return inner


# Blocked pipeline commands
StrictClusterPipeline.mget = block_pipeline_command(StrictRedis.mget)
StrictClusterPipeline.mset = block_pipeline_command(StrictRedis.mset)
StrictClusterPipeline.msetnx = block_pipeline_command(StrictRedis.msetnx)
StrictClusterPipeline.rename = block_pipeline_command(StrictRedis.rename)
StrictClusterPipeline.renamenx = block_pipeline_command(StrictRedis.renamenx)
StrictClusterPipeline.brpoplpush = block_pipeline_command(StrictRedis.brpoplpush)
StrictClusterPipeline.rpoplpush = block_pipeline_command(StrictRedis.rpoplpush)
StrictClusterPipeline.sort = block_pipeline_command(StrictRedis.sort)
StrictClusterPipeline.sdiff = block_pipeline_command(StrictRedis.sdiff)
StrictClusterPipeline.sdiffstore = block_pipeline_command(StrictRedis.sdiffstore)
StrictClusterPipeline.sinter = block_pipeline_command(StrictRedis.sinter)
StrictClusterPipeline.sinterstore = block_pipeline_command(StrictRedis.sinterstore)
StrictClusterPipeline.smove = block_pipeline_command(StrictRedis.smove)
StrictClusterPipeline.sunion = block_pipeline_command(StrictRedis.sunion)
StrictClusterPipeline.sunionstore = block_pipeline_command(StrictRedis.sunionstore)
StrictClusterPipeline.pfmerge = block_pipeline_command(StrictRedis.pfmerge)

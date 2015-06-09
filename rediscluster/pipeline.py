# -*- coding: utf-8 -*-

# python std lib
import random
import sys
import time
import threading

# rediscluster imports
from .client import StrictRedisCluster
from .connection import by_node_context
from .exceptions import RedisClusterException, ClusterDownException
from .utils import clusterdown_wrapper

# 3rd party imports
from redis import StrictRedis
from redis.exceptions import ResponseError, ConnectionError
from redis._compat import imap, unicode, xrange


class StrictClusterPipeline(StrictRedisCluster):
    """
    """

    def __init__(self, connection_pool, nodes_callbacks=None, result_callbacks=None,
                 response_callbacks=None, startup_nodes=None, refresh_table_asap=False,
                 use_threads=True):
        self.connection_pool = connection_pool
        self.startup_nodes = startup_nodes if startup_nodes else []
        self.refresh_table_asap = refresh_table_asap
        self.command_stack = []

        self.nodes_callbacks = nodes_callbacks
        self.result_callbacks = result_callbacks
        self.response_callbacks = response_callbacks
        self.use_threads = use_threads

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
        attempt = xrange(0, len(stack)) if stack else []  # noqa
        ask_slots = {}

        while attempt and ttl > 0:
            ttl -= 1
            node_commands = {}
            nodes = {}

            # Keep this section so that we can determine what nodes to contact
            for i in attempt:
                c = stack[i]
                slot = self._determine_slot(*c[0])
                if slot in ask_slots:
                    node = ask_slots[slot]
                else:
                    node = self.connection_pool.nodes.slots[slot]

                self.connection_pool.nodes.set_node_name(node)
                node_name = node['name']
                nodes[node_name] = node
                node_commands.setdefault(node_name, {})
                node_commands[node_name][i] = c

            # Get one connection at a time from the pool and basiccly copy the logic from
            #  _execute_pipeline() below and do what a normal pipeline does.

            attempt = []
            if self.use_threads and len(node_commands) > 1:
                workers = dict()
                for node_name in node_commands:
                    node = nodes[node_name]
                    cmds = [node_commands[node_name][i] for i in sorted(node_commands[node_name].keys())]
                    with by_node_context(self.connection_pool, node) as connection:
                        workers[node_name] = Worker(self._execute_pipeline, connection, cmds, False)
                        workers[node_name].start()

                for node_name, worker in workers.items():
                    worker.join()
                    if worker.exception:
                        for i in sorted(node_commands[node_name].keys()):
                            response[i] = worker.exception
                    else:
                        for i, v in zip(sorted(node_commands[node_name].keys()), worker.value):
                            response[i] = v
                del workers
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

                errv = StrictRedisCluster._exception_message(v)
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
                    node = self.connection_pool.nodes.set_node(redir['host'], redir['port'], server_type='master')
                    self.connection_pool.nodes.slots[redir['slot']] = node
                    attempt.append(i)
                    self._fail_on_redirect(allow_redirections)
                elif redir['action'] == "ASK":
                    node = self.connection_pool.nodes.set_node(redir['host'], redir['port'], server_type='master')
                    ask_slots[redir['slot']] = node
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
            return [e for _ in xrange(len(commands))]  # noqa

        response = []
        for args, options in commands:
            try:
                response.append(self.parse_response(connection, args[0], **options))
            except (ConnectionError, ResponseError):
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
StrictClusterPipeline.bgrewriteaof = block_pipeline_command(StrictRedis.bgrewriteaof)
StrictClusterPipeline.bgsave = block_pipeline_command(StrictRedis.bgsave)
StrictClusterPipeline.bitop = block_pipeline_command(StrictRedis.bitop)
StrictClusterPipeline.brpoplpush = block_pipeline_command(StrictRedis.brpoplpush)
StrictClusterPipeline.client_getname = block_pipeline_command(StrictRedis.client_getname)
StrictClusterPipeline.client_kill = block_pipeline_command(StrictRedis.client_kill)
StrictClusterPipeline.client_list = block_pipeline_command(StrictRedis.client_list)
StrictClusterPipeline.client_setname = block_pipeline_command(StrictRedis.client_setname)
StrictClusterPipeline.config_get = block_pipeline_command(StrictRedis.config_get)
StrictClusterPipeline.config_resetstat = block_pipeline_command(StrictRedis.config_resetstat)
StrictClusterPipeline.config_rewrite = block_pipeline_command(StrictRedis.config_rewrite)
StrictClusterPipeline.config_set = block_pipeline_command(StrictRedis.config_set)
StrictClusterPipeline.dbsize = block_pipeline_command(StrictRedis.dbsize)
StrictClusterPipeline.echo = block_pipeline_command(StrictRedis.echo)
StrictClusterPipeline.evalsha = block_pipeline_command(StrictRedis.evalsha)
StrictClusterPipeline.flushall = block_pipeline_command(StrictRedis.flushall)
StrictClusterPipeline.flushdb = block_pipeline_command(StrictRedis.flushdb)
StrictClusterPipeline.info = block_pipeline_command(StrictRedis.info)
StrictClusterPipeline.keys = block_pipeline_command(StrictRedis.keys)
StrictClusterPipeline.lastsave = block_pipeline_command(StrictRedis.lastsave)
StrictClusterPipeline.mget = block_pipeline_command(StrictRedis.mget)
StrictClusterPipeline.move = block_pipeline_command(StrictRedis.move)
StrictClusterPipeline.mset = block_pipeline_command(StrictRedis.mset)
StrictClusterPipeline.msetnx = block_pipeline_command(StrictRedis.msetnx)
StrictClusterPipeline.pfmerge = block_pipeline_command(StrictRedis.pfmerge)
StrictClusterPipeline.ping = block_pipeline_command(StrictRedis.ping)
StrictClusterPipeline.publish = block_pipeline_command(StrictRedis.publish)
StrictClusterPipeline.randomkey = block_pipeline_command(StrictRedis.randomkey)
StrictClusterPipeline.rename = block_pipeline_command(StrictRedis.rename)
StrictClusterPipeline.renamenx = block_pipeline_command(StrictRedis.renamenx)
StrictClusterPipeline.rpoplpush = block_pipeline_command(StrictRedis.rpoplpush)
StrictClusterPipeline.save = block_pipeline_command(StrictRedis.save)
StrictClusterPipeline.scan = block_pipeline_command(StrictRedis.scan)
StrictClusterPipeline.script_exists = block_pipeline_command(StrictRedis.script_exists)
StrictClusterPipeline.script_flush = block_pipeline_command(StrictRedis.script_flush)
StrictClusterPipeline.script_kill = block_pipeline_command(StrictRedis.script_kill)
StrictClusterPipeline.script_load = block_pipeline_command(StrictRedis.script_load)
StrictClusterPipeline.sdiff = block_pipeline_command(StrictRedis.sdiff)
StrictClusterPipeline.sdiffstore = block_pipeline_command(StrictRedis.sdiffstore)
StrictClusterPipeline.sentinel_get_master_addr_by_name = block_pipeline_command(StrictRedis.sentinel_get_master_addr_by_name)
StrictClusterPipeline.sentinel_master = block_pipeline_command(StrictRedis.sentinel_master)
StrictClusterPipeline.sentinel_masters = block_pipeline_command(StrictRedis.sentinel_masters)
StrictClusterPipeline.sentinel_monitor = block_pipeline_command(StrictRedis.sentinel_monitor)
StrictClusterPipeline.sentinel_remove = block_pipeline_command(StrictRedis.sentinel_remove)
StrictClusterPipeline.sentinel_sentinels = block_pipeline_command(StrictRedis.sentinel_sentinels)
StrictClusterPipeline.sentinel_set = block_pipeline_command(StrictRedis.sentinel_set)
StrictClusterPipeline.sentinel_slaves = block_pipeline_command(StrictRedis.sentinel_slaves)
StrictClusterPipeline.shutdown = block_pipeline_command(StrictRedis.shutdown)
StrictClusterPipeline.sinter = block_pipeline_command(StrictRedis.sinter)
StrictClusterPipeline.sinterstore = block_pipeline_command(StrictRedis.sinterstore)
StrictClusterPipeline.slaveof = block_pipeline_command(StrictRedis.slaveof)
StrictClusterPipeline.slowlog_get = block_pipeline_command(StrictRedis.slowlog_get)
StrictClusterPipeline.slowlog_len = block_pipeline_command(StrictRedis.slowlog_len)
StrictClusterPipeline.slowlog_reset = block_pipeline_command(StrictRedis.slowlog_reset)
StrictClusterPipeline.smove = block_pipeline_command(StrictRedis.smove)
StrictClusterPipeline.sort = block_pipeline_command(StrictRedis.sort)
StrictClusterPipeline.sunion = block_pipeline_command(StrictRedis.sunion)
StrictClusterPipeline.sunionstore = block_pipeline_command(StrictRedis.sunionstore)
StrictClusterPipeline.time = block_pipeline_command(StrictRedis.time)


class Worker(threading.Thread):
    """
    A simple thread wrapper class to perform an arbitrary function and store the result.
    Used to parallelize network i/o when issuing many pipelined commands to multiple nodes in the cluster.
    Later on we may need to convert this to a thread pool, although if you use gevent the current implementation
    is not too bad.
    """
    def __init__(self, func, *args, **kwargs):
        threading.Thread.__init__(self)
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.exception = None
        self.value = None

    def run(self):
        try:
            self.value = self.func(*self.args, **self.kwargs)
        except Exception as e:
            self.exception = e

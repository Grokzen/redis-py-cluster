# -*- coding: utf-8 -*-

# python std lib
import random
import sys
import time

# rediscluster imports
from .client import StrictRedisCluster
from .exceptions import (
    RedisClusterException, AskError, MovedError, ClusterDownError,
)
from .utils import clusterdown_wrapper

# 3rd party imports
from redis import StrictRedis
from redis.exceptions import ResponseError, ConnectionError, RedisError
from redis._compat import imap, unicode


class StrictClusterPipeline(StrictRedisCluster):
    """
    """

    def __init__(self, connection_pool, nodes_callbacks=None, result_callbacks=None,
                 response_callbacks=None, startup_nodes=None, refresh_table_asap=False,
                 reinitialize_steps=None):
        self.command_stack = []
        self.connection_pool = connection_pool
        self.nodes_callbacks = nodes_callbacks
        self.refresh_table_asap = refresh_table_asap
        self.reinitialize_counter = 0
        self.reinitialize_steps = reinitialize_steps or 25
        self.response_callbacks = response_callbacks
        self.result_callbacks = result_callbacks
        self.startup_nodes = startup_nodes if startup_nodes else []

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
        self.command_stack.append(PipelineCommand(args, options, len(self.command_stack)))
        return self

    def raise_first_error(self, stack):
        for c in stack:
            r = c.result
            if isinstance(r, ResponseError):
                self.annotate_exception(r, c.position + 1, c.args)
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

        # the first time sending the commands we send all of the commands that were queued up.
        # if we have to run through it again, we only retry the commands that failed.
        attempt = sorted(stack, key=lambda x: x.position)

        # as long as we have commands left to attempt and we haven't overrun the max attempts, keep trying.
        while attempt and ttl > 0:

            # decrement our counter for number of attempts left before giving up.
            ttl -= 1

            # each time we go through this we need to separate out the commands by node.
            node_commands = {}

            # build a list of node objects based on node names we need to
            nodes = {}

            # as we move through each command that still needs to be processed,
            # we figure out the slot number that command maps to, then from the slot determine the node.
            for c in attempt:
                # normally we just refer to our internal node -> slot table that tells us where a given
                # command should route to.
                # but if we are retrying, the cluster could have told us we were wrong or the node was down.
                # in that case, we have to try something that contradicts our rules.
                # there are different types of retries. redis cluster says if it responds with an ASK error,
                # you need to handle it differently than a moved error. And if we hit a connection error, we
                # don't really know what to do for that command so we pick a random other node in the cluster.
                if c.node is not None:
                    node = c.node
                else:
                    slot = self._determine_slot(*c.args)
                    if self.refresh_table_asap:  # MOVED
                        node = self.connection_pool.get_master_node_by_slot(slot)
                    else:
                        node = self.connection_pool.get_node_by_slot(slot)

                # little hack to make sure the node name is populated. probably could clean this up.
                self.connection_pool.nodes.set_node_name(node)

                # now that we know the name of the node ( it's just a string in the form of host:port )
                # we can build a list of commands for each node.
                node_name = node['name']
                if node_name not in nodes:
                    nodes[node_name] = NodeCommands(self.parse_response, self.connection_pool.get_connection_by_node(node))

                if c.asking:
                    nodes[node_name].append(PipelineCommand(['ASKING']))
                nodes[node_name].append(c)

            try:
                # send the commands in sequence.
                # we only write to all the open sockets for each node, we don't read
                # this allows us to flush all the requests out across the network essentially in parallel
                # so that we can read them all in parallel as they come back.
                # we dont' multiplex on the sockets as they come available, but that shouldn't make too much difference.
                node_commands = nodes.values()
                for n in node_commands:
                    n.write()

                for n in node_commands:
                    n.read()

            finally:
                # release all of the redis connections we allocated earlier back into the connection pool.
                for n in nodes.values():
                    self.connection_pool.release(n.connection)
                del nodes

            # if the response isn't an exception it is a valid response from the node
            # we're all done with that command, YAY!
            # if we move beyond this point, we've run into problems and we need to retry the command.
            attempt = sorted([c for c in attempt if isinstance(c.result, Exception)], key=lambda x: x.position)

            # now that we have tried to execute all the commands let's see what we have left.
            for c in attempt:
                c.node = None
                c.asking = False
                # connection errors are tricky because most likely we routed to the right node but it is
                # down. In that case, the best we can do is randomly try another node in the cluster
                # and hope that it tells us to try that node again with a MOVED error or tells us the new
                # master.
                if isinstance(c.result, ConnectionError):
                    c.node = random.choice(self.startup_nodes)
                    # if we are stuck in a retry loop, slow things down a bit to give the failover
                    # a chance of actually happening.
                    if ttl < self.RedisClusterRequestTTL / 2:
                        time.sleep(0.1)
                    continue

                # If cluster is down it should be raised and bubble up to
                # utils.clusterdown_wrapper()
                if isinstance(c.result, ClusterDownError):
                    self.connection_pool.disconnect()
                    self.connection_pool.reset()
                    self.refresh_table_asap = True

                    raise c.result

                # A MOVED response from the cluster means that somehow we were misinformed about which node
                # a given key slot maps to. This can happen during cluster resharding, during master-slave
                # failover, or if we got a connection error and were forced to re-attempt the command against a
                # random node.
                if isinstance(c.result, MovedError):
                    # Do not perform full cluster refresh on every MOVED error
                    self.reinitialize_counter += 1

                    if self.reinitialize_counter % self.reinitialize_steps == 0:
                        self.refresh_table_asap = True

                    node = self.connection_pool.nodes.set_node(c.result.host, c.result.port, server_type='master')
                    self.connection_pool.nodes.slots[c.result.slot_id][0] = node
                    self._fail_on_redirect(allow_redirections)

                # an ASK error from the server means that only this specific command needs to be tried against
                # a different server (not every key in the slot). This happens only during cluster re-sharding
                # and is a major pain in the ass. For it to work correctly, we have to resend the command to
                # the new node but only after first sending an ASKING command immediately beforehand.
                elif isinstance(c.result, AskError):
                    node = self.connection_pool.nodes.set_node(c.result.host, c.result.port, server_type='master')
                    c.node = node
                    c.asking = True
                    self._fail_on_redirect(allow_redirections)

        # YAY! we made it out of the attempt loop.
        # turn the response back into a simple flat array that corresponds
        # to the sequence of commands issued in the stack in pipeline.execute()
        response = [c.result for c in sorted(stack, key=lambda x: x.position)]

        if raise_on_error:
            self.raise_first_error(stack)

        return response

    def _fail_on_redirect(self, allow_redirections):
        """
        """
        if not allow_redirections:
            raise RedisClusterException("ASK & MOVED redirection not allowed in this pipeline")

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
StrictClusterPipeline.pfcount = block_pipeline_command(StrictRedis.pfcount)
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


class PipelineCommand(object):
    def __init__(self, args, options=None, position=None):
        self.args = args
        if options is None:
            options = {}
        self.options = options
        self.position = position
        self.result = None
        self.node = None
        self.asking = False


class NodeCommands(object):

    def __init__(self, parse_response, connection):
        self.parse_response = parse_response
        self.connection = connection
        self.commands = []

    def append(self, c):
        self.commands.append(c)

    def write(self):
        """
        Code borrowed from StrictRedis so it can be fixed
        """
        # build up all commands into a single request to increase network perf
        connection = self.connection
        commands = self.commands
        try:
            connection.send_packed_command(connection.pack_commands([c.args for c in commands]))
        except ConnectionError as e:
            for c in commands:
                c.result = e

    def read(self):
        connection = self.connection
        for c in self.commands:
            try:
                c.result = self.parse_response(connection, c.args[0], **c.options)
            except RedisError:
                c.result = sys.exc_info()[1]

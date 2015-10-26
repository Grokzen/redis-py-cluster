# -*- coding: utf-8 -*-

# python std lib
import random
import sys
import time
import threading

# rediscluster imports
from .client import StrictRedisCluster
from .connection import by_node_context
from .exceptions import (
    RedisClusterException, AskError, MovedError, ClusterDownError,
)
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
                 use_threads=True, reinitialize_steps=None):
        self.command_stack = []
        self.connection_pool = connection_pool
        self.nodes_callbacks = nodes_callbacks
        self.refresh_table_asap = refresh_table_asap
        self.reinitialize_counter = 0
        self.reinitialize_steps = reinitialize_steps or 25
        self.response_callbacks = response_callbacks
        self.result_callbacks = result_callbacks
        self.startup_nodes = startup_nodes if startup_nodes else []
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

        # this is where we store all the responses to the pipeline execute.
        # the actual response is a list, not a dict, but because we may be getting
        # the responses for commands out of order or sometimes retrying them it is important
        # that we have a way to key the responses by the order they came in so that we can return
        # the responses as if we did them sequentially.
        response = {}

        # `attempt` corresponds to the sequence number of commands still left to process or retry.
        # initially this corresponds exactly to the number of commands we need to run, and if all goes
        # well, that's where it'll end. Everything will be attempted once, and we end up with an empty
        # array of commands left to process. But if we need to retry, `attempt` gets repopulated with
        # the sequence number of the command that is being retried.
        attempt = xrange(0, len(stack)) if stack else []  # noqa

        # there are different types of retries. redis cluster says if it responds with an ASK error,
        # you need to handle it differently than a moved error. And if we hit a connection error, we
        # don't really know what to do for that command so we pick a random other node in the cluster.
        ask_retry = {}
        conn_retry = {}

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
            for i in attempt:
                c = stack[i]
                slot = self._determine_slot(*c[0])

                # normally we just refer to our internal node -> slot table that tells us where a given
                # command should route to.
                # but if we are retrying, the cluster could have told us we were wrong or the node was down.
                # in that case, we have to try something that contradicts our rules.
                if i in ask_retry:
                    node = ask_retry[i]
                elif i in conn_retry:
                    node = conn_retry[i]
                else:
                    if self.refresh_table_asap:  # MOVED
                        node = self.connection_pool.get_master_node_by_slot(slot)
                    else:
                        node = self.connection_pool.get_node_by_slot(slot)

                # little hack to make sure the node name is populated. probably could clean this up.
                self.connection_pool.nodes.set_node_name(node)

                # now that we know the name of the node ( it's just a string in the form of host:port )
                # we can build a list of commands for each node.
                node_name = node['name']
                nodes[node_name] = node
                node_commands.setdefault(node_name, {})
                node_commands[node_name][i] = c

            # Get one connection at a time from the pool and basiccly copy the logic from
            #  _execute_pipeline() below and do what a normal pipeline does.

            # now that we've split out the commands by the node we plan to send them to,
            # we can reset the commands we'll attempt next time around back to nothing.
            # when we process the response, any commands that need to be retried because of
            # connection errors, MOVED errors, or ASKING errors will be dumped into here.
            # most of the time this array will just stay empty.
            attempt = []

            # only use threads when it makes sense performance-wise to do so.
            # if you are doing an ask_retry, explicitly disable it.
            # makes it easier to define the logic of how to do the ASKING command,
            # and in practice, the server will only be moving one slot at a time,
            # so there will only be one server that will be recieving these ASKING retries
            # anyway.
            if self.use_threads and not ask_retry and len(node_commands) > 1:

                # for each node we query, we need to have one worker.
                # that way all pipelined commands are issued in parallel.
                # this could be a problem if you have hundreds of nodes in your cluster.
                # We should really refactor this to be a thread pool of workers, and allocate up to a
                # certain max number of threads.
                workers = dict()

                # allocate all of the redis connections from the connection pool.
                # each connection gets passed into its own thread so it can query each node in paralle.
                connections = {node_name: self.connection_pool.get_connection_by_node(nodes[node_name])
                                   for node_name in node_commands}

                # iterate through each set of commands and pass them into a worker thread so
                # it can be executed in it's own socket connection from the redis connection pool
                # in parallel.
                try:

                    for node_name in node_commands:
                        node = nodes[node_name]
                        # build the list of commands to be passed to a particular node.
                        # we have to do this on each attempt, because the cluster may respond to us
                        # that a command for a given slot actually should be routed to a different node.
                        cmds = [node_commands[node_name][i] for i in sorted(node_commands[node_name].keys())]

                        # pass all the commands bound for a particular node into a thread worker object
                        # along with the redis connection needed to run the commands and parse the response.
                        workers[node_name] = ThreadedPipelineExecute(
                            execute=self._execute_pipeline,
                            conn=connections[node_name],
                            cmds=cmds)

                        workers[node_name].start()

                    # now that all the queries are running against all the nodes,
                    # wait for all of them to come back so we can parse the responses.
                    for node_name, worker in workers.items():
                        worker.join()

                        # if the worker hit an exception this is really bad.
                        # that means something completely unexpected happened.
                        # we have to assume the worst and assume that all the calls against
                        # that particular node in the cluster failed and will need to be retried.
                        # maybe that isn't a safe assumption?
                        if worker.exception:
                            for i in node_commands[node_name].keys():
                                response[i] = worker.exception
                        else:
                            # we got a valid response back from redis.
                            # map each response based on the sequence of the original request stack.
                            # some of these responses may represent redis connection or ask errors etc.
                            for i, v in zip(sorted(node_commands[node_name].keys()), worker.value):
                                response[i] = v


                finally:
                    # don't need our threads anymore.
                    # explicitly remove them from the current namespace so they can be garbage collected.
                    del workers

                    # release all of the redis connections we allocated earlier back into the connection pool.
                    for conn in connections.values():
                        self.connection_pool.release(conn)
                    del connections
            else:
                # if we got here, it's because threading is disabled explicitly, or
                # all the commands map to a single node so we don't need to use different threads to
                # issue commands in parallel.

                # first, we need to keep track of all the commands and what responses they map to.
                # this is because we need to interject ASKING commands into the mix. I thought of a little
                # hack to map these responses back to None instead of the integer sequence id that was the
                # position number of the command issued in the stack of command requests at the point pipeline
                # execute was issued.
                track_cmds = {}

                # send the commands in sequence.
                for node_name in node_commands:
                    node = nodes[node_name]
                    cmds = []
                    track_cmds[node_name] = []

                    # we've got the commands we need to run for each node,
                    # sort them to make sure that they are executed in the same order
                    # they came in on the stack otherwise it changes the logic.
                    # we make no guarantees about the order of execution of the commands run
                    # except that we are sure we will always process the commands for a given key
                    # in a sequential order. If we get an error from the server about a given key,
                    # that will apply the same for all commands on that key (MOVED, ASKING, etc)
                    # so we will be resending all of the commands for that key to a new node.
                    for i in sorted(node_commands[node_name].keys()):
                        if i in ask_retry:
                            # put in our fake stub placeholder for the response.
                            track_cmds[node_name].append(None)
                            cmds.append((['ASKING'], {}))

                        # keep track of the sequence number and the mapping of actual commands
                        # sent to the node. (ASKING SCREWS EVERYTHING UP!!!!!)
                        track_cmds[node_name].append(i)
                        cmds.append(node_commands[node_name][i])

                    # allocate a connection from the connection pool and send the commands for each node
                    # as a packed single network request. Since we aren't using threads here, we are
                    # only able to send each request sequentially and block, waiting for the response.
                    # After we get the response to one connection, we move on to the next.
                    with by_node_context(self.connection_pool, node) as connection:
                        result = zip(
                            track_cmds[node_name],
                            self._execute_pipeline(connection, cmds, False))

                        # map the response from the connection to the commands we were running.
                        for i, v in result:

                            # remember None is a shim value used above as a placeholder for the ASKING
                            # command. That response is just `OK` and we don't care about that.
                            # throw it away.
                            # Map the response here to the original sequence of commands in the stack
                            # sent to pipeline.
                            if i is not None:
                                response[i] = v

            ask_retry = {}
            conn_retry = {}

            # now that we have tried to execute all the commands let's see what we have left.
            for i, v in response.items():
                # if the response isn't an exception it is a valid response from the node
                # we're all done with that command, YAY!
                # if we move beyond this point, we've run into problems and we need to retry the command.
                if not isinstance(v, Exception):
                    continue

                # connection errors are tricky because most likely we routed to the right node but it is
                # down. In that case, the best we can do is randomly try another node in the cluster
                # and hope that it tells us to try that node again with a MOVED error or tells us the new
                # master.
                if isinstance(v, ConnectionError):
                    conn_retry[i] = random.choice(self.startup_nodes)
                    attempt.append(i)

                    # if we are stuck in a retry loop, slow things down a bit to give the failover
                    # a chance of actually happening.
                    if ttl < self.RedisClusterRequestTTL / 2:
                        time.sleep(0.1)
                    continue

                # If cluster is down it should be raised and bubble up to
                # utils.clusterdown_wrapper()
                if isinstance(v, ClusterDownError):
                    self.connection_pool.disconnect()
                    self.connection_pool.reset()
                    self.refresh_table_asap = True

                    raise v

                # A MOVED response from the cluster means that somehow we were misinformed about which node
                # a given key slot maps to. This can happen during cluster resharding, during master-slave
                # failover, or if we got a connection error and were forced to re-attempt the command against a
                # random node.
                if isinstance(v, MovedError):
                    # Do not perform full cluster refresh on every MOVED error
                    self.reinitialize_counter += 1

                    if self.reinitialize_counter % self.reinitialize_steps == 0:
                        self.refresh_table_asap = True

                    node = self.connection_pool.nodes.set_node(v.host, v.port, server_type='master')
                    self.connection_pool.nodes.slots[v.slot_id][0] = node
                    attempt.append(i)
                    self._fail_on_redirect(allow_redirections)

                # an ASK error from the server means that only this specific command needs to be tried against
                # a different server (not every key in the slot). This happens only during cluster re-sharding
                # and is a major pain in the ass. For it to work correctly, we have to resend the command to
                # the new node but only after first sending an ASKING command immediately beforehand.
                elif isinstance(v, AskError):
                    node = self.connection_pool.nodes.set_node(v.host, v.port, server_type='master')
                    ask_retry[i] = node
                    attempt.append(i)
                    self._fail_on_redirect(allow_redirections)

        # YAY! we made it out of the attempt loop.
        # turn the response back into a simple flat array that corresponds
        # to the sequence of commands issued in the stack in pipeline.execute()
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


class ThreadedPipelineExecute(threading.Thread):
    """
    Threaded pipeline execution.
    release the connection back into the pool after executing.
    """

    def __init__(self, execute, conn, cmds):
        threading.Thread.__init__(self)
        self.execute = execute
        self.conn = conn
        self.cmds = cmds
        self.exception = None
        self.value = None

    def run(self):
        try:
            self.value = self.execute(self.conn, self.cmds, False)
        except Exception as e:
            self.exception = e

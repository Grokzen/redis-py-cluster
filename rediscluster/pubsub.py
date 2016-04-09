# -*- coding: utf-8 -*-

# 3rd party imports
from redis.client import PubSub


class ClusterPubSub(PubSub):
    """
    Wrapper for PubSub class.
    """

    def __init__(self, *args, **kwargs):
        super(ClusterPubSub, self).__init__(*args, **kwargs)

    def execute_command(self, *args, **kwargs):
        """
        Execute a publish/subscribe command.

        Taken code from redis-py and tweak to make it work within a cluster.
        """
        # NOTE: don't parse the response in this function -- it could pull a
        # legitimate message off the stack if the connection is already
        # subscribed to one or more channels

        if self.connection is None:
            self.connection = self.connection_pool.get_connection(
                'pubsub',
                self.shard_hint,
                channel=args[1],
            )
            # register a callback that re-subscribes to any channels we
            # were listening to when we were disconnected
            self.connection.register_connect_callback(self.on_connect)
        connection = self.connection
        self._execute(connection, connection.send_command, *args)

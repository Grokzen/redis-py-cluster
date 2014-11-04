# -*- coding: utf-8 -*-

# 3rd party imports
from redis.client import PubSub


class ClusterPubSub(PubSub):
    """
    # TODO: Write
    """

    def __init__(self, *args, **kwargs):
        super(ClusterPubSub, self).__init__(*args, **kwargs)

Setup client logging
####################

To setup logging for debugging inside the client during development you can add this as an example to your own code to enable `DEBUG` logging when using the library.

.. code-block:: python

	import logging

	from rediscluster import RedisCluster

	logging.basicConfig()
	logger = logging.getLogger('rediscluster')
	logger.setLevel(logging.DEBUG)
	logger.propergate = True

Note that this logging is not reccommended to be used inside production as it can cause a performance drain and a slowdown of your client.

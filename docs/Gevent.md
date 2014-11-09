## Gevent Support
Redis cluster optionally supports parallel execution of pipelined commands to reduce latency of pipelined requests via gevent. 

### Rationale
When pipelining a bunch of commands to the cluster, many of the commands may be routed to different nodes in the cluster. The client-server design in redis-cluster dictates that the client communicates directly with each node in the cluster rather than treating each node as a homogenous group. 

The advantage to this design is that a smart client can communicate with the cluster with the same latency characteristics as it might communicate with a single-instance redis cluster. But only if the client can communicate with each node in parallel. 

When issuing only a single command, there is only one network round trip to be made. But what if you issue 100 pipelined commands? In a single-instance redis configuration, you still only need to make one network hop. The commands are packed into a single request and the server responds with all the data for those requests in a single response. But with redis cluster, those keys could be spread out over many different nodes. 

The client is responsible for figuring out which commands map to which nodes. Let's say for example that your 100 pipelined commands need to route to 3 different nodes? The first thing the client does is break out the commands that go to each node, so it only has 3 network requests to make instead of 100. 

That's pretty good. But we are still issuing those 3 network requests in serial order. The code loops through each node and issues a request, then gets the response, then issues the next one. We could improve the situation with python threads, making each request in parallel over the network. Now we are only as slow as the slowest single request. But python offers something even more lightweight and efficient than threads to perform tasks in parallel: GEVENT.

You can read up more about gevent here: http://www.gevent.org/

We may offer threaded parallel execution in the future as a fallback option if you are unable or unwilling to install gevent. Let us know if that is important to you. IMHO, gevent works great and is a superior choice. There is no gevent support in python3 yet, but there has been some efforts to get it working. Google for more info. :-) Python3 may be a good reason for us to do threaded support fallback or some other option. Haven't decided yet.


### How to install gevent
 To install gevent you can usually just do:

```
pip install gevent
```

### Configuration

If you have gevent installed, redis-py-cluster automatically detects and enables it for pipelined requests. Just use it.

:-)

redis-py-cluster automatically detects if you've installed gevent and automatically enables it.





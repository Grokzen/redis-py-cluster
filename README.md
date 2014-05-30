# redis-py-cluster

Python cluster client for the official cluster support targeted for redis 3.0

This project is a port to python based on the redis-rb-cluster implementation done by antirez.

The original source can be found at https://github.com/antirez/redis-rb-cluster



## Dependencies

- redis (Python client - https://github.com/andymccurdy/redis-py - Install [pip install redis])
- Cluster enabled redis server (Download the branch that is version 2.9.9+ and that will be 3.0.0 in the future. Build redis and setup a cluster with n machines. Redis can be found at https://github.com/antirez/redis) (Or use the docker image to create a new cluster)



## Implemented commands

- set
- get
- smembers
- srem
- delete
- sadd
- publish
- hset
- hget
- hdel
- hexists
- type
- exists
- rename (NYI)
- renamex (NYI)



## How to setup a cluster manually

 - This video will describe how to setup and use a redis cluster: http://vimeo.com/63672368 (This video is old so look at instructions in Redis cluster tutorial link below)
 - Redis cluster tutorial: http://redis.io/topics/cluster-tutorial
 - Redis cluster specs: http://redis.io/topics/cluster-spect



## Python support

Current python support is

- 2.6   (Not yet tested)
- 2.7.5 (Working)
- 3.1   (Not yet tested)
- 3.2   (Not yet tested)
- 3.3   (Not yet tested)
- 3.4   (Not yet tested)



## Speed

On my laptop with x2 redis servers in cluster mode and one python process on the same machine i do 50k set/get commands in between 6-8 sec



## Disclaimer

Both this client and Redis Cluster are a work in progress that is not suitable to be used in production environments. This is only my current personal opinion about both projects.



## License

MIT (See LICENSE file)

The license should be the same as redis-py library (https://github.com/andymccurdy/redis-py)

# Limitations and differences with redis-py

There is alot of differences that have to be taken into consideration when using redis cluster mode.

Any method that can operate on multiple keys have to be reimplemented in the client and in some cases that is not possible to do. In general any method that is overriden in RedisCluster have lost the ability of being atomic. 

Pipelines do not work the same way in cluster mode. In 'StrictRedis' it batch all commands so that they can be executed at the same time when requested. But with RedisCluster pipelines will send the command directly to the server when it is called, but it will still store the result internally and return the same data from .execute(). This is done so that the code still behaves like a pipeline and no code will break. Some better solution will be implemented in the future but a true transactional pipeline will not be possible right now.

Alot of methods will behave very different when using RedisCluster. Some methods send the same request to all servers and return the result in another format then 'StrictRedis' do. Some methods is blocked because they do not work / is not implemented / is dangerous to use in cluster mode (like shutdown()).

Some of the commands are only partially supported when using RedisCluster.  The commands ``zinterstore`` and ``zunionstore`` are only supported if all the keys map to the same key slot in the cluster. This can be achieved by namespacing related keys with a prefix followed by a bracketed common key. Example: 

```
r.zunionstore('d{foo}', ['a{foo}', 'b{foo}', 'c{foo}'])
```

This corresponds to how redis behaves in cluster mode. Eventually these commands will likely be more fully supported by implementing the logic in the client library at the expense of atomicity and performance.

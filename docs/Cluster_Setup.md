# How to setup a cluster manually

 - Redis cluster tutorial: http://redis.io/topics/cluster-tutorial
 - Redis cluster specs: http://redis.io/topics/cluster-spec
 - This video will describe how to setup and use a redis cluster: http://vimeo.com/63672368 (This video old and maybe outdated)



# Docker

A fully functional docker image can be found at [Docker-redis-cluster](https://github.com/Grokzen/docker-redis-cluster).

See repo README for detailed instructions how to setup.



# Vagrant

You can also use vagrant to spin up redis cluster in a vm for testing. The vm also provides all the python libraries needed to run the tests.

To use the vm, first install vagrant on your system (Instructions can be found at: http://www.vagrantup.com/).
Navigate to root of this project in your ssh terminal and run these commands:


```
vagrant up && vagrant ssh
```

This will print out a bunch of debugging output as it installs redis-server and all the python libraries.
If all is successful, you will be logged into the vagrant instance at the end.

Once inside the vagrant instance you should be able to do:

```
cd /vagrant && make test
```

This will put you in the root directory of this project from within vagrant and run all of the tests.


# Simple makefile

A simple makefile solution can be found at [travis-redis-cluster](https://github.com/Grokzen/travis-redis-cluster)

See repo README for detailed instructions how to setup.

================
redis-py-cluster
================

Python cluster client for the official cluster support targeted for redis 3.0

This project is based on the redis-rb-cluster implementation done by antirez. The original source can be found at https://github.com/antirez/redis-rb-cluster

What i have done is to port redis-rb-cluster to python.



Python support
==============

Current python support is

 - 2.6.x (Not yet tested)
 - 2.7.3 (Working)
 - 3.1.x (Not yet tested)
 - 3.2.x (Not yet tested)
 - 3.3.x (Not yet tested)
 - 3.4.x (Not yet tested)



Dependencies
============

 - redis (Python client - https://github.com/andymccurdy/redis-py - Install [pip install redis])
 - Cluster enabled redis server (Download the branch that is version 2.9.9+ and that will be 3.0.0 in the future. Build redis and setup a cluster with n machines. Redis can be found at https://github.com/antirez/redis)



How to setup a cluster
======================

This video willdescribe how to setup and use a redis cluster: http://vimeo.com/63672368



Implemented commands
====================

 - set
 - get



Speed
=====

On my laptop with x2 redis servers in cluster mode and one python process on the same machine i do 50k set/get commands in between 6-8 sec



Disclaimer
==========

Both this client and Redis Cluster are a work in progress that is not suitable to be used in production environments.



License
=======

This is done for educational purposes and to test the official cluster support for redis

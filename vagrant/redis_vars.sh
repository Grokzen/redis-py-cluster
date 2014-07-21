#!/usr/bin/env bash

VAGRANT_DIR=/home/vagrant/redis-py-cluster/vagrant
REDIS_VERSION=3.0.0-beta7
REDIS_DOWNLOAD_DIR=/home/vagrant/redis-downloads
REDIS_PACKAGE=$REDIS_VERSION.tar.gz
REDIS_BUILD_DIR=$REDIS_DOWNLOAD_DIR/redis-$REDIS_VERSION
REDIS_DIR=/home/vagrant/redis
REDIS_SUPERVISOR_CONF=/etc/supervisor/conf.d/redis.conf
REDIS_PORTS=$(seq 7000 7005)

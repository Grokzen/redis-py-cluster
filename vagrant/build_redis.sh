#!/usr/bin/env bash

source /home/vagrant/redis-py-cluster/vagrant/redis_vars.sh

pushd /home/vagrant

rm -rf $REDIS_SUPERVISOR_CONF
supervisorctl update


# create a clean directory for redis
rm -rf $REDIS_DIR

# download, unpack and build redis
mkdir -p $REDIS_DOWNLOAD_DIR
cd $REDIS_DOWNLOAD_DIR
rm -f $REDIS_PACKAGE
rm -rf $REDIS_BUILD_DIR
wget https://github.com/antirez/redis/archive/$REDIS_PACKAGE
tar zxvf $REDIS_PACKAGE
cd $REDIS_BUILD_DIR
make

mkdir -p $REDIS_DIR
mkdir -p $REDIS_DIR/bin
cp src/redis-server $REDIS_DIR/bin
cp src/redis-cli $REDIS_DIR/bin
cp src/redis-trib.rb $REDIS_DIR/bin
cp ./redis.conf $REDIS_DIR/redis.conf

for port in $REDIS_PORTS
do
    mkdir -p $REDIS_DIR/$port
done

popd

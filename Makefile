PATH := ./redis-git/src:${PATH}

# CLUSTER REDIS NODES
define REDIS_CLUSTER_NODE1_CONF
daemonize yes
port 7000
cluster-node-timeout 5000
pidfile /tmp/redis_cluster_node1.pid
logfile /tmp/redis_cluster_node1.log
save ""
appendonly no
cluster-enabled yes
cluster-config-file /tmp/redis_cluster_node1.conf
endef

define REDIS_CLUSTER_NODE2_CONF
daemonize yes
port 7001
cluster-node-timeout 5000
pidfile /tmp/redis_cluster_node2.pid
logfile /tmp/redis_cluster_node2.log
save ""
appendonly no
cluster-enabled yes
cluster-config-file /tmp/redis_cluster_node2.conf
endef

define REDIS_CLUSTER_NODE3_CONF
daemonize yes
port 7002
cluster-node-timeout 5000
pidfile /tmp/redis_cluster_node3.pid
logfile /tmp/redis_cluster_node3.log
save ""
appendonly no
cluster-enabled yes
cluster-config-file /tmp/redis_cluster_node3.conf
endef

define REDIS_CLUSTER_NODE4_CONF
daemonize yes
port 7003
cluster-node-timeout 5000
pidfile /tmp/redis_cluster_node4.pid
logfile /tmp/redis_cluster_node4.log
save ""
appendonly no
cluster-enabled yes
cluster-config-file /tmp/redis_cluster_node4.conf
endef

define REDIS_CLUSTER_NODE5_CONF
daemonize yes
port 7004
cluster-node-timeout 5000
pidfile /tmp/redis_cluster_node5.pid
logfile /tmp/redis_cluster_node5.log
save ""
appendonly no
cluster-enabled yes
cluster-config-file /tmp/redis_cluster_node5.conf
endef

define REDIS_CLUSTER_NODE6_CONF
daemonize yes
port 7005
cluster-node-timeout 5000
pidfile /tmp/redis_cluster_node6.pid
logfile /tmp/redis_cluster_node6.log
save ""
appendonly no
cluster-enabled yes
cluster-config-file /tmp/redis_cluster_node6.conf
endef

define REDIS_CLUSTER_NODE7_CONF
daemonize yes
port 7006
cluster-node-timeout 5000
pidfile /tmp/redis_cluster_node7.pid
logfile /tmp/redis_cluster_node7.log
save ""
appendonly no
cluster-enabled yes
cluster-config-file /tmp/redis_cluster_node7.conf
endef

define REDIS_CLUSTER_NODE8_CONF
daemonize yes
port 7007
cluster-node-timeout 5000
pidfile /tmp/redis_cluster_node8.pid
logfile /tmp/redis_cluster_node8.log
save ""
appendonly no
cluster-enabled yes
cluster-config-file /tmp/redis_cluster_node8.conf
endef

ifndef REDIS_TRIB_RB
	REDIS_TRIB_RB=redis-git/src/redis-trib.rb
endif

export REDIS_CLUSTER_NODE1_CONF
export REDIS_CLUSTER_NODE2_CONF
export REDIS_CLUSTER_NODE3_CONF
export REDIS_CLUSTER_NODE4_CONF
export REDIS_CLUSTER_NODE5_CONF
export REDIS_CLUSTER_NODE6_CONF
export REDIS_CLUSTER_NODE7_CONF
export REDIS_CLUSTER_NODE8_CONF

help:
	@echo "Please use 'make <target>' where <target> is one of"
	@echo "  clean           remove temporary files created by build tools"
	@echo "  cleanmeta       removes all META-* and egg-info/ files created by build tools"	
	@echo "  cleancov        remove all files related to coverage reports"
	@echo "  cleanall        all the above + tmp files from development tools"
	@echo "  test            run test suite"
	@echo "  sdist           make a source distribution"
	@echo "  bdist           make an egg distribution"
	@echo "  install         install package"
	@echo "  benchmark       runs all benchmarks. assumes nodes running on port 7001 and 7007"
	@echo " *** CI Commands ***"
	@echo "  start           starts a test redis cluster"
	@echo "  stop            stop all started redis nodes (Started via 'make start' only affected)"
	@echo "  cleanup         cleanup files after running a test cluster"
	@echo "  test            starts/activates the test cluster nodes and runs tox test"
	@echo "  tox             run all tox environments and combine coverage report after"
	@echo "  redis-install  checkout latest redis commit --> build --> install ruby dependencies"

clean:
	-rm -f MANIFEST
	-rm -rf dist/
	-rm -rf build/

cleancov:
	-rm -rf htmlcov/
	-coverage combine
	-coverage erase

cleanmeta:
	-rm -rf redis_py_cluster.egg-info/

cleanall: clean cleancov cleanmeta
	-find . -type f -name "*~" -exec rm -f "{}" \;
	-find . -type f -name "*.orig" -exec rm -f "{}" \;
	-find . -type f -name "*.rej" -exec rm -f "{}" \;
	-find . -type f -name "*.pyc" -exec rm -f "{}" \;
	-find . -type f -name "*.parse-index" -exec rm -f "{}" \;

sdist: cleanmeta
	python setup.py sdist

bdist: cleanmeta
	python setup.py bdist_egg

install:
	python setup.py install

start: cleanup
	echo "$$REDIS_CLUSTER_NODE1_CONF" | redis-server -
	echo "$$REDIS_CLUSTER_NODE2_CONF" | redis-server -
	echo "$$REDIS_CLUSTER_NODE3_CONF" | redis-server -
	echo "$$REDIS_CLUSTER_NODE4_CONF" | redis-server -
	echo "$$REDIS_CLUSTER_NODE5_CONF" | redis-server -
	echo "$$REDIS_CLUSTER_NODE6_CONF" | redis-server -
	echo "$$REDIS_CLUSTER_NODE7_CONF" | redis-server -
	echo "$$REDIS_CLUSTER_NODE8_CONF" | redis-server -
	sleep 5
	echo "yes" | ruby $(REDIS_TRIB_RB) create --replicas 1 127.0.0.1:7000 127.0.0.1:7001 127.0.0.1:7002 127.0.0.1:7003 127.0.0.1:7004 127.0.0.1:7005
	sleep 5

cleanup:
	- rm -vf /tmp/redis_cluster_node*.conf 2>/dev/null
	- rm dump.rdb appendonly.aof - 2>/dev/null

stop:
	kill `cat /tmp/redis_cluster_node1.pid` || true
	kill `cat /tmp/redis_cluster_node2.pid` || true
	kill `cat /tmp/redis_cluster_node3.pid` || true
	kill `cat /tmp/redis_cluster_node4.pid` || true
	kill `cat /tmp/redis_cluster_node5.pid` || true
	kill `cat /tmp/redis_cluster_node6.pid` || true
	kill `cat /tmp/redis_cluster_node7.pid` || true
	kill `cat /tmp/redis_cluster_node8.pid` || true
	rm -f /tmp/redis_cluster_node1.conf
	rm -f /tmp/redis_cluster_node2.conf
	rm -f /tmp/redis_cluster_node3.conf
	rm -f /tmp/redis_cluster_node4.conf
	rm -f /tmp/redis_cluster_node5.conf
	rm -f /tmp/redis_cluster_node6.conf
	rm -f /tmp/redis_cluster_node7.conf
	rm -f /tmp/redis_cluster_node8.conf

test:
	make start
	make tox
	make stop

tox:
	coverage erase
	tox
	coverage combine
	coverage report

redis-install:
	[ ! -e redis-git ] && git clone --depth 1 https://github.com/antirez/redis.git redis-git || true
	make -C redis-git -j4
	gem install redis
	sleep 3

benchmark:
	@echo ""
	@echo " -- Running Simple benchmark with StrictRedis lib and non cluster server --"
	python benchmarks/simple.py --port 7007 --timeit --nocluster
	@echo ""
	@echo " -- Running Simple benchmark with RedisCluster lib and cluster server --"
	python benchmarks/simple.py --port 7001 --timeit

.PHONY: test

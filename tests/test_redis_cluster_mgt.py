# -*- coding: utf-8 -*-

class TestRedisClusterMgt(object):

    def test_info(self, rcm):
        info = rcm.info()        
        assert 'cluster_state' in info

    def test_slots(self, rcm):
        slots = rcm.slots()
        assert 'master' in slots
        assert 'slave' in slots

        master_slots = slots['master']
        for host, slots in master_slots.iteritems():        
            s = slots[0]
            # node can have multiple slots
            # as a result, the format is [[1, 2], [3, 4]]
            assert isinstance(s, list) 
            assert len(s) == 2

    def test_nodes(self, rcm):
        nodes = rcm.nodes()
        for host, info in nodes.iteritems():
            assert 'role' in info
            assert 'slots' in info

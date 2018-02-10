
import sys, os
from scapy.all import *
import simpy

class StdMetadata(object):
    def __init__(self, pkt_len, src_port, dst_port, ranks, leaf_node):
        self.pkt_len = pkt_len
        self.src_port = src_port
        self.dst_port = dst_port
        self.ranks = ranks
        self.leaf_node = leaf_node

    def __str__(self):
        return '{{ pkt_len: {}, src_port: {:08b}, dst_port: {:08b}, ranks: {}, leaf_node: {}}}'.format(self.pkt_len, self.src_port, self.dst_port, self.ranks, self.leaf_node)

def pad_pkt(pkt, size):
    if len(pkt) >= size:
        return pkt
    else:
        return pkt / ('\x00'*(size - len(pkt)))

class HW_sim_object(object):
    def __init__(self, env, period):
        self.env = env
        self.period = period
        self.sim_done = False

    def clock(self):
        yield self.env.timeout(self.period)

    def wait_clock(self):
        return self.env.process(self.clock())


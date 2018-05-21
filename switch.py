
import simpy
from hwsim_utils import *
from p4_ingress import *
from scheduling_tree import *
from p4_egress import *

import json
PCAP_FILE = 'data/pkts.pcap'
RANK_FILE = 'data/ranks.json'

class Switch(HW_sim_object):
    def __init__(self, env, period, ready_out_pipe, pkt_in_pipe, pkt_out_pipe, start_dequeue_pipe, sched_tree_shape, sched_alg, istate=None, sched_node_size=None):
        super(Switch, self).__init__(env, period)
        self.ready_out_pipe = ready_out_pipe
        self.pkt_in_pipe = pkt_in_pipe
        self.pkt_out_pipe = pkt_out_pipe
        self.start_dequeue_pipe = start_dequeue_pipe

        ingress_tm_ready_pipe = simpy.Store(env)
        ingress_tm_pkt_pipe = simpy.Store(env)
        tm_egress_ready_pipe = simpy.Store(env)
        tm_egress_pkt_pipe = simpy.Store(env)
        ingress_egress_pipe = simpy.Store(env)

        if sched_alg == "Invert_pkts":
            self.global_state = None
        elif sched_alg == "STFQ":
            self.global_state = STFQ_global_state()
        elif sched_alg == "HSTFQ":
            self.global_state = HSTFQ_global_state()
        elif sched_alg == "MinRate":
            self.global_state = None
        elif sched_alg == "RR":
            self.global_state = None
        elif sched_alg == "WRR":
            self.global_state = None
        elif sched_alg == "Strict":
            self.global_state = None

        self.ingress = IngressPipe(env, period, ingress_tm_ready_pipe, self.pkt_in_pipe, ingress_tm_pkt_pipe, self.global_state, sched_alg, istate)
        self.tm = Scheduling_tree(env, period, ingress_tm_ready_pipe, tm_egress_ready_pipe, ingress_tm_pkt_pipe, tm_egress_pkt_pipe, sched_tree_shape, max_node_size=sched_node_size)
        self.egress = EgressPipe(env, period, tm_egress_ready_pipe, self.ready_out_pipe, tm_egress_pkt_pipe, self.pkt_out_pipe, self.start_dequeue_pipe, self.global_state, sched_alg)

    def cleanup_switch(self):
        self.ingress.sim_done = True
        self.egress.sim_done = True
        self.tm.sim_done = True
        for node in self.tm.nodes.values():
            node.sim_done = True
        yield self.wait_clock()

        # record the recorded pkts and ranks
        wrpcap(PCAP_FILE, self.ingress.pkts)
        with open(RANK_FILE, 'w') as f:
            json.dump(self.ingress.ranks, f)


class STFQ_global_state(object):
    def __init__(self):
        self.virtual_time = 0

class HSTFQ_global_state(object):
    def __init__(self):
        self.flow_virtual_time = [0, 0]
        self.class_virtual_time = 0





import simpy
from hwsim_utils import *
from p4_ingress import *
from scheduling_tree import *
from p4_egress import *


class Switch(HW_sim_object):
    def __init__(self, env, period, ready_in_pipe, ready_out_pipe, pkt_in_pipe, pkt_out_pipe, start_dequeue_pipe, sched_tree_shape):
        super(Switch, self).__init__(env, period)
        self.ready_in_pipe = ready_in_pipe
        self.ready_out_pipe = ready_out_pipe
        self.pkt_in_pipe = pkt_in_pipe
        self.pkt_out_pipe = pkt_out_pipe
        self.start_dequeue_pipe = start_dequeue_pipe

        ingress_tm_ready_pipe = simpy.Store(env)
        ingress_tm_pkt_pipe = simpy.Store(env)
        tm_egress_ready_pipe = simpy.Store(env)
        tm_egress_pkt_pipe = simpy.Store(env)
        ingress_egress_pipe = simpy.Store(env)

        self.ingress = IngressPipe(env, period, self.ready_in_pipe, ingress_tm_ready_pipe, self.pkt_in_pipe, ingress_tm_pkt_pipe)
        self.tm = Scheduling_tree(env, period, ingress_tm_ready_pipe, tm_egress_ready_pipe, ingress_tm_pkt_pipe, tm_egress_pkt_pipe, sched_tree_shape)
        self.egress = EgressPipe(env, period, tm_egress_ready_pipe, self.ready_out_pipe, tm_egress_pkt_pipe, self.pkt_out_pipe, self.start_dequeue_pipe)

    def cleanup_sim(self):
        self.ingress.sim_done = True
        self.egress.sim_done = True
        self.tm.sim_done = True
        for node in self.tm.nodes.values():
            node.sim_done = True
        yield self.wait_clock()

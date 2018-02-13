
import simpy
from hwsim_utils import *

class IngressPipe(HW_sim_object):
    def __init__(self, env, period, ready_out_pipe, pkt_in_pipe, pkt_out_pipe, global_state, sched_alg):
        super(IngressPipe, self).__init__(env, period)
        self.ready_out_pipe = ready_out_pipe
        self.pkt_in_pipe = pkt_in_pipe
        self.pkt_out_pipe = pkt_out_pipe

        self.gstate = global_state
        self.sched_alg = sched_alg

        if sched_alg == "Invert_pkts":
            self.istate = InvPktsIngressState()
        elif sched_alg == "STFQ":
            self.istate = STFQIngressState()

        # register processes for simulation
        self.run()

    def run(self):
        self.env.process(self.process_pkts())

    def process_pkts(self):
        """
        This is the Ingress P4 pipeline that is responsible for computing the rank values
        """
        while not self.sim_done:
            # wait for metadata and pkt to arrive
            (meta, pkt) = yield self.pkt_in_pipe.get()

            # This is where the scheduling algorithm goes
            if self.sched_alg == "Invert_pkts":
                yield self.env.process(self.invert_pkts(meta, pkt))
            elif self.sched_alg == "STFQ":
                yield self.env.process(self.STFQ(meta, pkt))

            # wait until the scheduling_tree is ready to receive
            yield self.ready_out_pipe.get()
            # write metadata and pkt out
            self.pkt_out_pipe.put((meta, pkt))

    def invert_pkts(self, meta, pkt):
        """
        Scheduling algorithm to invert the order of incoming pkts (rank is strictly decreasing)
        scheduling tree shape is assumed to be:
          {0: []}
        """
        max_rank = 100
        meta.ranks[0] = max_rank - self.istate.pkt_cnt
        meta.leaf_node = 0
        self.istate.pkt_cnt += 1
        yield self.wait_clock()

    def STFQ(self, meta, pkt):
        """
        Start Time Fair Queueing (STFQ) - approximation of fair queueing
        """
        # flowID is 5-tuple
        flowID = (pkt[IP].proto, pkt[IP].src, pkt[IP].dst, pkt.sport, pkt.dport)
        self.istate.weights[flowID] = 1 # temporary
        if flowID in self.istate.last_finish.keys():
            start = max(self.gstate.virtual_time, self.istate.last_finish[flowID])
        else:
            start = self.gstate.virtual_time
        self.istate.last_finish[flowID] = start + meta.pkt_len / self.istate.weights[flowID]
        meta.ranks[0] = start
        meta.leaf_node = 0
        meta.sched_meta.start = start
        yield self.wait_clock()

class InvPktsIngressState(object):
    def __init__(self):
        self.pkt_cnt = 0


class STFQIngressState(object):
    def __init__(self):
        # state for STFQ
        #  last_finish: maps flowID to virtual finish time of previous pkt in flow
        self.last_finish = {}
        #  weights: maps flowID to flow weight 
        self.weights = {}

class STFQMeta(object):
    def __init__(self):
        self.start = 0

    def __str__(self):
        return 'start = {}'.format(self.start)


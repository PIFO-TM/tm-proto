
import simpy
from hwsim_utils import *

class IngressPipe(HW_sim_object):
    def __init__(self, env, period, ready_out_pipe, pkt_in_pipe, pkt_out_pipe, global_state, sched_alg, istate=None):
        super(IngressPipe, self).__init__(env, period)
        self.ready_out_pipe = ready_out_pipe
        self.pkt_in_pipe = pkt_in_pipe
        self.pkt_out_pipe = pkt_out_pipe

        self.gstate = global_state
        self.sched_alg = sched_alg

        self.pkts = []
        self.ranks = []

        if istate is not None:
            self.istate = istate
        elif sched_alg == "Invert_pkts":
            self.istate = InvPktsIngressState()
        elif sched_alg == "STFQ":
            self.istate = STFQIngressState()
        elif sched_alg == "HSTFQ":
            self.istate = HSTFQIngressState()
        elif sched_alg == "MinRate":
            self.istate = MinRateIngressState()
        elif sched_alg == "RR":
            self.istate = RRIngressState()
        elif sched_alg == "WRR":
            self.istate = WRRIngressState()
        elif sched_alg == "Strict":
            self.istate = None 

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
            elif self.sched_alg == "HSTFQ":
                yield self.env.process(self.HSTFQ(meta, pkt))
            elif self.sched_alg == "MinRate":
                yield self.env.process(self.MinRate(meta, pkt))
            elif self.sched_alg == "RR":
                yield self.env.process(self.RR(meta, pkt))
            elif self.sched_alg == "WRR":
                yield self.env.process(self.WRR(meta, pkt))
            elif self.sched_alg == "Strict":
                yield self.env.process(self.Strict(meta, pkt))

            # record pkts and ranks
            self.pkts.append(pkt)
            self.ranks.append(meta.ranks[0])

            # wait until the scheduling_tree is ready to receive
            yield self.ready_out_pipe.get()
            # write metadata and pkt out
            self.pkt_out_pipe.put((meta, pkt))

        wrpcap(PCAP_FILE, self.pkts)
        with open(RANK_FILE, 'w') as f:
            json.dump(self.ranks, f)

    #####################
    ## Scheduling Algs ##
    #####################

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

    def HSTFQ(self, meta, pkt):
        """
        Hierarchical Start Time Fair Queueing (HSTFQ)
        """
        # flowID is just sport field
        flowID = pkt.sport
        classID = pkt.sport % 2

        # rank computation for leaf node
        if flowID in self.istate.flow_last_finish.keys():
            start = max(self.gstate.flow_virtual_time[classID], self.istate.flow_last_finish[flowID])
        else:
            start = self.gstate.flow_virtual_time[classID]
        self.istate.flow_last_finish[flowID] = start + meta.pkt_len / self.istate.flow_weights[flowID]
        meta.ranks[0] = start
        meta.leaf_node = classID + 1
        meta.sched_meta.flow_start = start

        # rank computation for root node
        if classID in self.istate.class_last_finish.keys():
            start = max(self.gstate.class_virtual_time, self.istate.class_last_finish[classID])
        else:
            start = self.gstate.class_virtual_time
        self.istate.class_last_finish[classID] = start + meta.pkt_len / self.istate.class_weights[classID]
        meta.ranks[1] = start
        meta.sched_meta.class_start = start

        yield self.wait_clock()

    def MinRate(self, meta, pkt):
        """
        Minimum Rate Gaurantees for flows
        """
        BURST_SIZE = 1500 # bytes
        flowID = pkt.sport
        assert(flowID in self.istate.flow_min_rate.keys())
        min_rate = self.istate.flow_min_rate[flowID]

        flow_tb = self.istate.flow_tb
        if flowID not in self.istate.flow_last_time.keys():
            self.istate.flow_last_time[flowID] = self.env.now
        if flowID not in flow_tb.keys():
            flow_tb[flowID] = BURST_SIZE

        # Replenish tokens
        flow_tb[flowID] = flow_tb[flowID] + min_rate * (self.env.now - self.istate.flow_last_time[flowID])
        if (flow_tb[flowID] > BURST_SIZE):
            flow_tb[flowID] = BURST_SIZE

        # Check if we have enough tokens
        if (flow_tb[flowID] > len(pkt)):
            # under min rate
            over_min = 0
            flow_tb[flowID] = flow_tb[flowID] - len(pkt)
        else:
            # over min rate
            over_min = 1

        self.istate.flow_last_time[flowID] = self.env.now
        meta.ranks[0] = self.env.now # FIFO order at the leaf
        meta.ranks[1] = over_min
        meta.leaf_node = over_min + 1

        yield self.wait_clock()

    def RR(self, meta, pkt):
        """
        Round Robin Scheduling
        """
        # flowID is just sport field
        flowID = pkt.sport

        if flowID not in self.istate.flow_last_rank.keys():
            rank = self.istate.max_rank + 1
            self.istate.num_active_flows += 1
        else:
            rank = self.istate.flow_last_rank[flowID] + self.istate.num_active_flows

        self.istate.max_rank = rank
        self.istate.flow_last_rank[flowID] = rank
        meta.ranks[0] = rank
        meta.leaf_node = 0
        yield self.wait_clock()

    def WRR(self, meta, pkt):
        """
        Weighted Round Robin Scheduling
        """
        # flowID is just sport field
        flowID = pkt.sport

        if flowID not in self.istate.flow_last_rank.keys():
            rank = self.istate.max_rank + 1
            self.istate.num_active_flows += 1
            self.istate.flow_cnt[flowID] = 1
        else:
            weight = self.istate.flow_weight[flowID]
            if (self.istate.flow_cnt[flowID] == weight):
                rank = self.istate.flow_last_rank[flowID] + self.istate.num_active_flows
                self.istate.flow_cnt[flowID] = 1
            else:
                rank = self.istate.flow_last_rank[flowID]
                self.istate.flow_cnt[flowID] += 1

        if rank > self.istate.max_rank:
            self.istate.max_rank = rank
        self.istate.flow_last_rank[flowID] = rank
        meta.ranks[0] = rank
        meta.leaf_node = 0
        yield self.wait_clock()

    def Strict(self, meta, pkt):
        """
        Strict Priority Scheduling
        """
        # flowID is just sport field
        flowID = pkt.sport
        rank = flowID
        meta.ranks[0] = rank
        meta.leaf_node = 0
        yield self.wait_clock()

###################
## Ingress State ##
###################

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

class HSTFQIngressState(object):
    def __init__(self, flow_weights={}, class_weights={}):
        #  last_finish: maps flowID and classID to virtual finish time of previous pkt in flow
        self.flow_last_finish = {}
        self.class_last_finish = {}
        #  weights: maps flowID and classID to weights
        self.flow_weights = flow_weights
        self.class_weights = class_weights

class MinRateIngressState(object):
    def __init__(self, flow_min_rate):
        self.flow_min_rate = flow_min_rate
        self.flow_tb = {}
        self.flow_last_time = {}

class RRIngressState(object):
    def __init__(self):
        self.max_rank = 0
        self.flow_last_rank = {}
        self.num_active_flows = 0

class WRRIngressState(object):
    def __init__(self, weights):
        self.max_rank = 0
        self.flow_cnt = {}
        self.flow_last_rank = {}
        self.num_active_flows = 0
        self.flow_weight = weights

##############
## Metadata ##
##############

class STFQMeta(object):
    def __init__(self):
        self.start = 0

    def __str__(self):
        return 'start = {}'.format(self.start)


class HSTFQMeta(object):
    def __init__(self):
        self.flow_start = 0
        self.class_start = 0

    def __str__(self):
        return 'flow_start = {}'.format(self.flow_start)
        return 'class_start = {}'.format(self.class_start)


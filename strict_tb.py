
import simpy
from hwsim_utils import *
from switch import Switch
from switch_tb import Switch_testbench
from stats_utils import StatsGenerator
import matplotlib
import matplotlib.pyplot as plt

CYCLE_LIMIT = 8000
RATE_AVG_INTERVAL = 500 # ns

class Strict_tb(Switch_testbench):
    def __init__(self, env, period):
        super(Strict_tb, self).__init__(env, period)

        self.sched_alg = "Strict"
        self.sched_tree_shape = {0: []}
        sched_node_size = None
        self.switch = Switch(self.env, self.period, self.sw_ready_out_pipe, self.sw_pkt_in_pipe, self.sw_pkt_out_pipe, self.start_dequeue_pipe, self.sched_tree_shape, self.sched_alg, sched_node_size=sched_node_size)

        # start dequeueing immediately
        self.start_dequeue_pipe.put(1)

        # create flows
        rates = [5, 20]
        num_flows = len(rates)
        base_sport = 0
        self.generators = []
        self.pkt_gen_pipes = []
        for i in range(num_flows):
            pipe = simpy.Store(env)
            rate = rates[i] # Gbps
            pkt = Ether()/IP()/TCP(sport=base_sport+i)/('\x00'*10)
            meta = StdMetadata(len(pkt), 0b00000001, 0b00000100, [0], 0, sched_meta=None)
#            pkt_gen = PktGenerator(env, period, pipe, rate, pkt, meta, cycle_limit=5000, burst_size=100, burst_delay=500)
            if i == 0:
                pkt_gen = PktGenerator(env, period, pipe, rate, pkt, meta, cycle_limit=CYCLE_LIMIT, burst_size=200, burst_delay=2000)
            else:
                pkt_gen = PktGenerator(env, period, pipe, rate, pkt, meta, cycle_limit=CYCLE_LIMIT)
            self.generators.append(pkt_gen)
            self.pkt_gen_pipes.append(pipe)

        self.egress_link_rate = 10 # Gbps

        self.arbiter = Arbiter(env, period, self.pkt_gen_pipes, self.sw_pkt_in_pipe)
        self.receiver = PktReceiver(env, period, self.sw_pkt_out_pipe, self.sw_ready_out_pipe, self.egress_link_rate)

        self.env.process(self.wait_complete()) 

    def wait_complete(self):
        # wait for all pkts to be inserted
        for gen in self.generators:
            yield gen.proc

        # wait for receiver to receive all pkts
        timeout_val = 100000 # cycles
        cnt = 0
        while len(self.receiver.pkts) < len(self.arbiter.pkts) and cnt < timeout_val:
            yield self.wait_clock()
            cnt += 1

        yield self.env.process(self.cleanup_switch())
        self.arbiter.sim_done = True
        self.receiver.sim_done = True

        print '# input pkts = {}'.format(len(self.arbiter.pkts))
#        print 'input pkts:'
#        for (t, meta, pkt) in self.arbiter.pkts:
#            print '({}) {}  ||  {}'.format(t, str(meta), pkt.summary())

        print '# output pkts = {}'.format(len(self.receiver.pkts))
#        print 'output pkts:'
        flow_ranks = {}
        for (t, meta, pkt) in self.receiver.pkts:
#            print '@{}: flowID = {}  || rank = {}'.format(t, pkt.sport, meta.ranks[0])
            flowID = pkt.sport
            rank = meta.ranks[0]
            if flowID not in flow_ranks.keys():
                flow_ranks[flowID] = [rank]
            else:
                flow_ranks[flowID].append(rank)

#        for flowID, ranks in flow_ranks.items():
#            print "flowID = {} || ranks = {}".format(flowID, ranks)


def plot_stats(input_pkts, output_pkts, egress_link_rate):
    # convert cycles to ns and remove metadata from pkt_list
    input_pkts = [(tup[0]*5, tup[2]) for tup in input_pkts]
    output_pkts = [(tup[0]*5, tup[2]) for tup in output_pkts]
    print 'input_pkts:  (start, end) = ({} ns, {} ns)'.format(input_pkts[0][0], input_pkts[-1][0])
    print 'output_pkts: (start, end) = ({} ns, {} ns)'.format(output_pkts[0][0], output_pkts[-1][0])
    flowID_tuple = ((IP, 'sport'),)
    print "Calculating Input Rates ..."
    input_stats = StatsGenerator(flowID_tuple, input_pkts, avg_interval=RATE_AVG_INTERVAL)
    print "Calculating Output Rates ..."
    output_stats = StatsGenerator(flowID_tuple, output_pkts, avg_interval=RATE_AVG_INTERVAL)
    # create plots
    fig, axarr = plt.subplots(2)
    plt.sca(axarr[0])
    input_stats.plot_rates('Input Flow Rates', linewidth=3)
    plt.sca(axarr[1])
    output_stats.plot_rates('Output Flow Rates', ymax=egress_link_rate+egress_link_rate*0.5, linewidth=3)

    font = {'family' : 'normal',
            'weight' : 'bold',
            'size'   : 22}
    matplotlib.rc('font', **font)
    plt.show()


def main():
    env = simpy.Environment()
    period = 1
    tb = Strict_tb(env, period)
    env.run()

    plot_stats(tb.arbiter.pkts, tb.receiver.pkts, tb.egress_link_rate)


if __name__ == '__main__':
    main()


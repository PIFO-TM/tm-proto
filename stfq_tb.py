
import simpy
from hwsim_utils import *
from switch import Switch
from switch_tb import Switch_testbench
from p4_ingress import STFQMeta
from stats_utils import StatsGenerator
import matplotlib
import matplotlib.pyplot as plt

class STFQ_tb(Switch_testbench):
    def __init__(self, env, period):
        super(STFQ_tb, self).__init__(env, period)

        self.sched_alg = "STFQ"
        self.sched_tree_shape = {0: []}
        self.switch = Switch(self.env, self.period, self.sw_ready_out_pipe, self.sw_pkt_in_pipe, self.sw_pkt_out_pipe, self.start_dequeue_pipe, self.sched_tree_shape, self.sched_alg)

        # start dequeueing immediately
        self.start_dequeue_pipe.put(1)

        # create flows
        self.num_flows = 4
        base_sport = 100
        self.generators = []
        self.pkt_gen_pipes = []
        for i in range(self.num_flows):
            pipe = simpy.Store(env)
            rate = 10*(i+1) # Gbps
            pkt = Ether()/IP()/TCP(sport=base_sport+i)/('\x00'*10)
            meta = StdMetadata(len(pkt), 0b00000001, 0b00000100, [0], 0, sched_meta=STFQMeta())
            pkt_gen = PktGenerator(env, period, pipe, rate, pkt, meta, pkt_limit=1000)
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
        while len(self.receiver.pkts) < len(self.arbiter.pkts):
            yield self.wait_clock()

        yield self.env.process(self.cleanup_switch())
        self.arbiter.sim_done = True
        self.receiver.sim_done = True

        print '# input pkts = {}'.format(len(self.arbiter.pkts))
#        print 'input pkts:'
#        for (t, meta, pkt) in self.arbiter.pkts:
#            print '({}) {}  ||  {}'.format(t, str(meta), pkt.summary())

        print '# output pkts = {}'.format(len(self.receiver.pkts))
#        print 'output pkts:'
#        for (t, meta, pkt) in self.receiver.pkts:
#            print '({}) {}  ||  {}'.format(t, str(meta), pkt.summary())

def plot_stats(input_pkts, output_pkts, egress_link_rate):
    # convert cycles to ns and remove metadata from pkt_list
    input_pkts = [(tup[0]*5, tup[2]) for tup in input_pkts]
    output_pkts = [(tup[0]*5, tup[2]) for tup in output_pkts]
    print 'input_pkts:  (start, end) = ({} ns, {} ns)'.format(input_pkts[0][0], input_pkts[-1][0])
    print 'output_pkts: (start, end) = ({} ns, {} ns)'.format(output_pkts[0][0], output_pkts[-1][0])
    flowID_tuple = ((IP, 'proto'), (IP, 'src'), (IP, 'dst'), (IP, 'sport'), (IP, 'dport'))
    input_stats = StatsGenerator(flowID_tuple, input_pkts)
    output_stats = StatsGenerator(flowID_tuple, output_pkts)
    # create plots
    plt.figure()
    input_stats.plot_rates('Input Flow Rates')
    plt.figure()
    output_stats.plot_rates('Output Flow Rates', ymax=egress_link_rate)
    plt.show()

def main():
    env = simpy.Environment()
    period = 1
    tb = STFQ_tb(env, period)
    env.run()

    plot_stats(tb.arbiter.pkts, tb.receiver.pkts, tb.egress_link_rate)


if __name__ == '__main__':
    main()


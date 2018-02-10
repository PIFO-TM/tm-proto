
import simpy
from hwsim_utils import *
from switch import Switch
from switch_tb import Switch_testbench

class Invert_pkts_tb(Switch_testbench):
    def __init__(self, env, period):
        super(Invert_pkts_tb, self).__init__(env, period)

        self.sched_tree_shape = {0: []}
        self.switch = Switch(self.env, self.period, self.sw_ready_in_pipe, self.sw_ready_out_pipe, self.sw_pkt_in_pipe, self.sw_pkt_out_pipe, self.start_dequeue_pipe, self.sched_tree_shape)

        self.env.process(self.gen_pkts())
        self.env.process(self.rcv_pkts()) 

    def gen_pkts(self):
        for i in range(10):
            # wait for switch to be ready to receive a pkt
            yield self.sw_ready_in_pipe.get()
            pkt_id = i
            pkt = Ether()/IP(id=pkt_id)/TCP()/'THIS IS A TEST PKT!!'
            ranks = [0]
            leaf_node = 0
            meta = StdMetadata(len(pkt), 0b00000001, 0, ranks, leaf_node)
            self.sw_pkt_in_pipe.put((meta, pkt))
            self.input_pkts.append((self.env.now, meta, pkt))

        for i in range(20):
            yield self.wait_clock()

        self.input_done = True
        # start dequeuing after all pkts have been inserted
        self.start_dequeue_pipe.put(1)

    def rcv_pkts(self):
        # wait for all pkts to be inserted
        while not self.input_done:
            yield self.wait_clock()

        # compute the expected_pkts from the input_pkts
        expected_pkts = []
        for (t, meta, pkt) in self.input_pkts:
            expected_pkts = [(meta, pkt)] + expected_pkts

        # read out the pkts
        rcvd_pkts = []
        done = False
        while not done:
            self.sw_ready_out_pipe.put(1)
            (meta, pkt) = yield self.sw_pkt_out_pipe.get()
            rcvd_pkts.append((meta, pkt))
            if len(rcvd_pkts) == len(expected_pkts):
                done = True

        yield self.env.process(self.reconcile_pkts(expected_pkts, rcvd_pkts))
        yield self.env.process(self.cleanup_sim())

def main():
    env = simpy.Environment()
    period = 1
    tb = Invert_pkts_tb(env, period)
    env.run()


if __name__ == '__main__':
    main()


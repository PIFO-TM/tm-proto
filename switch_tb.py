
import simpy
from hwsim_utils import *
from switch import Switch

class Switch_testbench(HW_sim_object):
    def __init__(self, env, period):
        self.env = env
        self.period = period
        self.sw_ready_out_pipe = simpy.Store(env)
        self.sw_pkt_in_pipe  = simpy.Store(env)
        self.sw_pkt_out_pipe = simpy.Store(env)
        self.start_dequeue_pipe = simpy.Store(env)

        self.input_done = False
        self.input_pkts = []

    def reconcile_pkts(self, expected_pkts, rcvd_pkts):
        for ((exp_meta, exp_pkt), (rcvd_meta, rcvd_pkt), i) in zip(expected_pkts, rcvd_pkts, range(len(rcvd_pkts))):
            if str(exp_meta) != str(rcvd_meta):
                print 'ERROR: exp_meta != rcvd_meta for pkt {}'.format(i)
                print 'exp_meta  = {}'.format(str(exp_meta))
                print 'rcvd_meta = {}'.format(str(rcvd_meta))
            if str(exp_pkt) != str(rcvd_pkt):
                print 'ERROR: exp_pkt != rcvd_pkt for pkt {}'.format(i)
                print 'exp_pkt  = {}'.format(exp_pkt.summary())
                print 'rcvd_pkt = {}'.format(rcvd_pkt.summary())

        yield self.wait_clock()

    def cleanup_switch(self):
        yield self.env.process(self.switch.cleanup_switch())



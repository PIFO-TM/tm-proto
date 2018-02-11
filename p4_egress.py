
import simpy
from hwsim_utils import *

class EgressPipe(HW_sim_object):
    def __init__(self, env, period, ready_in_pipe, ready_out_pipe, pkt_in_pipe, pkt_out_pipe, start_dequeue_pipe, global_state):
        super(EgressPipe, self).__init__(env, period)
        self.ready_in_pipe = ready_in_pipe
        self.ready_out_pipe = ready_out_pipe
        self.pkt_in_pipe = pkt_in_pipe
        self.pkt_out_pipe = pkt_out_pipe
        # this is a pipe from the top level block to tell the egress when to start dequeuing
        self.start_dequeue_pipe = start_dequeue_pipe

        self.global_state = global_state

        # register processes for simulation
        self.run()

    def run(self):
        self.env.process(self.process_pkts())

    def process_pkts(self):
        """
        This is the Egress P4 pipeline that is responsible for processing pkts after scheduling
        """
        # wait for the top level to say that dequeuing may begin
        yield self.start_dequeue_pipe.get()
        while not self.sim_done:
            # wait until the top level is ready to receive before trying to read from tm
            yield self.ready_out_pipe.get()

            self.ready_in_pipe.put(1)
            # wait for metadata and pkt to arrive
            (meta, pkt) = yield self.pkt_in_pipe.get()

            # This is where the post-scheduling algorithm goes
            yield self.env.process(self.post_invert_pkts(meta, pkt))

            # write metadata and pkt out
            self.pkt_out_pipe.put((meta, pkt))

    def post_invert_pkts(self, meta, pkt):
        print 'meta = {}'.format(str(meta))
        print 'pkt_id = {}'.format(pkt[IP].id)
        yield self.wait_clock()














import simpy
from hwsim_utils import *

class EgressPipe(HW_sim_object):
    def __init__(self, env, period, ready_in_pipe, ready_out_pipe, pkt_in_pipe, pkt_out_pipe, start_dequeue_pipe, global_state, sched_alg):
        super(EgressPipe, self).__init__(env, period)
        self.ready_in_pipe = ready_in_pipe
        self.ready_out_pipe = ready_out_pipe
        self.pkt_in_pipe = pkt_in_pipe
        self.pkt_out_pipe = pkt_out_pipe
        # this is a pipe from the top level block to tell the egress when to start dequeuing
        self.start_dequeue_pipe = start_dequeue_pipe

        self.gstate = global_state
        self.sched_alg = sched_alg

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
            if self.sched_alg == "Invert_pkts":
                yield self.env.process(self.invert_pkts_egress(meta, pkt))
            elif self.sched_alg == "STFQ":
                yield self.env.process(self.STFQ_egress(meta, pkt))
            elif self.sched_alg == "HSTFQ":
                # TODO: HSTFQ actually seems to work pretty well without this... why???
                yield self.env.process(self.HSTFQ_egress(meta, pkt)) 

            # write metadata and pkt out
            self.pkt_out_pipe.put((meta, pkt))

    def invert_pkts_egress(self, meta, pkt):
        print 'meta = {}'.format(str(meta))
        print 'pkt_id = {}'.format(pkt[IP].id)
        yield self.wait_clock()

    def STFQ_egress(self, meta, pkt):
        """
        Egress processing for Start Time Fair Queueing
        """
        self.gstate.virtual_time = meta.sched_meta.start
        yield self.wait_clock()

    def HSTFQ_egress(self, meta, pkt):
        """
        Egress processing for Hierarchical Start Time Fair Queueing
        """
        classID = pkt.sport % 2
        self.gstate.flow_virtual_time[classID] = meta.sched_meta.flow_start
        self.gstate.class_virtual_time = meta.sched_meta.class_start
        yield self.wait_clock()







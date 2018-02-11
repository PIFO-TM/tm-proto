
import simpy
from hwsim_utils import HW_sim_object, StdMetadata

class IngressPipe(HW_sim_object):
    def __init__(self, env, period, ready_in_pipe, ready_out_pipe, pkt_in_pipe, pkt_out_pipe, global_state):
        super(IngressPipe, self).__init__(env, period)
        self.ready_in_pipe = ready_in_pipe
        self.ready_out_pipe = ready_out_pipe
        self.pkt_in_pipe = pkt_in_pipe
        self.pkt_out_pipe = pkt_out_pipe

        self.global_state = global_state

        self.pkt_cnt = 0

        # register processes for simulation
        self.run()

    def run(self):
        self.env.process(self.process_pkts())

    def process_pkts(self):
        """
        This is the Ingress P4 pipeline that is responsible for computing the rank values
        """
        while not self.sim_done:
            self.ready_in_pipe.put(1)
            # wait for metadata and pkt to arrive
            (meta, pkt) = yield self.pkt_in_pipe.get()

            # This is where the scheduling algorithm goes
            yield self.env.process(self.invert_pkts(meta, pkt))

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
        meta.ranks[0] = max_rank - self.pkt_cnt
        meta.leaf_node = 0
        self.pkt_cnt += 1
        yield self.wait_clock()









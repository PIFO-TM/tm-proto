
import simpy
from hwsim_utils import HW_sim_object, StdMetadata

class IngressPipe(HW_sim_object):
    def __init__(self, env, period, ready_in_pipe, ready_out_pipe, w_in_pipe, w_out_pipe):
        super(IngressPipe, self).__init__(env, period)
        self.ready_in_pipe = ready_in_pipe
        self.ready_out_pipe = ready_out_pipe
        self.w_in_pipe = w_in_pipe
        self.w_out_pipe = w_out_pipe

        # register processes for simulation
        self.run()

    def run(self):
        self.env.process(self.process_pkts())

    def process_pkts(self):
        """
        This is the Ingress P4 pipeline that is responsible for computing the rank values
        """
        while True:
            # wait for metadata and pkt to arrive
            (meta, pkt) = yield self.w_in_pipe.get()

            # This is where the scheduling algorithm goes


            # wait until the scheduling_tree is ready to receive
            yield self.ready_out_pipe.get()
            # write metadata and pkt out
            self.w_out_pipe.put((meta, pkt))
            self.ready_in_pipe.put(1)


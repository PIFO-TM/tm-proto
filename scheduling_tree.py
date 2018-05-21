
import sys, os
from scapy.all import *
import simpy
from heapq import heappush, heappop, heapify
from hwsim_utils import *

class PIFO(HW_sim_object):
    def __init__(self, env, period, r_in_pipe, r_out_pipe, w_in_pipe, w_out_pipe, write_latency=1, read_latency=1, max_size=None):
        super(PIFO, self).__init__(env, period)
        self.r_in_pipe = r_in_pipe
        self.r_out_pipe = r_out_pipe
        self.w_in_pipe = w_in_pipe
        self.w_out_pipe = w_out_pipe
        self.write_latency = write_latency
        self.read_latency = read_latency
        self.values = []

        self.max_size = max_size
        self.drop_cnt = 0

        # register processes for simulation
        self.run()

    def run(self):
        self.env.process(self.write_sm())
        self.env.process(self.read_sm())

    def write_sm(self):
        """
        State machine to write incomming data into pifo
        """
        while not self.sim_done:
            # wait to receive incoming data
            (rank, data) = yield self.w_in_pipe.get()
            # model write latency
            for i in range(self.write_latency):
                yield self.wait_clock()
            # write pkt and metadata into pifo
            if self.max_size is None or len(self.values) < self.max_size:
                heappush(self.values, (rank, data))
            else:
                heappush(self.values, (rank, data))
                self.values.remove(max(self.values))
                heapify(self.values)
                self.drop_cnt += 1
            # indicate write_completion
            done = 1
            self.w_out_pipe.put(done)    

    def read_sm(self):
        """
        State machine to read data from memory
        """
        while not self.sim_done:
            # wait to receive a read request
            read_req = yield self.r_in_pipe.get()
            # model read latency
            for i in range(self.read_latency):
                yield self.wait_clock()
            # try to read data from pifo
            read_complete = False
            while not read_complete and not self.sim_done:
                if len(self.values) > 0:
                    (rank, data) = heappop(self.values)
                    self.r_out_pipe.put((rank, data))
                    read_complete = True
                else:
                    yield self.wait_clock()

class Scheduling_tree_node(PIFO):
    def __init__(self, env, period, ID, r_in_pipe, r_out_pipe, w_in_pipe, w_out_pipe, children, parent, max_size=None):
        super(Scheduling_tree_node, self).__init__(env, period, r_in_pipe, r_out_pipe, w_in_pipe, w_out_pipe, max_size=max_size)
        self.ID = ID
        self.children = children
        self.parent = parent

    def __str__(self):
        children_strs = []
        for child in self.children:
            children_strs.append(str(child))
        return '[{}, [{}]]'.format(self.ID, ','.join(children_strs))

class Scheduling_tree(HW_sim_object):
    def __init__(self, env, period, ready_in_pipe, ready_out_pipe, pkt_in_pipe, pkt_out_pipe, shape, max_node_size=None):
        """Shape specifies the shape of the scheduling tree:
           e.g. single pifo  --  0
                2-level tree -- {0: [1, 2]}
                3-level tree -- {0: [{1: [3, 4]}, {2: [5, 6]}]}
        """
        super(Scheduling_tree, self).__init__(env, period)
        self.ready_in_pipe = ready_in_pipe
        self.ready_out_pipe = ready_out_pipe
        self.pkt_in_pipe = pkt_in_pipe
        self.pkt_out_pipe = pkt_out_pipe
        self.shape = shape
        self.max_node_size = max_node_size
        # this maps the node ID to the node itself 
        self.nodes = {}
        # tree is a pointer to the root node
        self.tree = self.make_tree(shape, None, max_node_size)

        # register processes for simulation
        self.run()

    def run(self):
        self.env.process(self.write_sm())
        self.env.process(self.read_sm())

    def __str__(self):
        return str(self.tree)

    def make_tree(self, shape, parent, max_node_size):
        """
        Recursive function to make scheduling tree
        """
        r_in_pipe = simpy.Store(self.env)
        r_out_pipe = simpy.Store(self.env)
        w_in_pipe = simpy.Store(self.env)
        w_out_pipe = simpy.Store(self.env)
        if (type(shape) == int):
            # base case
            children = []
            ID = shape
            node = Scheduling_tree_node(self.env, self.period, ID, r_in_pipe, r_out_pipe, w_in_pipe, w_out_pipe, children, parent, max_node_size)
        elif (type(shape) == dict):
            keys = shape.keys()
            vals = shape.values()
            if len(keys) != 1 or type(keys[0]) != int or type(vals[0]) != list:
                # must be exactly one integer key with a list value
                print >> sys.stderr, "ERROR: incorrct format of shape: {}".format(shape)
                sys.exit(1)
            ID = keys[0]
            node = Scheduling_tree_node(self.env, self.period, ID, r_in_pipe, r_out_pipe, w_in_pipe, w_out_pipe, [], parent, max_node_size)
            children = []
            for child in vals[0]:
                child_node = self.make_tree(child, node)
                children.append(child_node)
            node.children = children
        else:
            print >> sys.stderr, "ERROR: incorrct format of shape: {}".format(shape)
            sys.exit(1)
        self.nodes[ID] = node
        return node

    def write_sm(self):
        """
        State machine to enqueue into the scheduling tree
        """
        while not self.sim_done:
            self.ready_in_pipe.put(1) # to indicate ready to receive
            # wait to receive incoming data
            (meta, pkt) = yield self.pkt_in_pipe.get()

            level = 0
            # enqueue the pkt and metadata into the leaf node 
            leaf_rank = meta.ranks[level]
            leaf_node_ptr = meta.leaf_node
            leaf_node = self.nodes[leaf_node_ptr]
            leaf_node.w_in_pipe.put((leaf_rank, (meta, pkt)))
            yield leaf_node.w_out_pipe.get()
            parent = leaf_node.parent
            child_ID = leaf_node.ID
            while parent is not None:
                # enqueue node pointers up to the root
                node = parent
                level += 1
                rank = meta.ranks[level]
                node.w_in_pipe.put((rank, child_ID))
                yield node.w_out_pipe.get()
                parent = node.parent
                child_ID = node.ID

    def read_sm(self):
        """
        State machine to dequeue from the scheduling tree
        """
        while not self.sim_done:
            # wait to receive a read request
            read_req = yield self.ready_out_pipe.get()

            # always remove from the root first
            self.tree.r_in_pipe.put(1)
            (rank, data) = yield self.tree.r_out_pipe.get()
            while type(data) == int:
                # data is a pointer to another node
                node = self.nodes[data]
                node.r_in_pipe.put(1)
                (rank, data) = yield node.r_out_pipe.get()

            try:
                assert(type(data) == tuple)
            except AssertionError as e:
                print >> sys.stderr, "ERROR: invalid type returned from node: {}".format(data)
                sys.exit(1)

            # data is now the metadata and pkt
            self.pkt_out_pipe.put(data)





import sys, os
from scapy.all import *
import matplotlib
import matplotlib.pyplot as plt

#RATE_AVG_INTERVAL = 500000 # ns
RATE_AVG_INTERVAL = 1000 # ns

class StatsGenerator(object):
    def __init__(self, flowID_tuple, pkt_list):
        """
        flowID_tuple: tuple of tuples used to identify a flow in the pkt_list (e.g. ((IP, 'src'), (IP, 'dst')) )
        pkt_list: a list of nanosecond timestamps and scapy pkts with the format: [(t0, pkt0), (t1, pk1), ...]
        """

        self.flowID_tuple = flowID_tuple
        self.flow_pkts = self.parse_pkt_list(pkt_list)
        self.flow_rates = self.calc_flow_rates(self.flow_pkts)

    def extract_flowID(self, pkt):
        flowID = []
        for (layer, field) in self.flowID_tuple:
            try:
                val = pkt[layer].getfieldval(field)
            except IndexError as e1:
                print >> sys.stderr, 'WARNING: layer {} not in pkt: {}'.format(layer.name, pkt.summary())
                return None
            except AttributeError as e2:
                print >> sys.stderr, 'WARNING: field {} not in pkt[{}]: {}'.format(field, layer.name, pkt[layer].summary())
                return None
            flowID.append(val)
        return tuple(flowID)

    def parse_pkt_list(self, pkt_list):
        """
        Read a pkt_list and parse into per-flow pkts
        """
        flow_pkts = {}
        for (t, pkt) in pkt_list:
            flowID = self.extract_flowID(pkt)
            if flowID not in flow_pkts.keys():
                flow_pkts[flowID] = [(t, pkt)]
            else:
                flow_pkts[flowID].append((t,pkt))
        return flow_pkts

    def calc_flow_rates(self, flow_pkts):
        """
        Given dictionary mapping flowIDs to the flow's pkts with nanosecond timestamps, calculate a new
        dictionary mapping flowIDs to the flow's measured rate
        """
        flow_rates = {}
        for flowID, pkts in flow_pkts.items():
            prev_time = pkts[0][0]
            byte_cnt = 0
            flow_rates[flowID] = []
            for (cur_time, pkt) in pkts:
                if cur_time <= prev_time + RATE_AVG_INTERVAL:
                    # increment
                    byte_cnt += len(pkt)
                else:
                    # update
                    interval = cur_time - prev_time # ns
                    rate = (byte_cnt*8.0)/float(interval)  # Gbps
                    avg_time = (cur_time + prev_time)/2.0
                    flow_rates[flowID].append((avg_time, rate))
                    # reset
                    prev_time = cur_time
                    byte_cnt = 0
        return flow_rates


    def plot_rates(self, title, ymax=None, linewidth=1):
        """
        Plots the flow rates
        """
        for flowID, rate_points in self.flow_rates.items(): 
            times = [point[0] for point in rate_points]
            rates = [point[1] for point in rate_points]
            plt.plot(times, rates, label='{}'.format(flowID), linewidth=linewidth)
        plt.xlabel('time (ns)')
        plt.ylabel('rate (Gbps)')
        plt.title(title)
        #plt.legend(loc='lower right')
        plt.legend(loc='upper left')
        if ymax is not None:
            plt.ylim(0, ymax)




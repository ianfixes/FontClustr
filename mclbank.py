import json
import networkx
import numpy
from mcl.mcl_clustering import networkx_mcl
import pprint

# An MCL solver object.
# https://www.cs.ucsb.edu/~xyan/classes/CS595D-2009winter/MCL_Presentation2.pdf
# https://www.cs.umd.edu/class/fall2009/cmsc858l/lecs/Lec12-mcl.pdf
class MCLBank(object):

    # font_info: array of font information dicts
    # distances: 2d array of font distances, indexes align with font_info
    def __init__(self, font_info, distances):
        self.font_names = [f["name"] for f in font_info]
        self.data = dict([(f["name"], {
            "font": f,
            "distance_to": dict([(f2["name"], distances[i][j]) for j, f2 in enumerate(font_info)])
        }) for i, f in enumerate(font_info)])


    def multilevel_cluster(self):
        print "multilevel_cluster"

        # multicluster helper
        def mch(font_names):
            print "mch of", len(font_names), font_names
            distances = numpy.array([self.data[i]["distance_to"][j] for i in font_names for j in font_names if i != j])

            # et for Edge Threshold
            def get_graph(et):
                g = networkx.Graph()
                g.add_nodes_from(font_names)
                edges = [(i, j) for i in font_names for j in font_names if i < j and self.data[i]["distance_to"][j] < et]
                g.add_edges_from(edges)
                return g

            solution = [font_names]  # start with one cluster and try to break it apart
            quantile = 80.0          # we want to start at 40, so double it to start
            while 2.5 < quantile and 1 == len(solution):
                quantile = quantile * 0.5
                threshold = numpy.percentile(distances, quantile)
                g = get_graph(threshold)
                _, solution = networkx_mcl(g) #expand_factor = <expand_factor>,
                                              #inflate_factor = <inflate_factor>,
                                              #max_loop = <max_loop>,
                                              #mult_factor = <mult_factor>)

            if 1 == len(solution.keys()): return solution  # nothing more we can do

            # if a cluster has more than 5 members, recurse down
            return [c if 5 >= len(c) else mch(c) for c in solution]

        # start from the top
        return mch(self.font_names)

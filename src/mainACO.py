import os
import random
import networkx as nx
# from ga import GeneticAlgorithm
from aco_standalone import ACO
import matplotlib.pyplot as plt

DEMAND_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "demand_data.csv")
EDGE_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "edge_data.csv")
NODE_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "node_data.csv")

class NetworkTopology:
    def __init__(self, node_data_path, edge_data_path):
        self.nodes = {}
        self.G = None
        self.node_data_path = node_data_path
        self.edge_data_path = edge_data_path

    def setup_topology(self):
        self.create_nodes_from_file()
        self.build_graph()

    def create_nodes_from_file(self):
        nodes_file = read_file(self.node_data_path)
        for n in nodes_file:
            seperated = n.split(';')
            self.nodes[int(seperated[0])] = [float(seperated[1]), float(seperated[2])]

    def build_graph(self):
        self.G = nx.Graph()
        links_file = read_file(self.edge_data_path)
        for l in links_file:
            seperated = l.split(';')
            self.G.add_edge(int(seperated[0]), int(seperated[1]), bandwidth=int(seperated[2]), delay=int(seperated[3]), reliability=float(seperated[4]))

    def draw_graph(self):
        pass

def read_demand_file(file_path):
    result = []
    lines = read_file(file_path)
    for line in lines:
        seperated = line.split(';')
        values = (int(seperated[0]), int(seperated[1]), int(seperated[2]))
        result.append(values)

    return result

def read_file(file_path):
    result = []

    with open(file_path) as f:
        for line in f:
            line = line[:-1]
            line = line.replace(',', '.')
            result.append(line)

    return result[1:]

if __name__ == '__main__':
    network_topology = NetworkTopology(NODE_DATA_PATH, EDGE_DATA_PATH)
    network_topology.setup_topology()

    aco = ACO(network_topology)
    aco.set_configurations(ants=50, iterations=100, alpha=1.0, beta=2.0, evaporation=0.5)  # Örnek konfigürasyon, aco_standalone.py'ye göre uyarla

    demands = read_demand_file(DEMAND_DATA_PATH)
    count = 1
    for demand in demands:
        print('*-' * 20)
        print(f"{count}. Talep: source_node_id: {demand[0]}, target_node_id={demand[1]}, demand_bandwidth={demand[2]}")
    
        aco.optimize(source_node_id=demand[0], target_node_id=demand[1], demand_bandwidth=demand[2])  
        count += 1
        print()
        print()

    print('*-' * 20)
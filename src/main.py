import os
import networkx as nx
from ga import GeneticAlgorithm

DEMAND_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "demand_data.csv")
EDGE_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "edge_data.csv")
NODE_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "node_data.csv")

class NetworkTopology:
    def __init__(self, node_data_path, edge_data_path):
        self.G = None
        self.node_data_path = node_data_path
        self.edge_data_path = edge_data_path
        self.build_graph()

    def build_graph(self):
        self.G = nx.Graph()
        links_file = read_file(self.edge_data_path)
        nodes_file = read_file(self.node_data_path)

        for n in nodes_file:
            seperated = n.split(';')
            self.G.add_node(int(seperated[0]), processing_delay=float(seperated[1]), node_reliability=float(seperated[2]))

        for l in links_file:
            seperated = l.split(';')
            self.G.add_edge(int(seperated[0]), int(seperated[1]), bandwidth=int(seperated[2]), delay=int(seperated[3]), reliability=float(seperated[4]))

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

    ga = GeneticAlgorithm(network_topology)
    ga.set_configurations(population_size=200, mutation_rate=0.2, generations=1000, elitism_percentage=0.05, tournament_size=3, max_stagnation=50)

    senaryolar = {
        "Dengeli": {'delay': 0.33, 'reliability': 0.33, 'resource': 0.33}
    }

    demands = read_demand_file(DEMAND_DATA_PATH)
    count = 1
    for demand in demands:
        source = demand[0]
        target = demand[1]
        bw = demand[2]
        
        print('=' * 60)
        print(f"{count}. TALEP: {source} -> {target} (Bant Genişliği: {bw} Mbps)")
        print('=' * 60)

        for senaryo_adi, agirliklar in senaryolar.items():
            print(f"\n--- Senaryo: {senaryo_adi} {agirliklar} ---")

            best_route = ga.genetic_algorithm(
                source_node_id=source, 
                target_node_id=target, 
                demand_bandwidth=bw,
                weights=agirliklar  
            )

            if best_route:
                print(f"SONUÇ: Rota BAŞARIYLA bulundu! (Adım Sayısı: {len(best_route)})")
            else:
                print(f"SONUÇ: Rota BULUNAMADI.")
            
        count += 1
        print('\n\n')

    print('*-' * 20)
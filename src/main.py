import os

DEMAND_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "demand_data.csv")
EDGE_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "edge_data.csv")
NODE_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "node_data.csv")

class NetworkTopology:
    def __init__(self, connection_probability=0.4):
        self.connection_probabability = connection_probability
        self.nodes = []
        self.links = []
        self.graph = {}

    def setup_topology(self, edge_data_path, node_data_path):
        self.set_links_from_file(edge_data_path)
        self.create_nodes_from_file(node_data_path)
        self.create_graph()

    def create_nodes_from_file(self, file_path):
        nodes_file = read_file(file_path)
        for n in nodes_file:
            seperated = n.split(';')
            node = Node(int(seperated[0]), float(seperated[1]), float(seperated[2]), self)
            node.assign_adjacencies()
            self.nodes.append(node)

    def set_links_from_file(self, file_path):
        links_file = read_file(file_path)
        for l in links_file:
            seperated = l.split(';')
            link = Link(int(seperated[0]), int(seperated[1]), int(seperated[2]), int(seperated[3]), float(seperated[4]))
            self.links.append(link)

    def create_graph(self):
        for node in self.nodes:
            self.graph[node.id] = node.adjacency_list
        
class Node:
    def __init__(self, id: int, processing_delay: float, node_reliability: float, network_topology: NetworkTopology):
        self.id = id
        self.processing_delay = processing_delay # [0.5 ms - 2.0 ms]
        self.node_reliability = node_reliability # [0.95, 0.999]
        self.adjacency_list = []
        self.network_topology = network_topology

    def assign_adjacencies(self):
        for link in self.network_topology.links:
            if link.node1_id == self.id:
                self.adjacency_list.append(link.node2_id)

            elif link.node1_id > self.id:
                break

    def __str__(self):
        return f'id: {self.id}, processing_delay: {self.processing_delay}, node_reliability: {self.node_reliability}'

class Link:
    def __init__(self, node1_id: int, node2_id: int, bandwidth: int, link_delay: int, link_reliability: float):
        self.node1_id = node1_id
        self.node2_id = node2_id
        self.bandwidth = bandwidth # [100 Mbps, 1000 Mbps]
        self.link_delay = link_delay # [3 ms, 15 ms]
        self.link_reliability = link_reliability # [0.95, 0.999]

    def __str__(self):
        return f'node1_id: {self.node1_id}, node2_id: {self.node2_id}, bandwidth: {self.bandwidth}, link_delay: {self.link_delay}, link_reliability: {self.link_reliability}'

class Path:
    def __init__(self, network_topology: NetworkTopology, nodes: list):
        self.network_topology = network_topology
        self.nodes = nodes
        self.links = []
        self.assign_links()

    def assign_links(self):
        for link in self.network_topology.links:

            for i in range(len(self.nodes) - 1):
                j = i + 1
                small = min(self.nodes[i].id, self.nodes[j].id)
                large = max(self.nodes[i].id, self.nodes[j].id)

                if link.node1_id == small and link.node2_id == large:
                    self.links.append(link)

    def __str__(self):
        result = ' '
        for node in self.nodes:
            result = result + ' ' + str(node.id) + ' -> '
        
        return result[2: -3]

class MetricsCalculator: 
    def __init__(self, path: Path):
        self.path = path
        
    def calculate_metrics(self):
        total_delay = self.calculate_total_delay()
        total_reliability = self.calculate_reliability_cost()
        resource_cost = self.calculate_resource_cost()

        print(f"Total Delay: {total_delay}")
        print(f"Total Reliability: {total_reliability}")
        print(f"Resource Cost: {resource_cost}")

        return total_delay, total_reliability, resource_cost

    def calculate_total_delay(self):
        sum_link_delay = 0
        sum_processing_delay = 0

        for link in self.path.links:
            sum_link_delay += link.link_delay

        for i in range(len(self.path.nodes)):
            if i != 0 and i != len(self.path.nodes) - 1:
                sum_processing_delay += self.path.nodes[i].processing_delay

        return sum_link_delay + sum_processing_delay

    def calculate_reliability_cost(self):
        import math
        sum_link_reliability = 0
        sum_node_reliability = 0

        for link in self.path.links:
            sum_link_reliability += -(math.log(link.link_reliability))

        for node in self.path.nodes:
            sum_node_reliability += -(math.log(node.node_reliability))

        return sum_link_reliability + sum_node_reliability

    def calculate_resource_cost(self):
        resource_cost = 0

        for link in self.path.links:
            resource_cost += (1000 / link.bandwidth)

        return resource_cost

# Çok Amaçlı Çözüm    
def weighted_sum_method(path: Path, weight_delay, weight_reliability, weight_resource):
    metrics = MetricsCalculator(path)
    total_delay, total_reliability, resource_cost = metrics.calculate_metrics()

    total_cost = weight_delay * total_delay + weight_reliability * total_reliability + weight_resource * resource_cost

    return total_cost

def read_file(file_path):
    result = []

    with open(file_path) as f:
        for line in f:
            line = line[:-1]
            line = line.replace(',', '.')
            result.append(line)

    return result[1:]

if __name__ == '__main__':
    import random
    network_topology = NetworkTopology()
    network_topology.setup_topology(EDGE_DATA_PATH, NODE_DATA_PATH)

    # Başlangıç düğümünün komşularından başlayarak rastgele yol bulma test kodu
    best_fitness = 9999
    best_path = None

    for i in range(100):

        current_node = 12
        random_path = [current_node]

        for i in range(20):
            
            adjacencies = network_topology.graph[current_node]

            if len(adjacencies) >= 1:
                r = random.randint(0, len(adjacencies) - 1)
                current_node = adjacencies[r]
                random_path.append(current_node)
            else:
                break

        nodes = []
        for i in range(len(random_path)):
            nodes.append(network_topology.nodes[random_path[i]])

        path = Path(network_topology, nodes)
        print(path)
        total_cost = weighted_sum_method(path, 0.33, 0.34, 0.33)
        print(f"Fitness: {total_cost}\n")
        if total_cost < best_fitness:
            best_path = path
            best_fitness = total_cost
    
    print()
    print('=*' * 35)
    print(f'En iyi yol: {best_path} \nEn iyi fitness: {best_fitness}')
    print('=*' * 35)

    # En iyi yolu bulma algoritması uygulanması (başka dosyada geliştirilecek ve burada import edilip parametreleri verilerek kullanılacaktır.)
    

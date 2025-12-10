import os

DEMAND_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "demand_data.csv")
EDGE_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "edge_data.csv")
NODE_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "node_data.csv")

class NetworkTopology:
    def __init__(self, connection_probability=0.4):
        self.connection_probabability = connection_probability
        self.nodes = []
        self.links = []

    def create_nodes_from_file(self, file_path):
        nodes_file = read_file(file_path)
        for n in nodes_file:
            seperated = n.split(';')
            node = Node(int(seperated[0]), float(seperated[1]), float(seperated[2]))
            self.nodes.append(node)

    def set_links_from_file(self, file_path):
        links_file = read_file(file_path)
        for l in links_file:
            seperated = l.split(';')
            link = Link(int(seperated[0]), int(seperated[1]), int(seperated[2]), int(seperated[3]), float(seperated[4]))
            self.links.append(link)

class Node:
    def __init__(self, id: int, processing_delay: float, node_reliability: float):
        self.id = id
        self.processing_delay = processing_delay # [0.5 ms - 2.0 ms]
        self.node_reliability = node_reliability # [0.95, 0.999]

    def __str__(self):
        return f'id: {self.id}, processing_delay: {self.processing_delay}, node_reliability: {self.node_reliability}'

class Link:
    def __init__(self, node1_id: int, node2_id: int, bandwidth: int, link_delay: int, link_reliability: float):
        self.node1_id = node1_id
        self.node2_id = node2_id
        self.bandwidth = bandwidth # [100 Mbps, 1000 Mbps]
        self.link_delay = link_delay # [3 ms, 15 ms]
        self.link_reliability = link_reliability # [0.95, 0.999]

class Path:
    def __init__(self, nodes: list, links: list):
        self.nodes = nodes
        self.links = links

    def __str__(self):
        for node in self.nodes:
            print(f"{node.id} -> ", end=" ")

class Metrics: 
    def calculate_metrics(self, path: Path):
        total_delay = self.calculate_total_delay(path)
        total_reliability = self.calculate_total_reliability(path)
        resource_cost = self.calculate_resource_cost(path)

        print(f"Total Delay: {total_delay}")
        print(f"Total Reliability: {total_reliability}")
        print(f"Resource Cost: {resource_cost}")

        return total_delay, total_reliability, resource_cost

    def calculate_total_delay(path: Path):
        sum_link_delay = 0
        sum_processing_delay = 0

        for link in path.links:
            sum_link_delay += link.link_delay

        for i in range(len(path.nodes)):
            if i != 0 and i != len(path.nodes) - 1:
                sum_processing_delay += path.nodes[i].processing_delay

        return sum_link_delay + sum_processing_delay

    def calculate_reliability_cost(path: Path):
        import math
        sum_link_reliability = 0
        sum_node_reliability = 0

        for link in path.links:
            sum_link_reliability += -(math.log(link.link_reliability))

        for node in path.nodes:
            sum_node_reliability += -(math.log(node.node_reliability))

        return sum_link_reliability + sum_node_reliability

    def calculate_resource_cost(path: Path):
        resource_cost = 0

        for link in path.links:
            resource_cost += (1000 / link.bandwidth)

        return resource_cost

def read_file(file_path):
    result = []

    with open(file_path) as f:
        for line in f:
            line = line[:-1]
            line = line.replace(',', '.')
            result.append(line)

    return result[1:]

# Path -> P = {n1, n2, ..., nk}
# Path = [1, 63, 24, 256]

if __name__ == '__main__':
    
    network_topology = NetworkTopology()
    network_topology.create_nodes_from_file(NODE_DATA_PATH)

    for node in network_topology.nodes:
        print(node)


    # En iyi yolu bulma algoritması uygulanması (başka dosyada geliştirilecek ve burada import edilip parametreleri verilerek kullanılacaktır.)
    

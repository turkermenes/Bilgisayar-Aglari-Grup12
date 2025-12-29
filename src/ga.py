import random
import numpy as np
import networkx as nx

class GeneticAlgorithm:
    
    def __init__(self, network_topology):
        self.network_topology = network_topology
        self.set_configurations()

    def set_configurations(self, population_size=100, mutation_rate=0.2, generations=25, elitisim_percentage=0.1, tournament_size=25, max_stagnation=15):
        self.POPULATION_SIZE = population_size
        self.MUTATION_RATE = mutation_rate
        self.GENERATIONS = generations
        self.ELITISM_PERCENTAGE = elitisim_percentage
        self.TOURNAMENT_SIZE = tournament_size
        self.MAX_STAGNATION = max_stagnation
        
    
    def initialise_population(self, pop_size, source_node_id: int, target_node_id: int, bandwidth: int):
        population = []
        
        count=0
        max_count = pop_size*50

        
        while len(population) < pop_size and count < max_count:
            count+=1

            visited = {source_node_id}
            
            random_chromosome = [source_node_id]
            if len(self.network_topology.G[source_node_id]) == 0:
                continue
            current_node = source_node_id
            
            min_bandwidth = np.inf
            

            while current_node != target_node_id:
                all_neighbors = list(self.network_topology.G[current_node].keys())
                valid_neighbors = [n for n in all_neighbors if n not in visited]
                if not valid_neighbors:
                    random_chromosome = [] # Çıkmaz sokak
                    break
                next_node = random.choice(valid_neighbors)
                
                current_link_bw = self.network_topology.G[current_node][next_node]['bandwidth']
                if current_link_bw < min_bandwidth:
                    min_bandwidth = current_link_bw
                
                random_chromosome.append(next_node)
                visited.add(next_node) # Gidilenlere ekle
                current_node = next_node
                
                
                if len(random_chromosome) > len(self.network_topology.G.nodes):
                    random_chromosome = []
                    break
            
            if len(random_chromosome) > 0 and random_chromosome[-1] == target_node_id:
                
                if min_bandwidth > bandwidth:
                    if random_chromosome not in population:
                        population.append(random_chromosome)
                    elif count > pop_size * 20:    
                        population.append(random_chromosome)
                
        
        return population

    def calculate_fitness(self, chromosome, weight_delay, weight_reliability, weight_resource):
        total_delay = total_reliability = resource_cost = fitness = 0
        
        # TOTAL DELAY HESAPLAMA
        total_link_delay = 0
        total_processing_delay = 0
        for i in range(len(chromosome) - 1):
            j = i + 1
            total_link_delay += self.network_topology.G[chromosome[i]][chromosome[j]]['delay']
        
        for i in range(len(chromosome)):
            if i != 0 and i != len(chromosome) - 1:
                total_processing_delay += self.network_topology.nodes[chromosome[i]][0]

        total_delay = total_link_delay + total_processing_delay

        # TOTAL RELIABILITY HESAPLAMA
        total_link_reliability = 0
        total_node_reliability = 0
        for i in range(len(chromosome) - 1):
            j = i + 1
            total_link_reliability += -(np.log(self.network_topology.G[chromosome[i]][chromosome[j]]['reliability']))
        
        for i in range(len(chromosome)):
            total_node_reliability += -(np.log(self.network_topology.nodes[chromosome[i]][0]))

        total_reliability = total_link_reliability + total_node_reliability

        # RESOURCE COST HESAPLAMA
        for i in range(len(chromosome) - 1):
            j = i + 1
            resource_cost += 1000 / self.network_topology.G[chromosome[i]][chromosome[j]]['bandwidth']

        # FITNESS HESAPLA
        fitness = weight_delay * total_delay + weight_reliability * total_reliability + weight_resource * resource_cost

        return float(fitness)
    
     
    def tournament_selection(self, population, tournament_size, weights):
        selected_parents = []
        for _ in range(2):
            tournament = random.sample(population,min(len(population), tournament_size))
            best_fitness = np.inf
            best_parent = None
            for p in tournament:
                
                fitness = self.calculate_fitness(p, weights['delay'], weights['reliability'], weights['resource'])
                if fitness < best_fitness:
                    best_fitness = fitness
                    best_parent = p
            
            selected_parents.append(best_parent)

        return selected_parents

    def crossover(self, parent1, parent2):
        route1 = parent1
        route2 = parent2

        if min(len(route1), len(route2)) > 2 and route1 != route2:
            shorter = route1 if len(route1) < len(route2) else route2
            longer = route2 if len(route2) > len(route1) else route1
            crossover_point_short = 0
            crossover_point_long = 0

            for i in range(len(shorter) - 1):
                if i != 0:
                    if shorter[i] in longer and longer[0] != shorter[i] and longer[len(longer) - 1] != shorter[i]:
                        crossover_point_short = i
                        crossover_point_long = longer.index(shorter[i])
                        break
            
            if crossover_point_short != 0 and crossover_point_long != 0:
                offspring1_route = shorter[:crossover_point_short] + longer[crossover_point_long:]
                offspring2_route = longer[:crossover_point_long] + shorter[crossover_point_short:]
            else:
                offspring1_route = route1
                offspring2_route = route2

            return offspring1_route, offspring2_route
        else:
            return parent1, parent2
        
    # Crossover sonrasında rotada aynı düğüm birden fazla tekrar ediyorsa onu 1 defa olacak şekilde düzenlemek için.
    def repair_route():
        pass

    def mutation(self, chromosome, mutation_rate):
        mutated_chromosome = list(chromosome)

        for i in range(len(mutated_chromosome)):
            if i != 0 and i != len(mutated_chromosome) - 1:
                current = mutated_chromosome[i]
                r = random.random()
                if r <= mutation_rate:
                    prev = mutated_chromosome[i - 1]
                    next = mutated_chromosome[i + 1]

                    prev_adj = set(self.network_topology.G.adj[prev].keys())
                    next_adj = set(self.network_topology.G.adj[next].keys())
                    intersect_adj = prev_adj.intersection(next_adj)

                   
                    kesisim = list(intersect_adj)
                    if current in kesisim:
                        kesisim.remove(current)
                    if len(kesisim) > 0:
                        new_node = random.choice(kesisim) 
                        mutated_chromosome[i] = new_node      
                    else:
                        continue    
                    
        
        return mutated_chromosome
    
    def quick_sort(self, population, w_d, w_r, w_res):
        if len(population) <= 1:
            return population
        pivot = population[len(population) // 2]
        pivot_fitness = self.calculate_fitness(pivot, w_d, w_r, w_res)

        left = []    
        middle = []  
        right = []

        for chrom in population:
            fitness = self.calculate_fitness(chrom, w_d, w_r, w_res)
            
            if fitness < pivot_fitness:
                left.append(chrom)
            elif fitness > pivot_fitness:
                right.append(chrom)
            else:
                middle.append(chrom)

        return (self.quick_sort(left, w_d, w_r, w_res) + 
                middle + 
                self.quick_sort(right, w_d, w_r, w_res))        
   

    def sort_population(self, population, weights):
        return self.quick_sort(population, weights['delay'], weights['reliability'], weights['resource'])

    def print_population_results():
        pass

    def genetic_algorithm(self, source_node_id: int, target_node_id: int, demand_bandwidth: int, weights=None):
        if weights is None:
            weights = {'delay': 0.33, 'reliability': 0.33, 'resource': 0.33}

        population = self.initialise_population(self.POPULATION_SIZE, source_node_id, target_node_id, demand_bandwidth)

        if not population:
            print(f"Uyarı: {source_node_id} -> {target_node_id} için başlangıç popülasyonu oluşturulamadı.")
            return None

        population = self.sort_population(population, weights)

        best_fitness = float('inf')
        stagnation_counter = 0

        best_routes_per_generation = []

        for generation in range(self.GENERATIONS):
            new_population = []

            elite_chromosomes = population[:int(self.ELITISM_PERCENTAGE * self.POPULATION_SIZE)]
            new_population.extend(elite_chromosomes)

            while len(new_population) < self.POPULATION_SIZE:
                parent1, parent2 = self.tournament_selection(population, self.TOURNAMENT_SIZE, weights)

                offspring1, offspring2 = self.crossover(parent1, parent2)
                offspring3 = self.mutation(offspring1, self.MUTATION_RATE)
                offspring4 = self.mutation(offspring1, self.MUTATION_RATE)

                new_population.extend([offspring1, offspring2, offspring3, offspring4])

            population = new_population
            population = self.sort_population(population, weights)

            best_chromosome = population[0]
            best_routes_per_generation.append(best_chromosome)

            current_best_fitness = self.calculate_fitness(best_chromosome, weights['delay'], weights['reliability'], weights['resource'])
            if current_best_fitness < best_fitness:
                best_fitness = current_best_fitness
                print(f'Generation {generation} best fitness: {best_fitness}')
                stagnation_counter = 0
            else:
                stagnation_counter += 1
                
            
            if stagnation_counter >= self.MAX_STAGNATION:
                print(f"Durgunluk dolayısıyla jenerasyon {generation}'te sonlandırılıyor.")
                break

        if generation == self.GENERATIONS - 1:
            print("Maksimum jenerasyon sayısına ulaşıldığı için sonlandırılıyor.")

        print(f"Best fitness değeri: {best_fitness}")
        print(f"Bulunan en iyi rota: {best_chromosome}")

        return best_chromosome
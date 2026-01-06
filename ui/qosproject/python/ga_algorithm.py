#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import random
import numpy as np
import networkx as nx

EPS = 1e-12


class NetworkTopology:
    """
    CSV (nodes_df, edges_df) verilerinden NetworkX Graph üretir.
    Bu sınıf arayüz/uygulama katmanı ile GA/solver katmanı arasında köprü görevi görür.
    """

    def __init__(self, nodes_df, edges_df):
        # NetworkX graph nesnesi
        self.G = nx.Graph()

        # CSV kolon adlarını normalize eder 
        def norm_col(c: str) -> str:
            return str(c).replace("\ufeff", "").strip().lower()

        # Olası kolon isimlerinden ilk bulunanı seçer
        def pick(colmap, *names):
            for n in names:
                if n in colmap:
                    return colmap[n]
            return None

        # Node/Edge dataframe kolonlarını normalize edilmiş map e çevir
        ncols = {norm_col(c): c for c in nodes_df.columns}
        ecols = {norm_col(c): c for c in edges_df.columns}

        
        # Beklenen: node_id; s_ms; r_node
        node_id_col = pick(ncols, "node_id", "id")
        proc_col = pick(ncols, "s_ms", "processing_delay")
        node_rel_col = pick(ncols, "r_node", "node_reliability", "reliability")

        # node_id olmadan graph kurulamaz
        if node_id_col is None:
            raise ValueError("nodes_df must contain 'node_id' column (or equivalent).")

        # Düğümleri graph'a ekle 
        for _, row in nodes_df.iterrows():
            nid = int(row[node_id_col])

            processing_delay = float(row[proc_col]) if proc_col is not None else 0.0
            node_reliability = float(row[node_rel_col]) if node_rel_col is not None else 1.0

            self.G.add_node(
                nid,
                # GA'nın kullandığı anahtarlar
                processing_delay=processing_delay,
                node_reliability=node_reliability,
                # Arayüz/diğer modüller için alias
                s_ms=processing_delay,
                r_node=node_reliability,
            )

       
        # Beklenen: src; dst; capacity_mbps; delay_ms; r_link
        src_col = pick(ecols, "src", "source", "from")
        dst_col = pick(ecols, "dst", "target", "to")

        bw_col = pick(ecols, "capacity_mbps", "bandwidth_mbps", "bandwidth", "bw", "capacity", "link_bw")
        delay_col = pick(ecols, "delay_ms", "link_delay_ms", "delay", "latency")
        rel_col = pick(ecols, "r_link", "link_reliability", "reliability", "rel", "availability")

        # src/dst olmadan edge eklenemez
        if src_col is None or dst_col is None:
            raise ValueError("edges_df must contain 'src' and 'dst' columns (or equivalent).")

        # Bant genişliği/gecikme/güvenilirlik olmadan GA/solver hesapları yapılamaz
        if bw_col is None or delay_col is None or rel_col is None:
            raise ValueError(
                "edges_df must contain capacity/bandwidth, delay, reliability columns "
                "(e.g., capacity_mbps, delay_ms, r_link)."
            )

        # Linkleri graph'a ekle 
        for _, row in edges_df.iterrows():
            u = int(row[src_col])
            v = int(row[dst_col])

            bandwidth = float(row[bw_col])
            delay = float(row[delay_col])
            reliability = float(row[rel_col])

            # Edge uçları node tablosunda yoksa varsayılan node değerleriyle ekle
            if u not in self.G:
                self.G.add_node(u, processing_delay=0.0, node_reliability=1.0, s_ms=0.0, r_node=1.0)
            if v not in self.G:
                self.G.add_node(v, processing_delay=0.0, node_reliability=1.0, s_ms=0.0, r_node=1.0)

            self.G.add_edge(
                u, v,
                # GA keys
                bandwidth=bandwidth,
                delay=delay,
                reliability=reliability,
                # aliases (arayüz/diğer modüller uyumluluğu)
                capacity_mbps=bandwidth,
                bandwidth_mbps=bandwidth,
                link_delay_ms=delay,
                delay_ms=delay,
                r_link=reliability,
                link_reliability=reliability,
            )


class GeneticAlgorithm:

    def __init__(self, network_topology):
        self.network_topology = network_topology
        self.G = network_topology.G
        self.set_configurations()

    def set_configurations(
        self,
        population_size=200,
        mutation_rate=0.2,
        generations=1000,
        elitism_percentage=0.05,
        tournament_size=3,
        max_stagnation=50,
        elitisim_percentage=None
    ):
        if elitisim_percentage is not None:
            elitism_percentage = elitisim_percentage

        self.POPULATION_SIZE = population_size
        self.MUTATION_RATE = mutation_rate
        self.GENERATIONS = generations
        self.ELITISM_PERCENTAGE = elitism_percentage
        self.TOURNAMENT_SIZE = tournament_size
        self.MAX_STAGNATION = max_stagnation

    def initialise_population(self, pop_size, source_node_id: int, target_node_id: int, bandwidth: float):
        population = []

        count = 0
        max_count = pop_size * 50

        while len(population) < pop_size and count < max_count:
            count += 1

            visited = {source_node_id}
            random_chromosome = [source_node_id]

            if len(self.G[source_node_id]) == 0:
                continue

            current_node = source_node_id
            min_bandwidth = np.inf

            while current_node != target_node_id:
                all_neighbors = list(self.G[current_node].keys())
                valid_neighbors = [n for n in all_neighbors if n not in visited]
                if not valid_neighbors:
                    random_chromosome = []
                    break

                next_node = random.choice(valid_neighbors)

                current_link_bw = self.G[current_node][next_node]['bandwidth']
                if current_link_bw < min_bandwidth:
                    min_bandwidth = current_link_bw

                random_chromosome.append(next_node)
                visited.add(next_node)
                current_node = next_node

                if len(random_chromosome) > len(self.G.nodes):
                    random_chromosome = []
                    break

            if len(random_chromosome) > 0 and random_chromosome[-1] == target_node_id:
                if min_bandwidth > bandwidth:
                    if random_chromosome not in population:
                        population.append(random_chromosome)

        return population

    def calculate_fitness(self, chromosome, weight_delay, weight_reliability, weight_resource):
        total_delay = total_reliability = resource_cost = fitness = 0

        total_link_delay = 0
        total_processing_delay = 0
        for i in range(len(chromosome) - 1):
            j = i + 1
            total_link_delay += self.G[chromosome[i]][chromosome[j]]['delay']

        for i in range(len(chromosome)):
            if i != 0 and i != len(chromosome) - 1:
                total_processing_delay += self.G.nodes[chromosome[i]]['processing_delay']

        total_delay = total_link_delay + total_processing_delay

        total_link_reliability = 0
        total_node_reliability = 0
        for i in range(len(chromosome) - 1):
            j = i + 1
            total_link_reliability += -(np.log(self.G[chromosome[i]][chromosome[j]]['reliability']))

        for i in range(len(chromosome)):
            total_node_reliability += -(np.log(self.G.nodes[chromosome[i]]['node_reliability']))

        total_reliability = total_link_reliability + total_node_reliability

        for i in range(len(chromosome) - 1):
            j = i + 1
            resource_cost += 1000 / self.G[chromosome[i]][chromosome[j]]['bandwidth']

        fitness = weight_delay * total_delay + weight_reliability * total_reliability + weight_resource * resource_cost
        return float(fitness)

    def tournament_selection(self, population, tournament_size, weights):
        selected_parents = []
        for _ in range(2):
            tournament = random.sample(population, min(len(population), tournament_size))
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

    def mutation(self, chromosome, mutation_rate):
        mutated_chromosome = list(chromosome)
        first_gene = chromosome[0]
        last_gene = chromosome[-1]
        for gene in mutated_chromosome:
            if gene != first_gene and gene != last_gene:
                i = mutated_chromosome.index(gene)
                r = random.random()
                if r <= mutation_rate:
                    prev = mutated_chromosome[i - 1]
                    next_ = mutated_chromosome[i + 1]

                    prev_adj = set(self.G.adj[prev].keys())
                    next_adj = set(self.G.adj[next_].keys())

                    if prev in next_adj:
                        mutated_chromosome.remove(gene)
                    else:
                        intersect_adj = prev_adj.intersection(next_adj)

                        kesisim = list(intersect_adj)
                        if gene in kesisim:
                            kesisim.remove(gene)

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

        return self.quick_sort(left, w_d, w_r, w_res) + middle + self.quick_sort(right, w_d, w_r, w_res)

    def sort_population(self, population, weights):
        return self.quick_sort(population, weights['delay'], weights['reliability'], weights['resource'])

    def genetic_algorithm(
        self,
        source_node_id: int,
        target_node_id: int,
        demand_bandwidth: float,
        weight_delay: float = None,
        weight_reliability: float = None,
        weight_resource: float = None,
        verbose: bool = True,
        weights=None
    ):
        if weights is None:
            if (weight_delay is not None) and (weight_reliability is not None) and (weight_resource is not None):
                weights = {
                    'delay': float(weight_delay),
                    'reliability': float(weight_reliability),
                    'resource': float(weight_resource),
                }
            else:
                weights = {'delay': 0.33, 'reliability': 0.33, 'resource': 0.33}

        population = self.initialise_population(self.POPULATION_SIZE, source_node_id, target_node_id, demand_bandwidth)

        if not population:
            if verbose:
                print(f"Uyarı: {source_node_id} -> {target_node_id} için başlangıç popülasyonu oluşturulamadı.")
            return None, float("inf")

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
                mutation_rate = self.MUTATION_RATE

                if offspring1 == parent1 and offspring2 == parent2:
                    mutation_rate = min(1, mutation_rate + 0.5)

                offspring3 = self.mutation(offspring1, mutation_rate)
                offspring4 = self.mutation(offspring2, mutation_rate)

                offsprings = [offspring1, offspring2, offspring3, offspring4]

                for offspring in offsprings:
                    if offspring not in new_population:
                        new_population.append(offspring)

            population = new_population
            population = self.sort_population(population, weights)

            best_chromosome = population[0]
            best_routes_per_generation.append(best_chromosome)

            current_best_fitness = self.calculate_fitness(
                best_chromosome, weights['delay'], weights['reliability'], weights['resource']
            )

            if current_best_fitness < best_fitness:
                best_fitness = current_best_fitness
                if verbose:
                    print(f'Generation {generation} best fitness: {best_fitness}')
                stagnation_counter = 0
            else:
                stagnation_counter += 1

            if stagnation_counter >= self.MAX_STAGNATION:
                if verbose:
                    print(f"Durgunluk dolayısıyla {generation}. jenerasyonda sonlandırılıyor.")
                break

        if generation == self.GENERATIONS - 1:
            if verbose:
                print(f"Maksimum jenerasyon sayısına ulaşıldığı için {generation}. jenerasyonda sonlandırılıyor.")

        if verbose:
            print(f"Best fitness değeri: {best_fitness}")
            print(f"Bulunan en iyi rota: {best_chromosome}")

        return best_chromosome, float(best_fitness)

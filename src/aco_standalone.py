import random
import numpy as np
import networkx as nx
from collections import defaultdict

class ACO:
    """
    Ant Colony Optimization (ACO) for Multi-Objective Network Routing
    
    Karınca kolonisi davranışını taklit ederek ağ üzerinde optimal rotalar bulur.
    Karıncalar feromon bırakarak iyi yolları işaretler ve diğer karıncalar
    bu feromonlara göre kararlar alır.
    """
    
    def __init__(self, network_topology):
        """
        ACO algoritmasını başlat
        
        Args:
            network_topology: NetworkTopology sınıfının instance'ı
        """
        self.network = network_topology
        self.graph = network_topology.G
        self.nodes = network_topology.nodes
        self.pheromone_map = defaultdict(lambda: 1.0)
        self.best_solution = None
        self.best_cost = float('inf')
        
        # Varsayılan parametreler
        self.num_ants = 50
        self.num_iterations = 100
        self.evaporation_rate = 0.15
        self.pheromone_constant = 100.0
        self.alpha = 1.2  # Feromon etkisi
        self.beta = 2.5   # Heuristic etkisi
        self.early_stop_threshold = 25
    
    def set_configurations(self, ants=50, iterations=100, evaporation=0.15,
                 pheromone_constant=100.0, alpha=1.2, beta=2.5, early_stop_threshold=25):
        """
        ACO parametrelerini yapılandır
        
        Args:
            ants: Her iterasyondaki karınca sayısı
            iterations: Maksimum iterasyon sayısı
            evaporation: Feromon buharlaşma oranı (0-1)
            pheromone_constant: Feromon bırakma sabiti
            alpha: Feromon etkisi üssü
            beta: Heuristic etkisi üssü
            early_stop_threshold: İyileşme olmazsa durdurma eşiği
        """
        self.num_ants = ants
        self.num_iterations = iterations
        self.evaporation_rate = evaporation
        self.pheromone_constant = pheromone_constant
        self.alpha = alpha
        self.beta = beta
        self.early_stop_threshold = early_stop_threshold
    
    def _reset_pheromones(self):
        """Tüm feromon değerlerini başlangıç değerine döndür"""
        self.pheromone_map.clear()
        self.pheromone_map = defaultdict(lambda: 1.0)
    
    def _compute_path_metrics(self, path):
        """
        Verilen bir rotanın metriklerini hesapla
        
        Args:
            path: Düğüm listesi [n1, n2, ..., nk]
            
        Returns:
            tuple: (total_delay, reliability_cost, resource_cost)
        """
        if not path or len(path) < 2:
            return float('inf'), float('inf'), float('inf')
        
        total_delay = 0.0
        reliability_cost = 0.0
        resource_cost = 0.0
        
        # Kenar (edge) üzerindeki metrikler
        for i in range(len(path) - 1):
            current_node = path[i]
            next_node = path[i + 1]
            
            # Graf üzerinde kenar var mı kontrol et
            if not self.graph.has_edge(current_node, next_node):
                return float('inf'), float('inf'), float('inf')
            
            edge_data = self.graph[current_node][next_node]
            
            # Gecikme
            total_delay += edge_data['delay']
            
            # Güvenilirlik (log-transform ile toplama)
            link_reliability = edge_data['reliability']
            reliability_cost += -np.log(max(link_reliability, 1e-10))
            
            # Kaynak kullanımı (düşük bandwidth = yüksek maliyet)
            bandwidth = edge_data['bandwidth']
            resource_cost += 1000.0 / max(bandwidth, 1e-10)
        
        # Düğüm (node) üzerindeki metrikler
        for idx, node in enumerate(path):
            # Kaynak ve hedef düğümler için işlem gecikmesi ekleme
            if idx == 0 or idx == len(path) - 1:
                continue
            
            processing_delay = self.nodes[node][0]
            node_reliability = self.nodes[node][1]
            
            total_delay += processing_delay
            reliability_cost += -np.log(max(node_reliability, 1e-10))
        
        return total_delay, reliability_cost, resource_cost
    
    def _calculate_path_fitness(self, path, w_delay, w_reliability, w_resource):
        """
        Rotanın toplam fitness değerini hesapla
        
        Args:
            path: Rota düğüm listesi
            w_delay: Gecikme ağırlığı
            w_reliability: Güvenilirlik ağırlığı
            w_resource: Kaynak ağırlığı
            
        Returns:
            float: Toplam maliyet (düşük = iyi)
        """
        delay, rel_cost, res_cost = self._compute_path_metrics(path)
        
        if delay == float('inf'):
            return float('inf')
        
        total_cost = (w_delay * delay + 
                     w_reliability * rel_cost + 
                     w_resource * res_cost)
        
        return total_cost
    
    def _compute_edge_heuristic(self, from_node, to_node, w_delay, w_reliability, w_resource):
        """
        Bir kenar için heuristic (görünürlük) değerini hesapla
        
        Heuristic, kenarın ne kadar "çekici" olduğunu gösterir.
        Düşük maliyetli kenarlar daha çekicidir.
        
        Args:
            from_node, to_node: Kenarın uç noktaları
            w_delay, w_reliability, w_resource: Ağırlık katsayıları
            
        Returns:
            float: Heuristic değeri (η)
        """
        if not self.graph.has_edge(from_node, to_node):
            return 0.0
        
        edge_data = self.graph[from_node][to_node]
        
        # Kenar maliyetini hesapla
        delay = edge_data['delay']
        rel = edge_data['reliability']
        bw = edge_data['bandwidth']
        
        rel_cost = -np.log(max(rel, 1e-10))
        res_cost = 1000.0 / max(bw, 1e-10)
        
        edge_cost = (w_delay * delay + 
                    w_reliability * rel_cost + 
                    w_resource * res_cost)
        
        # Heuristic = 1 / cost (düşük maliyet = yüksek heuristic)
        return 1.0 / (edge_cost + 1e-10)
    
    def _get_feasible_neighbors(self, current_node, visited_nodes, min_bandwidth):
        """
        Mevcut düğümden gidilebilecek uygun komşuları bul
        
        Args:
            current_node: Şu anki düğüm
            visited_nodes: Ziyaret edilmiş düğümler kümesi
            min_bandwidth: Minimum gerekli bant genişliği
            
        Returns:
            list: Uygun komşu düğümlerin listesi
        """
        feasible = []
        
        for neighbor in self.graph.neighbors(current_node):
            # Zaten ziyaret edilmiş mi?
            if neighbor in visited_nodes:
                continue
            
            # Bant genişliği yeterli mi?
            edge_bandwidth = self.graph[current_node][neighbor]['bandwidth']
            if edge_bandwidth >= min_bandwidth:
                feasible.append(neighbor)
        
        return feasible
    
    def _select_next_node(self, current_node, feasible_neighbors, visited_nodes,
                         w_delay, w_reliability, w_resource):
        """
        Karınca için bir sonraki düğümü olasılıksal olarak seç
        
        ACO Formülü: P(i→j) = [τ^α × η^β] / Σ[τ^α × η^β]
        
        Args:
            current_node: Şu anki düğüm
            feasible_neighbors: Gidilebilecek komşular
            visited_nodes: Ziyaret edilmiş düğümler
            w_delay, w_reliability, w_resource: Ağırlıklar
            
        Returns:
            int: Seçilen düğüm ID'si veya None
        """
        if not feasible_neighbors:
            return None
        
        probabilities = []
        
        for neighbor in feasible_neighbors:
            # Feromon seviyesi (τ)
            pheromone = self.pheromone_map[(current_node, neighbor)]
            
            # Heuristic değeri (η)
            heuristic = self._compute_edge_heuristic(current_node, neighbor,
                                                     w_delay, w_reliability, w_resource)
            
            # Çekicilik = τ^α × η^β
            attractiveness = (pheromone ** self.alpha) * (heuristic ** self.beta)
            probabilities.append(attractiveness)
        
        # Olasılıkları normalize et
        total = sum(probabilities)
        if total == 0:
            # Eğer tüm olasılıklar 0 ise, rastgele seç
            return random.choice(feasible_neighbors)
        
        normalized_probs = [p / total for p in probabilities]
        
        # Roulette wheel selection
        selected_node = random.choices(feasible_neighbors, weights=normalized_probs, k=1)[0]
        
        return selected_node
    
    def _construct_ant_solution(self, source, target, min_bandwidth,
                                w_delay, w_reliability, w_resource, max_steps=500):
        """
        Tek bir karınca için çözüm oluştur (rota bul)
        
        Args:
            source: Kaynak düğüm
            target: Hedef düğüm
            min_bandwidth: Minimum bant genişliği gereksinimi
            w_delay, w_reliability, w_resource: Ağırlıklar
            max_steps: Maksimum adım sayısı (sonsuz döngü önleme)
            
        Returns:
            list veya None: Bulunan rota veya None
        """
        current_node = source
        path = [source]
        visited = {source}
        steps = 0
        
        while current_node != target and steps < max_steps:
            steps += 1
            
            # Gidilebilecek komşuları bul
            feasible_neighbors = self._get_feasible_neighbors(current_node, visited, min_bandwidth)
            
            if not feasible_neighbors:
                #막daşık sokak - başarısız
                return None
            
            # Bir sonraki düğümü seç
            next_node = self._select_next_node(current_node, feasible_neighbors, visited,
                                              w_delay, w_reliability, w_resource)
            
            if next_node is None:
                return None
            
            # Yolu güncelle
            path.append(next_node)
            visited.add(next_node)
            current_node = next_node
        
        # Hedefe ulaşıldı mı?
        if current_node == target:
            return path
        
        return None
    
    def _evaporate_pheromones(self):
        """
        Tüm kenarlardaki feromonları buharlaştır
        
        τ(i,j) ← (1 - ρ) × τ(i,j)
        """
        keys_to_update = list(self.pheromone_map.keys())
        
        for edge in keys_to_update:
            self.pheromone_map[edge] *= (1.0 - self.evaporation_rate)
            
            # Minimum feromon seviyesi
            if self.pheromone_map[edge] < 0.01:
                self.pheromone_map[edge] = 0.01
    
    def _deposit_pheromones(self, ant_solutions):
        """
        Karıncaların bulduğu yollara feromon bırak
        
        Δτ(i,j) = Q / L (L: yolun maliyeti)
        
        Args:
            ant_solutions: [(path, cost), ...] listesi
        """
        for path, cost in ant_solutions:
            if path is None or cost == float('inf'):
                continue
            
            # Daha iyi yollar daha fazla feromon bırakır
            pheromone_amount = self.pheromone_constant / (cost + 1e-10)
            
            # Yol üzerindeki her kenara feromon ekle
            for i in range(len(path) - 1):
                from_node = path[i]
                to_node = path[i + 1]
                
                self.pheromone_map[(from_node, to_node)] += pheromone_amount
                self.pheromone_map[(to_node, from_node)] += pheromone_amount
    
    def optimize(self, source_node_id: int, target_node_id: int, demand_bandwidth: int,
             weight_delay=0.33, weight_reliability=0.33, weight_resource=0.34):
        """
        ACO algoritmasını çalıştır ve optimal rotayı bul
        
        Args:
            source_node_id: Kaynak düğüm ID
            target_node_id: Hedef düğüm ID
            demand_bandwidth: İstenen minimum bant genişliği (Mbps)
            weight_delay: Gecikme ağırlığı (0-1)
            weight_reliability: Güvenilirlik ağırlığı (0-1)
            weight_resource: Kaynak kullanımı ağırlığı (0-1)
            
        Returns:
            tuple: (best_path, best_cost) veya (None, None)
        """
        # Başlangıç ayarları
        self._reset_pheromones()
        self.best_solution = None
        self.best_cost = float('inf')
        
        iterations_without_improvement = 0
        iteration_history = []
        
        print(f"\n{'='*70}")
        print(f"🐜 ACO Algoritması Başlatılıyor")
        print(f"{'='*70}")
        print(f"Kaynak: {source_node_id} → Hedef: {target_node_id}")
        print(f"Minimum Bant Genişliği: {demand_bandwidth} Mbps")
        print(f"Ağırlıklar: Delay={weight_delay:.2f}, Reliability={weight_reliability:.2f}, Resource={weight_resource:.2f}")
        print(f"Parametreler: {self.num_ants} karınca, {self.num_iterations} iterasyon")
        print(f"{'='*70}\n")
        
        # Ana ACO döngüsü
        for iteration in range(self.num_iterations):
            ant_solutions = []
            
            # Her karınca bir çözüm oluşturur
            for ant_id in range(self.num_ants):
                path = self._construct_ant_solution(
                    source_node_id, target_node_id, demand_bandwidth,
                    weight_delay, weight_reliability, weight_resource
                )
                
                if path is not None:
                    cost = self._calculate_path_fitness(path, weight_delay, 
                                                        weight_reliability, weight_resource)
                    ant_solutions.append((path, cost))
                    
                    # Global en iyi çözümü güncelle
                    if cost < self.best_cost:
                        self.best_cost = cost
                        self.best_solution = path
                        iterations_without_improvement = 0
                        
                        print(f"✨ İterasyon {iteration}: Yeni en iyi çözüm bulundu! Maliyet: {cost:.6f}")
            
            # Feromon güncelleme
            self._evaporate_pheromones()
            self._deposit_pheromones(ant_solutions)
            
            # İlerleme takibi
            iteration_history.append((iteration, self.best_cost, len(ant_solutions)))
            
            # Periyodik rapor
            if iteration % 20 == 0 and iteration > 0:
                valid_solutions = len(ant_solutions)
                avg_cost = np.mean([c for _, c in ant_solutions]) if ant_solutions else float('inf')
                print(f"İterasyon {iteration}: En İyi={self.best_cost:.6f}, "
                      f"Ortalama={avg_cost:.6f}, Geçerli Çözüm={valid_solutions}/{self.num_ants}")
            
            # Erken durdurma kontrolü
            if len(ant_solutions) == 0:
                iterations_without_improvement += 1
            elif self.best_solution is not None:
                iterations_without_improvement += 1
            
            if iterations_without_improvement >= self.early_stop_threshold:
                print(f"\n⚠️  {self.early_stop_threshold} iterasyon boyunca iyileşme olmadı. Algoritma sonlandırılıyor.")
                break
        
        # Sonuç raporu
        print(f"\n{'='*70}")
        if self.best_solution is not None:
            delay, rel_cost, res_cost = self._compute_path_metrics(self.best_solution)
            
            print(f"✅ BAŞARILI! Optimal Rota Bulundu")
            print(f"{'='*70}")
            print(f"Rota: {' → '.join(map(str, self.best_solution))}")
            print(f"Toplam Maliyet: {self.best_cost:.6f}")
            print(f"\nDetaylı Metrikler:")
            print(f"  • Toplam Gecikme: {delay:.3f} ms")
            print(f"  • Güvenilirlik Maliyeti: {rel_cost:.6f}")
            print(f"  • Kaynak Maliyeti: {res_cost:.6f}")
            print(f"  • Rota Uzunluğu: {len(self.best_solution)} düğüm")
            print(f"  • Tamamlanan İterasyon: {iteration + 1}")
        else:
            print(f"❌ BAŞARISIZ! Uygun Rota Bulunamadı")
            print(f"{'='*70}")
            print(f"Kaynak {source_node_id} ile Hedef {target_node_id} arasında")
            print(f"{demand_bandwidth} Mbps bant genişliği ile geçerli yol bulunamadı.")
        
        print(f"{'='*70}\n")
        
        return self.best_solution, self.best_cost

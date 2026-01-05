"""
BSM307 - Güz 2025 - Dönem Projesi
Karınca Kolonisi Optimizasyonu (Ant Colony Optimization - ACO)
QoS Odaklı Çok Amaçlı Ağ Rotalama

Bu modül, 250 düğümlü ağ topolojisi üzerinde optimal rotalar bulur.

Optimize edilen metrikler (Bölüm 3):
1. Minimum Gecikme: TotalDelay = Σ LinkDelay + Σ ProcessingDelay
2. Maximum Güvenilirlik: ReliabilityCost = Σ[-log(Reliability)]
3. Minimum Kaynak: ResourceCost = Σ[1000/Bandwidth]

Yazar: Grup 12
Tarih: Aralık 2025
"""

import random
import numpy as np
import networkx as nx
from collections import defaultdict


class ACO:
    """
    Ant Colony Optimization - Karınca Kolonisi Optimizasyonu
    
    Karıncalar feromon bırakarak iyi yolları işaretler.
    Diğer karıncalar bu feromonlara göre karar verir.
    """
    
    def __init__(self, network_topology):
        """
        ACO başlat
        
        Args:
            network_topology: NetworkTopology sınıfı (main.py'den)
        """
        # Ağ yapısını sakla
        self.network = network_topology
        self.graph = network_topology.G  # NetworkX grafiği
        self.nodes = network_topology.nodes  # Düğüm özellikleri
        
        # Feromon haritası: her kenar için τ değeri
        self.pheromone_map = defaultdict(lambda: 1.0)
        
        # En iyi çözüm
        self.best_solution = None
        self.best_cost = float('inf')
        
        # ACO parametreleri (varsayılan değerler)
        self.num_ants = 50  # Karınca sayısı
        self.num_iterations = 100  # İterasyon sayısı
        self.evaporation_rate = 0.15  # Buharlaşma oranı (ρ)
        self.pheromone_constant = 100.0  # Feromon sabiti (Q)
        self.alpha = 1.2  # Feromon etkisi (α)
        self.beta = 2.5   # Heuristic etkisi (β)
        self.early_stop_threshold = 25  # Erken durdurma
    
    def set_configurations(self, ants=50, iterations=100, evaporation=0.15,
                          pheromone_constant=100.0, alpha=1.2, beta=2.5, 
                          early_stop_threshold=25):
        """
        ACO parametrelerini ayarla
        
        Args:
            ants: Karınca sayısı
            iterations: İterasyon sayısı
            evaporation: Buharlaşma oranı (0-1)
            pheromone_constant: Feromon sabiti
            alpha: Feromon etkisi
            beta: Heuristic etkisi
            early_stop_threshold: Erken durdurma eşiği
        """
        self.num_ants = ants
        self.num_iterations = iterations
        self.evaporation_rate = evaporation
        self.pheromone_constant = pheromone_constant
        self.alpha = alpha
        self.beta = beta
        self.early_stop_threshold = early_stop_threshold
    
    def _reset_pheromones(self):
        """Tüm feromonları τ₀ = 1.0 yap"""
        self.pheromone_map.clear()
        self.pheromone_map = defaultdict(lambda: 1.0)
    
    def _compute_path_metrics(self, path):
        """
        Rotanın metriklerini hesapla (Bölüm 3)
        
        1. TotalDelay = Σ LinkDelay + Σ ProcessingDelay (S ve D hariç)
        2. ReliabilityCost = Σ[-log(Reliability)]
        3. ResourceCost = Σ[1000/Bandwidth]
        
        Args:
            path: Rota [n1, n2, ..., nk]
            
        Returns:
            tuple: (delay, reliability_cost, resource_cost)
        """
        if not path or len(path) < 2:
            return float('inf'), float('inf'), float('inf')
        
        total_delay = 0.0
        reliability_cost = 0.0
        resource_cost = 0.0
        
        # KENAR METRİKLERİ
        for i in range(len(path) - 1):
            current = path[i]
            next_node = path[i + 1]
            
            # Kenar var mı kontrol
            if not self.graph.has_edge(current, next_node):
                return float('inf'), float('inf'), float('inf')
            
            edge = self.graph[current][next_node]
            
            # Gecikme
            total_delay += edge['delay']
            
            # Güvenilirlik (-log transform)
            reliability_cost += -np.log(max(edge['reliability'], 1e-10))
            
            # Kaynak (1000/Bandwidth)
            resource_cost += 1000.0 / max(edge['bandwidth'], 1e-10)
        
        # DÜĞÜM METRİKLERİ (S ve D hariç)
        for idx, node in enumerate(path):
            if idx == 0 or idx == len(path) - 1:
                continue  # Kaynak ve hedef atla
            
            # İşlem gecikmesi
            total_delay += self.nodes[node][0]
            
            # Düğüm güvenilirliği
            reliability_cost += -np.log(max(self.nodes[node][1], 1e-10))
        
        return total_delay, reliability_cost, resource_cost
    
    def _calculate_path_fitness(self, path, w_delay, w_reliability, w_resource):
        """
        Rotanın toplam maliyetini hesapla (Bölüm 4)
        
        TotalCost = W_delay × Delay + W_reliability × ReliabilityCost + W_resource × ResourceCost
        
        Args:
            path: Rota
            w_delay, w_reliability, w_resource: Ağırlıklar
            
        Returns:
            float: Toplam maliyet
        """
        delay, rel_cost, res_cost = self._compute_path_metrics(path)
        
        if delay == float('inf'):
            return float('inf')
        
        # Ağırlıklı toplam
        total_cost = (w_delay * delay + 
                     w_reliability * rel_cost + 
                     w_resource * res_cost)
        
        return total_cost
    
    def _compute_edge_heuristic(self, from_node, to_node, w_delay, w_reliability, w_resource):
        """
        Kenar heuristic'i hesapla: η = 1 / edge_cost
        
        Düşük maliyet = yüksek heuristic = daha çekici
        
        Args:
            from_node, to_node: Kenar
            w_delay, w_reliability, w_resource: Ağırlıklar
            
        Returns:
            float: Heuristic değeri (η)
        """
        if not self.graph.has_edge(from_node, to_node):
            return 0.0
        
        edge = self.graph[from_node][to_node]
        
        # Kenar maliyeti hesapla
        delay = edge['delay']
        rel_cost = -np.log(max(edge['reliability'], 1e-10))
        res_cost = 1000.0 / max(edge['bandwidth'], 1e-10)
        
        edge_cost = (w_delay * delay + 
                    w_reliability * rel_cost + 
                    w_resource * res_cost)
        
        # Heuristic = 1/cost
        return 1.0 / (edge_cost + 1e-10)
    
    def _get_feasible_neighbors(self, current_node, visited_nodes, min_bandwidth):
        """
        Gidilebilecek geçerli komşuları bul
        
        Geçerli komşu:
        1. Ziyaret edilmemiş
        2. Yeterli bant genişliği var
        
        Args:
            current_node: Şu anki düğüm
            visited_nodes: Ziyaret edilmiş düğümler
            min_bandwidth: Minimum bant genişliği
            
        Returns:
            list: Geçerli komşular
        """
        feasible = []
        
        for neighbor in self.graph.neighbors(current_node):
            # Zaten ziyaret edilmiş mi?
            if neighbor in visited_nodes:
                continue
            
            # Bant genişliği yeterli mi?
            bw = self.graph[current_node][neighbor]['bandwidth']
            if bw >= min_bandwidth:
                feasible.append(neighbor)
        
        return feasible
    
    def _select_next_node(self, current_node, feasible_neighbors, visited_nodes,
                         w_delay, w_reliability, w_resource):
        """
        Bir sonraki düğümü seç (ACO formülü)
        
        P(i→j) = [τ^α × η^β] / Σ[τ^α × η^β]
        
        τ: feromon, η: heuristic, α: feromon etkisi, β: heuristic etkisi
        
        Args:
            current_node: Şu anki düğüm
            feasible_neighbors: Geçerli komşular
            visited_nodes: Ziyaret edilmiş düğümler
            w_delay, w_reliability, w_resource: Ağırlıklar
            
        Returns:
            int: Seçilen düğüm veya None
        """
        if not feasible_neighbors:
            return None
        
        probabilities = []
        
        # Her komşu için çekicilik hesapla
        for neighbor in feasible_neighbors:
            # Feromon (τ)
            tau = self.pheromone_map[(current_node, neighbor)]
            
            # Heuristic (η)
            eta = self._compute_edge_heuristic(current_node, neighbor,
                                              w_delay, w_reliability, w_resource)
            
            # Çekicilik: τ^α × η^β
            attractiveness = (tau ** self.alpha) * (eta ** self.beta)
            probabilities.append(attractiveness)
        
        # Normalize et
        total = sum(probabilities)
        if total == 0:
            return random.choice(feasible_neighbors)
        
        normalized = [p / total for p in probabilities]
        
        # Roulette wheel selection
        selected = random.choices(feasible_neighbors, weights=normalized, k=1)[0]
        
        return selected
    
    def _construct_ant_solution(self, source, target, min_bandwidth,
                                w_delay, w_reliability, w_resource, max_steps=500):
        """
        Karınca için rota oluştur
        
        1. Kaynak'tan başla
        2. Her adımda feromon ve heuristic'e göre düğüm seç
        3. Hedefe ulaş veya çıkmaza gir
        
        Args:
            source: Kaynak düğüm
            target: Hedef düğüm
            min_bandwidth: Minimum bant genişliği
            w_delay, w_reliability, w_resource: Ağırlıklar
            max_steps: Maksimum adım (sonsuz döngü önleme)
            
        Returns:
            list veya None: Rota veya None (başarısız)
        """
        current = source
        path = [source]
        visited = {source}
        steps = 0
        
        while current != target and steps < max_steps:
            steps += 1
            
            # Gidilebilecek komşuları bul
            neighbors = self._get_feasible_neighbors(current, visited, min_bandwidth)
            
            if not neighbors:
                return None  # Çıkmaz sokak
            
            # Bir sonraki düğümü seç
            next_node = self._select_next_node(current, neighbors, visited,
                                              w_delay, w_reliability, w_resource)
            
            if next_node is None:
                return None
            
            # Yolu güncelle
            path.append(next_node)
            visited.add(next_node)
            current = next_node
        
        # Hedefe ulaşıldı mı?
        if current == target:
            return path
        
        return None
    
    def _evaporate_pheromones(self):
        """
        Feromonları buharlaştır: τ ← (1-ρ) × τ
        
        Eski bilgileri unutmak için.
        """
        keys = list(self.pheromone_map.keys())
        
        for edge in keys:
            self.pheromone_map[edge] *= (1.0 - self.evaporation_rate)
            
            # Minimum feromon
            if self.pheromone_map[edge] < 0.01:
                self.pheromone_map[edge] = 0.01
    
    def _deposit_pheromones(self, ant_solutions):
        """
        Feromon bırak: Δτ = Q / cost
        
        Düşük maliyetli yollar daha fazla feromon alır.
        
        Args:
            ant_solutions: [(path, cost), ...]
        """
        for path, cost in ant_solutions:
            if path is None or cost == float('inf'):
                continue
            
            # Bırakılacak feromon miktarı
            amount = self.pheromone_constant / (cost + 1e-10)
            
            # Yol üzerindeki kenarlara feromon ekle
            for i in range(len(path) - 1):
                from_node = path[i]
                to_node = path[i + 1]
                
                # İki yönlü güncelleme (undirected graph)
                self.pheromone_map[(from_node, to_node)] += amount
                self.pheromone_map[(to_node, from_node)] += amount
    
    def optimize(self, source_node_id: int, target_node_id: int, demand_bandwidth: int,
                weight_delay=0.33, weight_reliability=0.33, weight_resource=0.34):
        """
        ACO algoritmasını çalıştır ve optimal rota bul
        
        Ana döngü:
        1. Her karınca bir rota oluşturur
        2. Feromonlar buharlaştırılır
        3. Karıncalar feromon bırakır
        4. En iyi çözüm güncellenir
        
        Args:
            source_node_id: Kaynak düğüm
            target_node_id: Hedef düğüm
            demand_bandwidth: Minimum bant genişliği (Mbps)
            weight_delay: Gecikme ağırlığı
            weight_reliability: Güvenilirlik ağırlığı
            weight_resource: Kaynak ağırlığı
            
        Returns:
            tuple: (best_path, best_cost) veya (None, None)
        """
        # BAŞLANGIÇ
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
        
        # ANA DÖNGÜ
        for iteration in range(self.num_iterations):
            ant_solutions = []
            
            # HER KARINCA BİR ROTA OLUŞTUR
            for ant_id in range(self.num_ants):
                path = self._construct_ant_solution(
                    source_node_id, target_node_id, demand_bandwidth,
                    weight_delay, weight_reliability, weight_resource
                )
                
                if path is not None:
                    cost = self._calculate_path_fitness(path, weight_delay, 
                                                        weight_reliability, weight_resource)
                    ant_solutions.append((path, cost))
                    
                    # EN İYİ ÇÖZÜMÜ GÜNCELLE
                    if cost < self.best_cost:
                        self.best_cost = cost
                        self.best_solution = path
                        iterations_without_improvement = 0
                        
                        print(f"✨ İterasyon {iteration}: Yeni en iyi çözüm bulundu! Maliyet: {cost:.6f}")
            
            # FEROMON GÜNCELLEMESİ
            self._evaporate_pheromones()  # Buharlaşma
            self._deposit_pheromones(ant_solutions)  # Bırakma
            
            # İLERLEME TAKİBİ
            iteration_history.append((iteration, self.best_cost, len(ant_solutions)))
            
            # Her iterasyonda kısa rapor
            if len(ant_solutions) > 0:
                avg_cost = np.mean([c for _, c in ant_solutions])
                print(f"İter {iteration}: Best={self.best_cost:.4f} | "
                      f"Avg={avg_cost:.4f} | Valid={len(ant_solutions)}/{self.num_ants}")
            
            # Detaylı rapor (her 10 iterasyon)
            if iteration % 10 == 0 and iteration > 0:
                print(f"  → İterasyon {iteration} Özet: En İyi Maliyet = {self.best_cost:.6f}")
            
            # ERKEN DURDURMA
            if len(ant_solutions) == 0:
                iterations_without_improvement += 1
            elif self.best_solution is not None:
                iterations_without_improvement += 1
            
            if iterations_without_improvement >= self.early_stop_threshold:
                print(f"\n⚠️  {self.early_stop_threshold} iterasyon boyunca iyileşme olmadı. "
                      f"Algoritma sonlandırılıyor.")
                break
        
        # SONUÇ RAPORU
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
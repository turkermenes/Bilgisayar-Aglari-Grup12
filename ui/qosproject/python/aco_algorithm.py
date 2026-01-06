#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ACO Routing (standalone module)
"""

import time
import random
from dataclasses import dataclass
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import numpy as np
import networkx as nx

EPS = 1e-12


def build_graph(nodes_df, edges_df) -> nx.Graph:
    """
    Arayüz/CSV katmanından gelen DataFrame'lerden NetworkX Graph üretir.
    Bu graph; ACO/GA/solver tarafında ortak kullanılabilecek şekilde hem "core"
    alanları hem de farklı modüllerle uyum için alias alanları içerir.
    """

    # CSV kolon isimlerini normalize eder 
    def norm_col(c: str) -> str:
        return str(c).replace("\ufeff", "").strip().lower()

    # Olası kolon isimleri arasından mevcut olan ilkini seçer 
    def pick(colmap, *names):
        for n in names:
            if n in colmap:
                return colmap[n]
        return None

    G = nx.Graph()

    # DataFrame kolonlarını normalize edilmiş bir haritada toplar
    ncols = {norm_col(c): c for c in nodes_df.columns}
    ecols = {norm_col(c): c for c in edges_df.columns}

   
    # node_id zorunlu; s_ms ve r_node yoksa varsayılan değerler kullanılır
    node_id_col = pick(ncols, "node_id", "id")
    s_col = pick(ncols, "s_ms", "processing_delay", "node_delay_ms")
    rnode_col = pick(ncols, "r_node", "node_reliability", "reliability")

    if node_id_col is None:
        raise ValueError("nodes_df must contain 'node_id' column (or equivalent).")

    # Düğümleri ekler: core anahtarlar + arayüz/diğer modüller için alias anahtarlar
    for _, row in nodes_df.iterrows():
        nid = int(row[node_id_col])
        s_ms = float(row[s_col]) if s_col is not None else 0.0
        r_node = float(row[rnode_col]) if rnode_col is not None else 1.0

        G.add_node(
            nid,
            # core keys 
            processing_delay=s_ms,
            node_reliability=r_node,
            # aliases
            s_ms=s_ms,
            r_node=r_node,
            node_delay_ms=s_ms,
        )

    # --- Edge schema eşleme (CSV/arayüz uyumluluğu) ---
    src_col = pick(ecols, "src", "source", "from")
    dst_col = pick(ecols, "dst", "target", "to")
    cap_col = pick(ecols, "capacity_mbps", "bandwidth_mbps", "bandwidth", "capacity", "bw")
    d_col = pick(ecols, "delay_ms", "link_delay_ms", "delay", "latency")
    rlink_col = pick(ecols, "r_link", "link_reliability", "reliability", "rel", "availability")

    if src_col is None or dst_col is None:
        raise ValueError("edges_df must contain 'src' and 'dst' columns (or equivalent).")
    if cap_col is None or d_col is None or rlink_col is None:
        raise ValueError(
            "edges_df must contain capacity/bandwidth, delay, reliability columns "
            "(e.g., capacity_mbps, delay_ms, r_link)."
        )

    # Linkleri ekler: core anahtarlar + alias anahtarlar
    for _, row in edges_df.iterrows():
        u = int(row[src_col])
        v = int(row[dst_col])
        bw = float(row[cap_col])
        delay = float(row[d_col])
        rel = float(row[rlink_col])

        # Edge uçları node tablosunda yoksa varsayılan node değerleriyle ekle
        if u not in G:
            G.add_node(u, processing_delay=0.0, node_reliability=1.0, s_ms=0.0, r_node=1.0, node_delay_ms=0.0)
        if v not in G:
            G.add_node(v, processing_delay=0.0, node_reliability=1.0, s_ms=0.0, r_node=1.0, node_delay_ms=0.0)

        G.add_edge(
            u, v,
            # core keys
            bandwidth=bw,
            delay=delay,
            reliability=rel,
            # aliases
            capacity_mbps=bw,
            bandwidth_mbps=bw,
            link_delay_ms=delay,
            delay_ms=delay,
            r_link=rel,
            link_reliability=rel,
        )

    return G


def compute_metrics_for_path(
    G: nx.Graph,
    path: List[int],
    include_processing_for_ends: bool = False
) -> Tuple[float, float, float]:
    """
    Solver/arayüz raporlaması için path metriklerini ortak bir fonksiyonda hesaplar.

    Amaç: farklı modüllerde farklı attribute isimleri kullanılsa bile KeyError olmadan
    delay/reliability/resource değerlerini toplayabilmek (alias destekli).
    """

    # Edge üzerinde birden fazla olası anahtar adı olabilir
    def get_edge(u, v, *keys, default=None):
        data = G[u][v]
        for k in keys:
            if k in data:
                return data[k]
        return default

    # Node üzerinde birden fazla olası anahtar adı olabilir 
    def get_node(n, *keys, default=None):
        data = G.nodes[n]
        for k in keys:
            if k in data:
                return data[k]
        return default

    # Geçersiz/boş yol durumunda 0 döndürerek üst katmanda kolay yönetim sağlar
    if not path or len(path) < 2:
        return 0.0, 0.0, 0.0

    delay_ms = 0.0
    rel_cost = 0.0
    res_cost = 0.0

    # Link metrikleri: delay + (-log reliability) + 1000/bw
    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]

        d = get_edge(u, v, "link_delay_ms", "delay_ms", "delay", default=0.0)
        delay_ms += float(d)

        r = get_edge(u, v, "link_reliability", "r_link", "reliability", default=1.0)
        r = max(float(r), EPS)
        rel_cost += float(-np.log(r))

        bw = get_edge(u, v, "capacity_mbps", "bandwidth_mbps", "bandwidth", default=EPS)
        bw = max(float(bw), EPS)
        res_cost += float(1000.0 / bw)

    # Node metrikleri: genelde uçlar hariç processing delay eklenir
    start_idx = 0 if include_processing_for_ends else 1
    end_idx = len(path) if include_processing_for_ends else (len(path) - 1)

    for i in range(start_idx, end_idx):
        n = path[i]

        nd = get_node(n, "processing_delay", "s_ms", "node_delay_ms", default=0.0)
        delay_ms += float(nd)

        nr = get_node(n, "node_reliability", "r_node", default=1.0)
        nr = max(float(nr), EPS)
        rel_cost += float(-np.log(nr))

    return float(delay_ms), float(rel_cost), float(res_cost)


@dataclass
class ACOResult:
    best_path: Optional[List[int]]
    best_cost: float
    delay_ms: float
    rel_cost: float
    res_cost: float
    time_sec: float


class ACO:
    def __init__(
        self,
        G: nx.Graph,
        w_delay: float = 0.33,
        w_rel: float = 0.33,
        w_res: float = 0.34,
        n_ants: int = 50,
        n_iter: int = 100,
        alpha: float = 1.2,
        beta: float = 2.5,
        rho: float = 0.15,
        q: float = 100.0,
        capacity_aware: bool = True,
    ):
        self.graph = G
        self.nodes: Dict[int, Tuple[float, float]] = {}
        for n in self.graph.nodes:
            pd = float(self.graph.nodes[n].get("processing_delay", self.graph.nodes[n].get("s_ms", 0.0)))
            nr = float(self.graph.nodes[n].get("node_reliability", self.graph.nodes[n].get("r_node", 1.0)))
            self.nodes[n] = (pd, nr)

        self.pheromone_map = defaultdict(lambda: 1.0)
        self.best_solution: Optional[List[int]] = None
        self.best_cost: float = float("inf")

        self.w_delay = float(w_delay)
        self.w_reliability = float(w_rel)
        self.w_resource = float(w_res)

        self.num_ants = int(n_ants)
        self.num_iterations = int(n_iter)
        self.evaporation_rate = float(rho)
        self.pheromone_constant = float(q)
        self.alpha = float(alpha)
        self.beta = float(beta)
        self.early_stop_threshold = 25

        self.capacity_aware = bool(capacity_aware)

    def set_configurations(
        self,
        ants: int = 50,
        iterations: int = 100,
        evaporation: float = 0.15,
        pheromone_constant: float = 100.0,
        alpha: float = 1.2,
        beta: float = 2.5,
        early_stop_threshold: int = 25
    ):
        self.num_ants = int(ants)
        self.num_iterations = int(iterations)
        self.evaporation_rate = float(evaporation)
        self.pheromone_constant = float(pheromone_constant)
        self.alpha = float(alpha)
        self.beta = float(beta)
        self.early_stop_threshold = int(early_stop_threshold)

    def _reset_pheromones(self):
        self.pheromone_map.clear()
        self.pheromone_map = defaultdict(lambda: 1.0)

    def _compute_path_metrics(self, path: List[int]) -> Tuple[float, float, float]:
        if not path or len(path) < 2:
            return float("inf"), float("inf"), float("inf")

        total_delay = 0.0
        reliability_cost = 0.0
        resource_cost = 0.0

        for i in range(len(path) - 1):
            current_node = path[i]
            next_node = path[i + 1]

            if not self.graph.has_edge(current_node, next_node):
                return float("inf"), float("inf"), float("inf")

            edge_data = self.graph[current_node][next_node]

            total_delay += edge_data["delay"]

            link_reliability = edge_data["reliability"]
            reliability_cost += -np.log(max(link_reliability, 1e-10))

            bandwidth = edge_data["bandwidth"]
            resource_cost += 1000.0 / max(bandwidth, 1e-10)

        for idx, node in enumerate(path):
            if idx == 0 or idx == len(path) - 1:
                continue

            processing_delay = self.nodes[node][0]
            node_reliability = self.nodes[node][1]

            total_delay += processing_delay
            reliability_cost += -np.log(max(node_reliability, 1e-10))

        return total_delay, reliability_cost, resource_cost

    def _calculate_path_fitness(self, path: List[int], w_delay: float, w_reliability: float, w_resource: float) -> float:
        delay, rel_cost, res_cost = self._compute_path_metrics(path)
        if delay == float("inf"):
            return float("inf")
        return (w_delay * delay + w_reliability * rel_cost + w_resource * res_cost)

    def _compute_edge_heuristic(self, from_node: int, to_node: int, w_delay: float, w_reliability: float, w_resource: float) -> float:
        if not self.graph.has_edge(from_node, to_node):
            return 0.0

        edge_data = self.graph[from_node][to_node]

        delay = edge_data["delay"]
        rel = edge_data["reliability"]
        bw = edge_data["bandwidth"]

        rel_cost = -np.log(max(rel, 1e-10))
        res_cost = 1000.0 / max(bw, 1e-10)

        edge_cost = (w_delay * delay + w_reliability * rel_cost + w_resource * res_cost)
        return 1.0 / (edge_cost + 1e-10)

    def _get_feasible_neighbors(self, current_node: int, visited_nodes: set, min_bandwidth: float) -> List[int]:
        feasible = []
        for neighbor in self.graph.neighbors(current_node):
            if neighbor in visited_nodes:
                continue
            edge_bandwidth = self.graph[current_node][neighbor]["bandwidth"]
            if edge_bandwidth >= min_bandwidth:
                feasible.append(neighbor)
        return feasible

    def _select_next_node(
        self,
        current_node: int,
        feasible_neighbors: List[int],
        visited_nodes: set,
        w_delay: float,
        w_reliability: float,
        w_resource: float
    ) -> Optional[int]:
        if not feasible_neighbors:
            return None

        probabilities = []
        for neighbor in feasible_neighbors:
            pheromone = self.pheromone_map[(current_node, neighbor)]
            heuristic = self._compute_edge_heuristic(current_node, neighbor, w_delay, w_reliability, w_resource)
            attractiveness = (pheromone ** self.alpha) * (heuristic ** self.beta)
            probabilities.append(attractiveness)

        total = sum(probabilities)
        if total == 0:
            return random.choice(feasible_neighbors)

        normalized_probs = [p / total for p in probabilities]
        return random.choices(feasible_neighbors, weights=normalized_probs, k=1)[0]

    def _construct_ant_solution(
        self,
        source: int,
        target: int,
        min_bandwidth: float,
        w_delay: float,
        w_reliability: float,
        w_resource: float,
        max_steps: int = 500
    ) -> Optional[List[int]]:
        current_node = source
        path = [source]
        visited = {source}
        steps = 0

        while current_node != target and steps < max_steps:
            steps += 1

            feasible_neighbors = self._get_feasible_neighbors(current_node, visited, min_bandwidth)
            if not feasible_neighbors:
                return None

            next_node = self._select_next_node(current_node, feasible_neighbors, visited, w_delay, w_reliability, w_resource)
            if next_node is None:
                return None

            path.append(next_node)
            visited.add(next_node)
            current_node = next_node

        if current_node == target:
            return path

        return None

    def _evaporate_pheromones(self):
        keys_to_update = list(self.pheromone_map.keys())
        for edge in keys_to_update:
            self.pheromone_map[edge] *= (1.0 - self.evaporation_rate)
            if self.pheromone_map[edge] < 0.01:
                self.pheromone_map[edge] = 0.01

    def _deposit_pheromones(self, ant_solutions: List[Tuple[Optional[List[int]], float]]):
        for path, cost in ant_solutions:
            if path is None or cost == float("inf"):
                continue

            pheromone_amount = self.pheromone_constant / (cost + 1e-10)

            for i in range(len(path) - 1):
                from_node = path[i]
                to_node = path[i + 1]

                self.pheromone_map[(from_node, to_node)] += pheromone_amount
                self.pheromone_map[(to_node, from_node)] += pheromone_amount

    def run_one(
        self,
        source: int,
        target: int,
        demand_mbps: float,
        include_processing_for_ends: bool = False,
        show_progress: bool = False
    ) -> ACOResult:
        t0 = time.time()

        self._reset_pheromones()
        self.best_solution = None
        self.best_cost = float("inf")

        iterations_without_improvement = 0

        for iteration in range(self.num_iterations):
            ant_solutions = []

            for _ant_id in range(self.num_ants):
                path = self._construct_ant_solution(
                    source, target, demand_mbps,
                    self.w_delay, self.w_reliability, self.w_resource
                )

                if path is not None:
                    cost = self._calculate_path_fitness(path, self.w_delay, self.w_reliability, self.w_resource)
                    ant_solutions.append((path, cost))

                    if cost < self.best_cost:
                        self.best_cost = cost
                        self.best_solution = path
                        iterations_without_improvement = 0

                        if show_progress:
                            print(f"Iteration {iteration}: New best cost = {cost:.6f}")

            self._evaporate_pheromones()
            self._deposit_pheromones(ant_solutions)

            if len(ant_solutions) == 0:
                iterations_without_improvement += 1
            elif self.best_solution is not None:
                iterations_without_improvement += 1

            if iterations_without_improvement >= self.early_stop_threshold:
                if show_progress:
                    print(f"Early stop: no improvement for {self.early_stop_threshold} iterations.")
                break

        if self.best_solution is None:
            t1 = time.time()
            return ACOResult(
                best_path=None,
                best_cost=float("inf"),
                delay_ms=float("inf"),
                rel_cost=float("inf"),
                res_cost=float("inf"),
                time_sec=float(t1 - t0),
            )

        delay_ms, rel_cost, res_cost = compute_metrics_for_path(
            self.graph,
            self.best_solution,
            include_processing_for_ends=include_processing_for_ends
        )

        t1 = time.time()
        return ACOResult(
            best_path=self.best_solution,
            best_cost=float(self.best_cost),
            delay_ms=float(delay_ms),
            rel_cost=float(rel_cost),
            res_cost=float(res_cost),
            time_sec=float(t1 - t0),
        )

    def optimize(
        self,
        source_node_id: int,
        target_node_id: int,
        demand_bandwidth: float,
        weight_delay: float = 0.33,
        weight_reliability: float = 0.33,
        weight_resource: float = 0.34
    ):
        self.w_delay = float(weight_delay)
        self.w_reliability = float(weight_reliability)
        self.w_resource = float(weight_resource)

        res = self.run_one(
            source=source_node_id,
            target=target_node_id,
            demand_mbps=float(demand_bandwidth),
            include_processing_for_ends=False,
            show_progress=True
        )
        return res.best_path, res.best_cost

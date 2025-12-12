#!/usr/bin/env python3
"""
aco_routing_fixed.py

Updated to accept column names:
- nodes CSV: node_id, s_ms, r_node
- edges CSV: src, dst, capacity_mbps, delay_ms, r_link
- demand CSV: src, dst, demand_mbps

Also accepts some common alternative column names.

Requirements:
    pip install pandas networkx numpy tqdm

Usage:
    python aco_routing_fixed.py --nodes NodeData.csv --edges EdgeData.csv --demand DemandData.csv --out results.csv
"""

import argparse
import csv
import math
import random
from collections import defaultdict
from tqdm import trange
import pandas as pd
import networkx as nx
import numpy as np
import time

EPS = 1e-12

# -------------------------
# Helpers for column mapping (robust to slight name differences)
# -------------------------
def choose_col(df, candidates):
    """Return first candidate that exists in df.columns, else raise KeyError."""
    for c in candidates:
        if c in df.columns:
            return c
    raise KeyError(f"None of the expected columns found. Expected one of: {candidates}. Found columns: {list(df.columns)}")

# -------------------------
# Utilities: load CSV -> dataframes
# -------------------------
def load_data(nodes_file, edges_file, demand_file):
    nodes_df = pd.read_csv(nodes_file, sep=';')
    edges_df = pd.read_csv(edges_file, sep=';')
    demand_df = pd.read_csv(demand_file, sep=';')

    return nodes_df, edges_df, demand_df


# -------------------------
# Build graph with robust column lookup
# -------------------------
def build_graph(nodes_df, edges_df):
    G = nx.DiGraph()

    # Node column names (accept alternatives)
    node_id_col = choose_col(nodes_df, ['node_id', 'node-id', 'id', 'nid'])
    proc_col = choose_col(nodes_df, ['s_ms', 's-ms', 'processing_delay_ms', 'processing_delay', 'proc_ms'])
    rnode_col = choose_col(nodes_df, ['r_node', 'r-node', 'node_reliability', 'reliability_node'])

    # Edge column names (accept alternatives)
    src_col = choose_col(edges_df, ['src', 'source'])
    dst_col = choose_col(edges_df, ['dst', 'target', 'dest'])
    cap_col = choose_col(edges_df, ['capacity_mbps', 'capacity-r', 'capacity', 'bandwidth_mbps', 'bandwidth'])
    delay_col = choose_col(edges_df, ['delay_ms', 'dely-ms', 'delay-ms', 'delay', 'link_delay_ms'])
    rlink_col = choose_col(edges_df, ['r_link', 'r-link', 'link_reliability', 'reliability_link'])

    # add nodes
    for _, r in nodes_df.iterrows():
        nid = r[node_id_col]
        try:
            proc = float(r.get(proc_col, 0.0))
        except Exception:
            proc = 0.0
        try:
            nrel = float(r.get(rnode_col, 1.0))
        except Exception:
            nrel = 1.0
        G.add_node(nid,
                   processing_delay_ms=proc,
                   node_reliability=nrel)

    # add edges
    for _, r in edges_df.iterrows():
        src = r[src_col]
        dst = r[dst_col]
        try:
            cap = float(r.get(cap_col, 0.0))
        except Exception:
            cap = 0.0
        try:
            dl = float(r.get(delay_col, 0.0))
        except Exception:
            dl = 0.0
        try:
            lrel = float(r.get(rlink_col, 1.0))
        except Exception:
            lrel = 1.0

        # add edge (directed). If your network is undirected, you can also add reverse
        G.add_edge(src, dst,
                   bandwidth_mbps=cap,
                   link_delay_ms=dl,
                   link_reliability=lrel)
    return G

# -------------------------
# Metric calculations for a path P (list of nodes)
# -------------------------
def compute_metrics_for_path(G, path, include_processing_for_ends=False):
    total_delay = 0.0
    reliability_cost = 0.0
    resource_cost = 0.0

    # edges
    for u, v in zip(path[:-1], path[1:]):
        e = G.edges[u, v]
        total_delay += float(e['link_delay_ms'])
        bw_gbps = float(e['bandwidth_mbps']) / 1000.0
        resource_cost += 1.0 / (bw_gbps + EPS)
        rel = float(e['link_reliability'])
        reliability_cost += -math.log(max(rel, EPS))

    # nodes processing delay and node reliability
    for i, n in enumerate(path):
        if (i == 0 or i == len(path)-1) and not include_processing_for_ends:
            continue
        proc = float(G.nodes[n].get('processing_delay_ms', 0.0))
        total_delay += proc
        nrel = float(G.nodes[n].get('node_reliability', 1.0))
        reliability_cost += -math.log(max(nrel, EPS))

    return total_delay, reliability_cost, resource_cost

# -------------------------
# edge_cost used in ACO heuristic
# -------------------------
def edge_cost(G, u, v, w_delay, w_rel, w_res):
    e = G.edges[u, v]
    delay = float(e['link_delay_ms'])
    rel_cost = -math.log(max(float(e['link_reliability']), EPS))
    bw_gbps = float(e['bandwidth_mbps']) / 1000.0
    res_cost = 1.0 / (bw_gbps + EPS)
    return w_delay * delay + w_rel * rel_cost + w_res * res_cost

# -------------------------
# ACO class (same as before, minor adjustments)
# -------------------------
class ACO:
    def __init__(self, G, w_delay=0.5, w_rel=0.25, w_res=0.25,
                 n_ants=30, n_iter=200, alpha=1.0, beta=2.0, rho=0.1, q=1.0,
                 capacity_aware=True):
        self.G = G
        self.w_delay = w_delay
        self.w_rel = w_rel
        self.w_res = w_res
        self.n_ants = n_ants
        self.n_iter = n_iter
        self.alpha = alpha
        self.beta = beta
        self.rho = rho
        self.q = q
        self.capacity_aware = capacity_aware

        self.pheromone = {}
        for u, v in G.edges():
            self.pheromone[(u, v)] = 1.0

    def _heuristic(self, u, v):
        c = edge_cost(self.G, u, v, self.w_delay, self.w_rel, self.w_res)
        return 1.0 / (c + EPS)

    def _possible_neighbors(self, current, visited, demand_mbps=None):
        neighbors = []
        for nb in self.G.successors(current):
            if demand_mbps is not None and self.capacity_aware:
                if float(self.G.edges[current, nb].get('bandwidth_mbps', 0.0)) + 1e-9 < demand_mbps:
                    continue
            if nb in visited:
                continue
            neighbors.append(nb)
        return neighbors

    def _construct_path(self, s, d, demand_mbps=None, max_hops=500):
        current = s
        path = [s]
        visited = set([s])
        hops = 0
        while current != d and hops < max_hops:
            hops += 1
            neighbors = self._possible_neighbors(current, visited, demand_mbps)
            if not neighbors:
                return None
            probs = []
            for nb in neighbors:
                tau = self.pheromone.get((current, nb), 1e-9)
                eta = self._heuristic(current, nb)
                probs.append((tau ** self.alpha) * (eta ** self.beta))
            ssum = sum(probs)
            probs = [p / (ssum + EPS) for p in probs]
            next_node = random.choices(neighbors, weights=probs, k=1)[0]
            path.append(next_node)
            visited.add(next_node)
            current = next_node
        if current == d:
            return path
        return None

    def run(self, s, d, demand_mbps=None, include_processing_for_ends=False, verbose=False):
        best_path = None
        best_total_cost = float('inf')
        history = []
        start_time = time.time()

        for it in trange(self.n_iter, desc="ACO iter"):
            paths = []
            costs = []
            for ant in range(self.n_ants):
                p = self._construct_path(s, d, demand_mbps)
                if p is None:
                    continue
                delay, rel_cost, res_cost = compute_metrics_for_path(self.G, p, include_processing_for_ends)
                total_cost = self.w_delay * delay + self.w_rel * rel_cost + self.w_res * res_cost
                paths.append(p)
                costs.append((total_cost, delay, rel_cost, res_cost))
                if total_cost < best_total_cost:
                    best_total_cost = total_cost
                    best_path = (p, total_cost, delay, rel_cost, res_cost)

            for e in list(self.pheromone.keys()):
                self.pheromone[e] *= (1.0 - self.rho)
                if self.pheromone[e] < 1e-12:
                    self.pheromone[e] = 1e-12

            for p, ctuple in zip(paths, costs):
                total_cost = ctuple[0]
                deposit = self.q / (total_cost + EPS)
                for u, v in zip(p[:-1], p[1:]):
                    self.pheromone[(u, v)] = self.pheromone.get((u, v), 0.0) + deposit

            history.append((it, best_total_cost))

        run_time = time.time() - start_time
        return {
            'best_path': best_path,
            'best_cost': best_total_cost,
            'time': run_time,
            'history': history,
            'pheromone': self.pheromone
        }

# -------------------------
# CLI main
# -------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--nodes', required=True)
    parser.add_argument('--edges', required=True)
    parser.add_argument('--demand', required=True)
    parser.add_argument('--out', default='aco_results.csv')
    parser.add_argument('--ants', type=int, default=30)
    parser.add_argument('--iter', type=int, default=200)
    parser.add_argument('--wd', type=float, default=0.5)
    parser.add_argument('--wr', type=float, default=0.25)
    parser.add_argument('--wc', type=float, default=0.25)
    args = parser.parse_args()

    nodes_df, edges_df, demand_df = load_data(args.nodes, args.edges, args.demand)
    try:
        G = build_graph(nodes_df, edges_df)
    except KeyError as e:
        print("Column error when building graph:", e)
        print("Nodes CSV columns:", list(nodes_df.columns))
        print("Edges CSV columns:", list(edges_df.columns))
        return

    aco = ACO(G,
              w_delay=args.wd,
              w_rel=args.wr,
              w_res=args.wc,
              n_ants=args.ants,
              n_iter=args.iter,
              alpha=1.0, beta=2.0, rho=0.1, q=1.0)

    results_rows = []
    # for each demand (S,D)
    for _, row in demand_df.iterrows():
        s = row['src'] if 'src' in row else row.get('source')
        d = row['dst'] if 'dst' in row else row.get('target')
        demand_mbps = float(row.get('demand_mbps', row.get('demand-mbps', row.get('demand', 0))))
        print(f"\nRunning ACO for S={s} D={d} demand={demand_mbps} Mbps")
        res = aco.run(s, d, demand_mbps=demand_mbps, include_processing_for_ends=False, verbose=True)
        best = res['best_path']
        if best is None:
            print("No path found by ACO")
            results_rows.append({
                'src': s, 'dst': d, 'best_path': None, 'total_cost': None,
                'total_delay_ms': None, 'reliability_cost': None, 'resource_cost': None,
                'time_sec': res['time']
            })
        else:
            path, total_cost, delay, rel_cost, res_cost = best
            results_rows.append({
                'src': s, 'dst': d, 'best_path': "->".join(map(str, path)), 'total_cost': total_cost,
                'total_delay_ms': delay, 'reliability_cost': rel_cost, 'resource_cost': res_cost,
                'time_sec': res['time']
            })
            print("Best path:", path)
            print(f"Delay={delay:.3f}ms rel_cost={rel_cost:.6f} res_cost={res_cost:.6f} total={total_cost:.6f}")

    out_df = pd.DataFrame(results_rows)
    out_df.to_csv(args.out, index=False)
    print(f"\nSaved results to {args.out}")

if __name__ == '__main__':
    main()

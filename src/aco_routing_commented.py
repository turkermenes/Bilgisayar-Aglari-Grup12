#!/usr/bin/env python3
"""
aco_routing.py (LEARNING / EPOCH + ANTI-STAGNATION VERSION)

Bu sürümün ana fikri:
- Tek bir program çalışması içinde "epoch" kavramı ile run-to-run learning sağlamak:
  Feromonlar epoch bitince sıfırlanmaz; bir sonraki epoch'a taşınır.
- Stagnation (tek bir çözüme kilitlenme) azaltmak:
  - deposit sadece global-best değil, iterasyon içindeki top-k iyi yollara yapılır
  - epsilon-greedy keşif vardır ve epoch'lara göre epsilon planlı biçimde azaltılır
  - epoch boyunca iyileşme yoksa reheat ile feromonlar başlangıca yaklaştırılır
- Talep (demand) kapasite kısıtı: bandwidth >= demand olmayan kenarlar kullanılmaz
- Kaynak maliyeti: sum(1000 / bandwidth_mbps)
- Opsiyonel Dijkstra baseline: weighted-sum maliyette kesin optimumu verir (karşılaştırma için)

Gereksinimler:
  pip install pandas networkx numpy tqdm
"""

import argparse
import math
import time
from typing import Dict, Tuple, List, Optional

import pandas as pd
import networkx as nx
import numpy as np
from tqdm import trange

# Sayısal stabilite için çok küçük değer (log(0) vb. önlemek)
EPS = 1e-12


# -------------------- CSV helpers --------------------

def choose_col(df: pd.DataFrame, candidates: List[str]) -> str:
    """
    CSV kolon isimleri farklı olabileceği için (node_id/id vb.),
    aday isimlerden DataFrame'de bulunan ilkini seçer.
    """
    for c in candidates:
        if c in df.columns:
            return c
    raise KeyError(
        f"Beklenen kolon bulunamadı. Adaylar: {candidates}. Bulunan kolonlar: {list(df.columns)}"
    )


def to_float(value, default=1.0) -> float:
    """
    CSV değerlerini güvenli biçimde float'a çevirir.
    Türkiye/Avrupa formatı virgüllü ondalıkları (0,968) noktaya çevirir.
    """
    if pd.isna(value) or value == "":
        return float(default)
    try:
        return float(str(value).replace(",", ".").strip())
    except (ValueError, TypeError):
        return float(default)


def load_data(nodes_file: str, edges_file: str, demand_file: str):
    """Node, Edge, Demand CSV dosyalarını okur."""
    nodes_df = pd.read_csv(nodes_file, sep=";")
    edges_df = pd.read_csv(edges_file, sep=";")
    demand_df = pd.read_csv(demand_file, sep=";")
    return nodes_df, edges_df, demand_df


def build_graph(nodes_df: pd.DataFrame, edges_df: pd.DataFrame) -> nx.Graph:
    """
    NetworkX Graph oluşturur.
    - Node attribute'ları: processing_delay_ms, node_reliability
    - Edge attribute'ları: bandwidth_mbps, link_delay_ms, link_reliability
    """
    G = nx.Graph()

    # Kolon isimlerini esnek seç
    node_id_col = choose_col(nodes_df, ["node_id", "node-id", "id", "nid"])
    proc_col = choose_col(nodes_df, ["s_ms", "s-ms", "processing_delay_ms", "processing_delay", "proc_ms"])
    rnode_col = choose_col(nodes_df, ["r_node", "r-node", "node_reliability", "reliability_node"])

    src_col = choose_col(edges_df, ["src", "source"])
    dst_col = choose_col(edges_df, ["dst", "target", "dest"])
    cap_col = choose_col(edges_df, ["capacity_mbps", "capacity", "bandwidth_mbps", "bandwidth", "bw_mbps"])
    delay_col = choose_col(edges_df, ["delay_ms", "delay", "link_delay_ms"])
    rlink_col = choose_col(edges_df, ["r_link", "r-link", "link_reliability", "reliability_link"])

    # Düğümleri ekle
    for _, r in nodes_df.iterrows():
        nid = int(r[node_id_col])
        proc = to_float(r.get(proc_col), default=0.0)
        nrel = to_float(r.get(rnode_col), default=1.0)
        G.add_node(nid, processing_delay_ms=proc, node_reliability=nrel)

    # Kenarları ekle
    for _, r in edges_df.iterrows():
        u = int(r[src_col])
        v = int(r[dst_col])
        cap = to_float(r.get(cap_col), default=100.0)
        dl = to_float(r.get(delay_col), default=0.0)
        lrel = to_float(r.get(rlink_col), default=1.0)

        G.add_edge(
            u, v,
            bandwidth_mbps=cap,
            link_delay_ms=dl,
            link_reliability=lrel
        )

    return G


def capacity_subgraph(G: nx.Graph, demand_mbps: float) -> nx.Graph:
    """
    Talep edilen bandwidth'i karşılamayan kenarları atar.
    Böylece üretilen yollar otomatik olarak kapasite kısıtına uygun olur.
    """
    demand = float(demand_mbps)
    eligible = [
        (u, v) for u, v, data in G.edges(data=True)
        if float(data.get("bandwidth_mbps", 0.0)) >= demand
    ]
    return G.edge_subgraph(eligible).copy()


# -------------------- Metrics --------------------

def compute_metrics_for_path(G: nx.Graph, path: List[int]) -> Tuple[float, float, float]:
    """
    Bir path için 3 metriği hesaplar:
      - total_delay (ms): link delay + ara node processing delay
      - reliability_cost: sum( -log(node_rel) ) + sum( -log(link_rel) )
      - resource_cost: sum( 1000 / bandwidth_mbps )

    Not: reliability_cost'u böyle tanımlamamızın sebebi:
      Çarpımsal güvenilirliği (r1*r2*...) toplamsal maliyete çevirmek.
    """
    total_delay = 0.0
    reliability_cost = 0.0
    resource_cost = 0.0

    start = path[0]
    end = path[-1]

    # Düğüm katkıları
    for node in path:
        n = G.nodes[node]

        # Düğüm güvenilirliği maliyeti: -log(r)
        n_rel = float(n.get("node_reliability", 1.0))
        reliability_cost += -math.log(max(n_rel, EPS))

        # Processing delay sadece ara düğümlerde (S ve D hariç)
        if node != start and node != end:
            total_delay += float(n.get("processing_delay_ms", 0.0))

    # Kenar katkıları
    for u, v in zip(path[:-1], path[1:]):
        e = G.edges[u, v]

        # Link gecikmesi
        total_delay += float(e.get("link_delay_ms", 0.0))

        # Link güvenilirliği maliyeti: -log(r_link)
        l_rel = float(e.get("link_reliability", 1.0))
        reliability_cost += -math.log(max(l_rel, EPS))

        # Kaynak maliyeti: 1000/bw (bw artarsa maliyet düşer)
        bw = float(e.get("bandwidth_mbps", 1.0))
        resource_cost += 1000.0 / max(bw, EPS)

    return total_delay, reliability_cost, resource_cost


def edge_cost_components(G: nx.Graph, u: int, v: int) -> Tuple[float, float, float]:
    """Tek bir kenar için (delay_ms, rel_cost, res_cost) döndürür."""
    e = G.edges[u, v]
    delay = float(e.get("link_delay_ms", 0.0))
    rel_cost = -math.log(max(float(e.get("link_reliability", 1.0)), EPS))
    bw = float(e.get("bandwidth_mbps", 1.0))
    res_cost = 1000.0 / max(bw, EPS)
    return delay, rel_cost, res_cost


def total_cost_from_metrics(wd: float, wr: float, wc: float, delay: float, rel_cost: float, res_cost: float) -> float:
    """3 metriği ağırlıklı toplam maliyete çevirir."""
    return wd * delay + wr * rel_cost + wc * res_cost


# -------------------- Dijkstra baseline (weighted-sum kesin optimum) --------------------

def dijkstra_optimal_path(G: nx.Graph, s: int, d: int, demand_mbps: float, wd: float, wr: float, wc: float):
    """
    Weighted-sum maliyet fonksiyonu additive olduğu için Dijkstra ile kesin optimum bulunabilir.

    Trick:
    - Kenar maliyeti: wd*link_delay + wr*(-log link_rel) + wc*(1000/bw)
    - Düğüm maliyeti: wr*(-log node_rel)
    - Ara düğüm processing delay: wd*proc_delay (D hedefinde genelde eklenmez)

    Bu fonksiyon karşılaştırma/doğrulama amaçlıdır.
    """
    H = capacity_subgraph(G, demand_mbps)
    if s not in H.nodes or d not in H.nodes or not nx.has_path(H, s, d):
        return None, float("inf"), None

    # Başlangıç düğümünün node reliability maliyetini sabit olarak ekle
    start_node_rel = -math.log(max(float(H.nodes[s].get("node_reliability", 1.0)), EPS))
    base = wr * start_node_rel

    def w(u, v, dest):
        # Kenar bileşenleri
        ed, er, ec = edge_cost_components(H, u, v)

        # v düğümüne girerken node reliability maliyeti
        node_rel = -math.log(max(float(H.nodes[v].get("node_reliability", 1.0)), EPS))

        # v düğümünde processing delay (hedef düğümde genelde saymıyoruz)
        node_proc = float(H.nodes[v].get("processing_delay_ms", 0.0))

        enter = wr * node_rel + (wd * node_proc if v != dest else 0.0)

        # Toplam geçiş maliyeti
        return (wd * ed + wr * er + wc * ec) + enter

    import heapq
    dist = {s: base}
    prev = {s: None}
    pq = [(base, s)]

    # Standart Dijkstra
    while pq:
        du, u = heapq.heappop(pq)
        if du != dist.get(u, float("inf")):
            continue
        if u == d:
            break
        for v in H.neighbors(u):
            cand = du + w(u, v, d)
            if cand < dist.get(v, float("inf")):
                dist[v] = cand
                prev[v] = u
                heapq.heappush(pq, (cand, v))

    if d not in dist:
        return None, float("inf"), None

    # Path geri kurma
    path = []
    cur = d
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    path.reverse()

    delay, rel_cost, res_cost = compute_metrics_for_path(H, path)
    return path, dist[d], (delay, rel_cost, res_cost)


# -------------------- ACO router --------------------

class ACO_Router:
    """
    ACO'nun çekirdek sınıfı.

    Öğrenme (run-to-run learning):
    - 'pheromone' tablosu epoch'lar boyunca korunur. Bu sayede
      önceki epoch'larda bulunan iyi yollar sonraki epoch'larda daha olası seçilir.

    Stagnation azaltma:
    - deposit: sadece global-best değil, iterasyon içindeki top-k iyi yollara feromon
    - epsilon-greedy: bazen rastgele keşif, çoğunlukla feromon+heuristic ile seçim
    - reheat: epoch boyunca iyileşme yoksa feromonları tau0'a yaklaştır (çeşitlilik)
    """

    def __init__(
        self,
        G: nx.Graph,
        demand_mbps: float,
        N_ants: int,
        rho: float,
        alpha: float,
        beta: float,
        wd: float,
        wr: float,
        wc: float,
        seed: int,
        eps_start: float,
        eps_end: float,
        eps_schedule: str,
        topk: int,
        tau_min: float = 1e-8,
        tau_max: float = 1e6,
    ):
        self.G = G
        self.demand_mbps = float(demand_mbps)

        # ACO parametreleri
        self.N_ants = int(N_ants)     # her iterasyondaki karınca sayısı
        self.rho = float(rho)         # buharlaşma oranı
        self.alpha = float(alpha)     # feromon etkisi
        self.beta = float(beta)       # heuristik etkisi

        # Weighted-sum ağırlıkları
        self.wd = float(wd)
        self.wr = float(wr)
        self.wc = float(wc)

        # Epsilon schedule (epoch'a göre keşif oranını azalt)
        self.eps_start = float(eps_start)
        self.eps_end = float(eps_end)
        self.eps_schedule = str(eps_schedule).lower().strip()

        # Kullanıcı yanlışlıkla eps_start < eps_end verdiyse ters çevir
        if self.eps_start < self.eps_end:
            self.eps_start, self.eps_end = self.eps_end, self.eps_start

        # O anki epsilon (epoch başında güncellenir)
        self.epsilon = float(self.eps_start)

        # Deposit top-k: her iterasyonda en iyi k yol feromon bırakacak
        self.topk = int(max(1, min(topk, N_ants)))

        # Rastgelelik için RNG
        self.rng = np.random.default_rng(seed)

        # Feromon clamp sınırları (patlamayı veya sıfıra inmeyi önler)
        self.tau_min = float(tau_min)
        self.tau_max = float(tau_max)

        # Kenar feromonları (undirected graph olduğu için (min,max) key kullanacağız)
        self.pheromone: Dict[Tuple[int, int], float] = {}
        self.tau0 = None

        # Global en iyi çözüm (tüm epoch/iterasyonlar boyunca)
        self.global_best_path: Optional[List[int]] = None
        self.global_best_cost: float = float("inf")

        self._init_pheromone()

    def _epsilon_at_epoch(self, ep: int, epochs: int) -> float:
        """
        Epoch indexine göre epsilon hesaplar.
        - linear: eps_start -> eps_end doğrusal
        - exp: eps_start -> eps_end üstel (genelde daha doğal annealing)
        """
        ep = int(ep)
        epochs = int(max(1, epochs))

        if epochs == 1:
            return float(self.eps_end)

        t = (ep - 1) / (epochs - 1)  # 0..1

        if self.eps_schedule == "linear":
            eps = self.eps_start + (self.eps_end - self.eps_start) * t
        else:
            # default exp: eps = eps_start * (eps_end/eps_start)^t
            ratio = max(self.eps_end, EPS) / max(self.eps_start, EPS)
            eps = self.eps_start * (ratio ** t)

        # Güvenli clamp
        eps = min(max(float(eps), 0.0), 1.0)
        eps = max(eps, self.eps_end)
        return float(eps)

    def _ekey(self, u: int, v: int) -> Tuple[int, int]:
        """Undirected edge için normalize key."""
        return (u, v) if u <= v else (v, u)

    def _tau(self, u: int, v: int) -> float:
        """(u,v) kenarının feromonunu döndür."""
        return float(self.pheromone.get(self._ekey(u, v), self.tau0))

    def _set_tau(self, u: int, v: int, val: float) -> None:
        """Feromonu clamp ederek yaz."""
        val = min(max(float(val), self.tau_min), self.tau_max)
        self.pheromone[self._ekey(u, v)] = val

    def _init_pheromone(self) -> None:
        """
        Başlangıç feromonu tau0:
        Kabaca ortalama maliyet ölçeğine göre 1/(N * avg_cost) gibi bir değer.
        """
        avg_cost_estimate = (
            self.wd * 10.0
            + self.wr * -math.log(0.97)
            + self.wc * (1000.0 / 500.0)
        )
        self.tau0 = 1.0 / (len(self.G.nodes) * avg_cost_estimate + EPS)

        # Tüm kenarları aynı tau0 ile başlat
        for u, v in self.G.edges:
            self.pheromone[self._ekey(u, v)] = float(self.tau0)

    def reheat(self, phi: float) -> None:
        """
        Reheat: feromonları kısmen başlangıca yaklaştır.
        tau = (1-phi)*tau + phi*tau0
        Amaç: stagnation sonrası çeşitliliği artırmak.
        """
        phi = float(phi)
        if phi <= 0:
            return
        for k in list(self.pheromone.keys()):
            self.pheromone[k] = (1.0 - phi) * self.pheromone[k] + phi * self.tau0
            self.pheromone[k] = min(max(self.pheromone[k], self.tau_min), self.tau_max)

    def _heuristic(self, u: int, v: int) -> float:
        """
        Heuristik: düşük maliyetli kenar daha iyi olsun diye
        eta = 1 / (weighted_edge_cost + EPS)
        """
        ed, er, ec = edge_cost_components(self.G, u, v)
        c = self.wd * ed + self.wr * er + self.wc * ec
        return 1.0 / (c + EPS)

    def _select_next(self, cur: int, in_path: set, tried: Dict[int, set]) -> Optional[int]:
        """
        Bir karıncanın 'cur' düğümünden sonraki düğümü seçme fonksiyonu.
        - Kapasite kısıtı uygular
        - Döngüleri engeller (in_path)
        - Daha önce denenmiş komşuları tekrar denemez (tried)
        - epsilon-greedy ile bazen rastgele seçer
        - aksi halde feromon+heuristik olasılıksal seçim yapar
        """
        if cur not in tried:
            tried[cur] = set()

        candidates = []
        for v in self.G.neighbors(cur):
            if v in in_path:
                continue  # döngü istemiyoruz
            if v in tried[cur]:
                continue  # aynı komşuyu tekrar deneme
            if float(self.G.edges[cur, v].get("bandwidth_mbps", 0.0)) < self.demand_mbps:
                continue  # demand kapasite kısıtı
            candidates.append(v)

        if not candidates:
            return None

        # epsilon-greedy: epsilon olasılıkla tamamen rastgele keşif
        if self.epsilon > 0 and self.rng.random() < self.epsilon:
            nxt = int(self.rng.choice(candidates))
            tried[cur].add(nxt)
            return nxt

        # Aksi halde: (tau^alpha) * (eta^beta) ile olasılık dağılımı
        powers = []
        for v in candidates:
            tau = self._tau(cur, v)
            eta = self._heuristic(cur, v)
            powers.append((tau ** self.alpha) * (eta ** self.beta))

        s = float(sum(powers))
        if s <= EPS:
            # Numerik problem varsa uniform dağıt
            probs = np.ones(len(candidates), dtype=float) / len(candidates)
        else:
            probs = np.array(powers, dtype=float) / s
            probs = probs / probs.sum()

        nxt = int(self.rng.choice(candidates, p=probs))
        tried[cur].add(nxt)
        return nxt

    def _construct_path(self, start: int, end: int) -> Optional[List[int]]:
        """
        Tek bir karıncanın S'ten D'ye yol inşa etmesi.
        Çıkmaza girerse backtracking yapar (path.pop()).
        """
        path = [start]
        in_path = {start}
        tried: Dict[int, set] = {}

        # Çok uzun aramayı sınırlamak için güvenlik sınırı
        max_steps = len(self.G.nodes) * 20
        steps = 0

        while path and steps < max_steps:
            steps += 1
            cur = path[-1]
            if cur == end:
                return path

            nxt = self._select_next(cur, in_path, tried)
            if nxt is None:
                # Çıkmaz: geri dön
                popped = path.pop()
                in_path.remove(popped)
                continue

            # Bir adım ilerle
            path.append(nxt)
            in_path.add(nxt)

        return None  # bulunamadı

    def _evaporate(self) -> None:
        """
        Feromon buharlaşması:
        tau = (1-rho)*tau
        Böylece eski bilgi zamanla azalır.
        """
        for k in list(self.pheromone.keys()):
            self.pheromone[k] = (1.0 - self.rho) * self.pheromone[k]
            self.pheromone[k] = min(max(self.pheromone[k], self.tau_min), self.tau_max)

    def _deposit_paths(self, paths_costs: List[Tuple[List[int], float]]) -> None:
        """
        Deposit:
        - Yolları maliyete göre sırala
        - En iyi top-k yola feromon ekle
        delta = 1/cost (daha iyi yol daha fazla feromon)
        """
        paths_costs.sort(key=lambda x: x[1])
        for p, c in paths_costs[: self.topk]:
            if c <= 0 or not math.isfinite(c):
                continue
            delta = 1.0 / c
            for u, v in zip(p[:-1], p[1:]):
                self._set_tau(u, v, self._tau(u, v) + delta)

    def iterate_once(self, start: int, end: int) -> bool:
        """
        ACO'nun 1 iterasyonu:
        - N_ants kadar karınca yol üretir
        - Her yolun cost'u hesaplanır
        - Global best güncellenir
        - Evaporation + deposit yapılır
        Döndürdüğü bool: Bu iterasyonda global best iyileşti mi?
        """
        paths_costs = []
        iter_best_cost = float("inf")
        iter_best_path = None

        for _ in range(self.N_ants):
            p = self._construct_path(start, end)
            if not p:
                continue
            dly, relc, resc = compute_metrics_for_path(self.G, p)
            c = total_cost_from_metrics(self.wd, self.wr, self.wc, dly, relc, resc)
            paths_costs.append((p, c))
            if c < iter_best_cost:
                iter_best_cost = c
                iter_best_path = p

        improved = False
        if iter_best_path is not None and iter_best_cost < self.global_best_cost:
            self.global_best_cost = iter_best_cost
            self.global_best_path = iter_best_path
            improved = True

        # Feromon güncelleme: önce buharlaşma
        self._evaporate()

        # Sonra iyi yollara feromon bırak
        if paths_costs:
            self._deposit_paths(paths_costs)

        return improved

    def run_epochs(self, start: int, end: int, epochs: int, iters_per_epoch: int, reheat: float) -> List[Tuple[int, Optional[List[int]], float, float]]:
        """
        Ana öğrenme döngüsü:
        - epochs boyunca tekrarla
        - her epoch başında epsilon güncelle
        - iters_per_epoch iterasyon çalıştır
        - epoch boyunca iyileşme yoksa reheat uygula
        history: (epoch, best_path, best_cost, epsilon)
        """
        history = []
        epochs = int(epochs)
        iters_per_epoch = int(iters_per_epoch)
        reheat = float(reheat)

        for ep in range(1, epochs + 1):
            # Bu epoch için epsilon değerini ayarla (keşif oranı)
            self.epsilon = self._epsilon_at_epoch(ep, epochs)

            improved_this_epoch = False
            for _ in trange(iters_per_epoch, desc=f"Epoch {ep}/{epochs}", leave=True):
                if self.iterate_once(start, end):
                    improved_this_epoch = True

            # Epoch boyunca gelişme yoksa stagnation olabilir -> reheat
            if (not improved_this_epoch) and reheat > 0:
                self.reheat(reheat)

            history.append((ep, self.global_best_path, self.global_best_cost, self.epsilon))

            if self.global_best_path is not None:
                print(
                    f"  [EPOCH-END] ep={ep} best_cost={self.global_best_cost:.6f} "
                    f"path={' -> '.join(map(str, self.global_best_path))} | eps={self.epsilon:.4f}"
                )

        return history


# -------------------- Runner --------------------

def run_for_single_demand(
    G_full: nx.Graph,
    s: int,
    d: int,
    demand_mbps: float,
    wd: float,
    wr: float,
    wc: float,
    epochs: int,
    iters_per_epoch: int,
    ants: int,
    seed: int,
    rho: float,
    alpha: float,
    beta: float,
    eps_start: float,
    eps_end: float,
    eps_schedule: str,
    topk: int,
    reheat: float,
    baseline_dijkstra: bool,
):
    """
    Tek bir demand satırı (S,D,demand) için:
    - capacity_subgraph ile feasible graph oluştur
    - ACO çalıştır (epochs x iters_per_epoch x ants)
    - İstenirse Dijkstra ile optimumu bul ve karşılaştır
    """
    H = capacity_subgraph(G_full, demand_mbps)

    # Feasible path yoksa çık
    if s not in H.nodes or d not in H.nodes or not nx.has_path(H, s, d):
        print(f"\nPath {s}->{d}: NO FEASIBLE PATH under demand={demand_mbps} Mbps (capacity constraint).")
        return None

    # Ağırlıklar toplamı 1 değilse normalize et (görece oranlar korunsun)
    wsum = float(wd + wr + wc)
    if abs(wsum - 1.0) > 1e-9 and wsum > 0:
        wd, wr, wc = wd / wsum, wr / wsum, wc / wsum

    # Ekran çıktısı için (start yüksek, end düşük) gösterim
    eps_start_disp = max(eps_start, eps_end)
    eps_end_disp = min(eps_start, eps_end)

    print(f"\n--- LEARNING ACO: S={s}, D={d}, demand={float(demand_mbps)} Mbps ---")
    print(f"FeasibleGraph: nodes={H.number_of_nodes()}, edges={H.number_of_edges()}")
    print(f"Epochs={epochs}, iters/epoch={iters_per_epoch}, ants={ants}, weights=({wd:.2f},{wr:.2f},{wc:.2f})")
    print(f"Params: rho={rho}, alpha={alpha}, beta={beta}, topk={topk}, reheat={reheat}, seed={seed}")
    print(f"Epsilon schedule: {eps_schedule} {eps_start_disp:.4f} -> {eps_end_disp:.4f}\n")

    # Dijkstra baseline: weighted-sum için kesin optimum
    if baseline_dijkstra:
        p_opt, c_opt, m_opt = dijkstra_optimal_path(G_full, s, d, demand_mbps, wd, wr, wc)
        if p_opt:
            dly, relc, resc = m_opt
            rel = math.exp(-relc)  # toplam güvenilirliği tekrar çarpımsal forma çevir
            print("Dijkstra baseline (exact optimum for weighted-sum):")
            print(f"  OptCost={c_opt:.6f} | delay={dly:.2f}ms | rel={rel:.6f} | res={resc:.6f} | path={' -> '.join(map(str,p_opt))}\n")
        else:
            print("Dijkstra baseline: no feasible path.\n")

    # ACO başlat (feasible graph üzerinde!)
    aco = ACO_Router(
        H,
        demand_mbps=demand_mbps,
        N_ants=ants,
        rho=rho,
        alpha=alpha,
        beta=beta,
        wd=wd,
        wr=wr,
        wc=wc,
        seed=seed,
        eps_start=eps_start,
        eps_end=eps_end,
        eps_schedule=eps_schedule,
        topk=topk,
    )

    # Epoch çalıştır
    t0 = time.time()
    hist = aco.run_epochs(s, d, epochs=epochs, iters_per_epoch=iters_per_epoch, reheat=reheat)
    t1 = time.time()

    # Her epoch sonunda best-so-far metriklerini raporla
    for ep, p, c, eps in hist:
        if p is None:
            print(f"  Epoch {ep}: best-so-far=None | eps={eps:.4f}")
            continue
        dly, relc, resc = compute_metrics_for_path(H, p)
        rel = math.exp(-relc)
        path_str = " -> ".join(map(str, p))
        print(
            f"  Epoch {ep}: best-so-far cost={c:.6f} | delay={dly:.2f}ms | rel={rel:.6f} | res={resc:.6f} "
            f"| hops={len(p)-1} | eps={eps:.4f} | path={path_str}"
        )

    # Final sonuç
    best_path = aco.global_best_path
    best_cost = aco.global_best_cost

    print(f"\nDone. Total time: {t1 - t0:.3f}s")
    if best_path:
        dly, relc, resc = compute_metrics_for_path(H, best_path)
        rel = math.exp(-relc)
        print(f"Final best path: {' -> '.join(map(str, best_path))}")
        print(f"Final best cost: {best_cost:.6f}")
        print(f"Final metrics : delay={dly:.2f}ms | rel={rel:.6f} | res={resc:.6f}")

    return {
        "S": s, "D": d, "Demand_Mbps": float(demand_mbps),
        "Best_Cost": float(best_cost),
        "Best_Path": None if not best_path else " -> ".join(map(str, best_path)),
        "Time_sec": float(t1 - t0),
    }


def main():
    """CLI argümanlarını alır, veriyi okur, graph kurar, demand'ları çalıştırır."""
    ap = argparse.ArgumentParser(description="ACO routing with epoch learning and anti-stagnation improvements (epsilon schedule).")

    ap.add_argument("--nodes-file", type=str, default="NodeData.csv")
    ap.add_argument("--edges-file", type=str, default="EdgeData.csv")
    ap.add_argument("--demand-file", type=str, default="DemandData.csv")
    ap.add_argument("--demand-idx", type=int, default=None)

    ap.add_argument("--wd", type=float, default=0.33)
    ap.add_argument("--wr", type=float, default=0.33)
    ap.add_argument("--wc", type=float, default=0.34)

    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--iters-per-epoch", type=int, default=200)
    ap.add_argument("--ants", type=int, default=20)
    ap.add_argument("--seed", type=int, default=42)

    # ACO hiperparametreleri
    ap.add_argument("--rho", type=float, default=0.1)
    ap.add_argument("--alpha", type=float, default=1.0)
    ap.add_argument("--beta", type=float, default=2.0)

    # epsilon schedule parametreleri
    ap.add_argument("--eps-start", type=float, default=0.15, help="epsilon at epoch 1 (higher exploration).")
    ap.add_argument("--eps-end", "--epsilon", dest="eps_end", type=float, default=0.02,
                    help="epsilon at final epoch (lower exploration). '--epsilon' kept as alias for backward compatibility.")
    ap.add_argument("--eps-schedule", type=str, default="exp", choices=["exp", "linear"],
                    help="epsilon schedule type across epochs.")

    # anti-stagnation parametreleri
    ap.add_argument("--topk", type=int, default=5, help="deposit pheromone using top-k ants each iteration.")
    ap.add_argument("--reheat", type=float, default=0.03, help="if an epoch has no improvement, pull pheromones toward tau0 by this ratio.")

    # baseline
    ap.add_argument("--baseline-dijkstra", action="store_true", help="Compute exact optimum via Dijkstra for comparison.")

    args = ap.parse_args()

    # Veriyi yükle ve graph oluştur
    nodes_df, edges_df, demand_df = load_data(args.nodes_file, args.edges_file, args.demand_file)
    G = build_graph(nodes_df, edges_df)

    # Demand kolonlarını seç
    src_col = choose_col(demand_df, ["src", "source", "start_node", "S"])
    dst_col = choose_col(demand_df, ["dst", "target", "end_node", "D"])
    dem_col = choose_col(demand_df, ["demand_mbps", "demand", "bw_required"])

    # Tek bir demand satırı çalıştırmak için index filtresi
    if args.demand_idx is not None:
        if not (0 <= args.demand_idx < len(demand_df)):
            raise SystemExit(f"demand-idx {args.demand_idx} out of range (0..{len(demand_df)-1}).")
        demand_df = demand_df.iloc[[args.demand_idx]]

    results = []
    for _, row in demand_df.iterrows():
        s = int(row[src_col])
        d = int(row[dst_col])
        dm = float(row[dem_col])

        res = run_for_single_demand(
            G_full=G,
            s=s,
            d=d,
            demand_mbps=dm,
            wd=args.wd,
            wr=args.wr,
            wc=args.wc,
            epochs=args.epochs,
            iters_per_epoch=args.iters_per_epoch,
            ants=args.ants,
            seed=args.seed,
            rho=args.rho,
            alpha=args.alpha,
            beta=args.beta,
            eps_start=args.eps_start,
            eps_end=args.eps_end,
            eps_schedule=args.eps_schedule,
            topk=args.topk,
            reheat=args.reheat,
            baseline_dijkstra=args.baseline_dijkstra,
        )
        if res:
            results.append(res)

    # Özet tablo
    if results:
        out_df = pd.DataFrame(results)
        print("\n--- SUMMARY ---")
        print(out_df.round(6).to_string(index=False))


if __name__ == "__main__":
    main()

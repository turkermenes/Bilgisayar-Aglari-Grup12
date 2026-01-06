import json
import sys
import time
from typing import Dict, Tuple
import pandas as pd

# Kayan noktalı sayı karşılaştırmalarında sıfıra çok yakın değerler için tolerans payı
EPS = 1e-12

# Özel modüllerden algoritmaların ve yardımcı fonksiyonların içe aktarılması
from aco_algorithm import ACO, build_graph, compute_metrics_for_path
from ga_algorithm import GeneticAlgorithm, NetworkTopology

def normalize_weights(w_delay: float, w_reliability: float, w_resource: float) -> Tuple[float, float, float]:
    """
    Kullanıcıdan gelen ağırlıkları normalize eder (toplamlarını 1.0 yapar).
    Eğer tüm ağırlıklar 0 ise eşit dağılım (1/3) uygular.
    """
    total = w_delay + w_reliability + w_resource
    if total < EPS:
        return (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0)
    return (w_delay / total, w_reliability / total, w_resource / total)

def read_csv_robust(path: str) -> pd.DataFrame:
    """
    CSV dosyalarını farklı ayraçlar (; veya ,) kullanarak dayanıklı bir şekilde okur.
    ID kolonlarını tam sayıya, diğer metrikleri ise sayısal değerlere dönüştürür.
    """
    try:
        df = pd.read_csv(path, sep=";", encoding="utf-8")
        if df.shape[1] <= 1: # Eğer tek sütun kaldıysa ayraç muhtemelen virgüllüdür
            df = pd.read_csv(path, sep=",", encoding="utf-8")
    except Exception:
        df = pd.read_csv(path, sep=",", encoding="utf-8")

    id_cols = {"node_id", "src", "dst"}

    for col in df.columns:
        s = df[col].astype(str).str.strip()
        # ID sütunlarını temizle ve tam sayıya çevir
        if col.lower() in id_cols:
            s = s.str.replace(",", ".", regex=False)
            df[col] = pd.to_numeric(s, errors="coerce").fillna(0).astype(int)
            continue

        # Diğer sayısal sütunlardaki virgülleri noktaya çevirip sayıya dönüştür
        s = s.str.replace(",", ".", regex=False)
        df[col] = pd.to_numeric(s, errors="ignore")

    return df

def solve_with_aco(
    nodes_csv: str,
    edges_csv: str,
    source: int,
    target: int,
    demand_mbps: float,
    weights: Dict[str, float],
    params: Dict
) -> Dict:
    """
    Karınca Kolonisi Optimizasyonu kullanarak en kısa/iyi yolu bulur.
    """
    try:
        # Veriyi yükle ve graf yapısını oluştur
        nodes_df = read_csv_robust(nodes_csv)
        edges_df = read_csv_robust(edges_csv)
        G = build_graph(nodes_df, edges_df)

        # Optimizasyon kriter ağırlıklarını hazırla
        w_delay, w_rel, w_res = normalize_weights(
            float(weights.get("delay", 0.33)),
            float(weights.get("reliability", 0.33)),
            float(weights.get("resource", 0.34)),
        )

        # ACO algoritma parametrelerini ayarla
        aco_params = params.get("aco", {})
        aco = ACO(
            G,
            w_delay=w_delay,
            w_rel=w_rel,
            w_res=w_res,
            n_ants=int(aco_params.get("ants", 30)),
            n_iter=int(aco_params.get("iters", 200)),
            alpha=float(aco_params.get("alpha", 1.0)), # Feromon önemi
            beta=float(aco_params.get("beta", 2.0)),   # Sezgisel bilgi önemi
            rho=float(aco_params.get("rho", 0.1)),     # Buharlaşma oranı
            q=float(aco_params.get("q", 1.0)),
            capacity_aware=True, # Kapasite kısıtlarını dikkate al
        )

        # Zamanlamayı başlat ve algoritmayı çalıştır
        t0 = time.time()
        result = aco.run_one(
            source,
            target,
            demand_mbps=demand_mbps,
            include_processing_for_ends=False,
            show_progress=False
        )
        t1 = time.time()

        if result.best_path is None:
            return {"ok": False, "error": "No path found", "time_sec": t1 - t0}

        # Sonuçları JSON formatına uygun sözlük yapısında döndür
        return {
            "ok": True,
            "best_path": result.best_path,
            "best_path_str": "->".join(map(str, result.best_path)),
            "metrics": {
                "total_cost": float(result.best_cost),
                "delay_ms": float(result.delay_ms),
                "reliability_cost": float(result.rel_cost),
                "resource_cost": float(result.res_cost),
            },
            "time_sec": float(result.time_sec),
            "error": None
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "time_sec": 0.0}

def solve_with_ga(
    nodes_csv: str,
    edges_csv: str,
    source: int,
    target: int,
    demand_mbps: float,
    weights: Dict[str, float],
    params: Dict
) -> Dict:
    """
    Genetik Algoritma kullanarak en uygun yolu bulur.
    """
    try:
        nodes_df = read_csv_robust(nodes_csv)
        edges_df = read_csv_robust(edges_csv)
        topology = NetworkTopology(nodes_df, edges_df)

        w_delay, w_rel, w_res = normalize_weights(
            float(weights.get("delay", 0.33)),
            float(weights.get("reliability", 0.33)),
            float(weights.get("resource", 0.34)),
        )

        # GA parametrelerini ayarla
        ga_params = params.get("ga", {})
        ga = GeneticAlgorithm(topology)
        ga.set_configurations(
            population_size=int(ga_params.get("population", 100)),
            mutation_rate=float(ga_params.get("mutation_rate", 0.2)),
            generations=int(ga_params.get("generations", 25)),
            elitisim_percentage=float(ga_params.get("elitism", 0.1)),
            tournament_size=int(ga_params.get("tournament_size", 25)),
            max_stagnation=int(ga_params.get("max_stagnation", 15)), 
        )

        t0 = time.time()
        best_path, best_fitness = ga.genetic_algorithm(
            source_node_id=source,
            target_node_id=target,
            demand_bandwidth=float(demand_mbps),
            weight_delay=w_delay,
            weight_reliability=w_rel,
            weight_resource=w_res,
            verbose=False
        )
        t1 = time.time()

        if best_path is None:
            return {"ok": False, "error": "No path found", "time_sec": t1 - t0}

        # Bulunan yolun metriklerini hesapla
        delay, rel_cost, res_cost = compute_metrics_for_path(
            topology.G, best_path, include_processing_for_ends=False
        )

        return {
            "ok": True,
            "best_path": best_path,
            "best_path_str": "->".join(map(str, best_path)),
            "metrics": {
                "total_cost": float(best_fitness),
                "delay_ms": float(delay),
                "reliability_cost": float(rel_cost),
                "resource_cost": float(res_cost),
            },
            "time_sec": float(t1 - t0),
            "error": None
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "time_sec": 0.0}

def main():
    """
    Programın ana giriş noktası. Standart girişten (stdin) JSON verisi bekler,
    istenilen algoritmayı çalıştırır ve sonucu standart çıkışa (stdout) yazar.
    """
    try:
        # Girdiyi JSON olarak oku
        input_data = json.load(sys.stdin)
        algorithm = str(input_data.get("algorithm", "ACO")).upper()
        nodes_csv = input_data["nodes_csv"]
        edges_csv = input_data["edges_csv"]
        source = int(input_data["source"])
        target = int(input_data["target"])
        demand_mbps = float(input_data["demand_mbps"])
        weights = input_data.get("weights", {"delay": 0.33, "reliability": 0.33, "resource": 0.34})
        params = input_data.get("params", {})

        # Algoritma seçimine göre ilgili fonksiyonu çağır
        if algorithm == "ACO":
            result = solve_with_aco(nodes_csv, edges_csv, source, target, demand_mbps, weights, params)
        elif algorithm == "GA":
            result = solve_with_ga(nodes_csv, edges_csv, source, target, demand_mbps, weights, params)
        else:
            result = {"ok": False, "error": f"Unknown algorithm: {algorithm}", "time_sec": 0.0}

        # Sonucu JSON formatında ekrana yazdır 
        print(json.dumps(result))
        sys.stdout.flush()
    except Exception as e:
        # Hata durumunda hatayı bildir
        print(json.dumps({"ok": False, "error": str(e), "time_sec": 0.0}))
        sys.stdout.flush()
        sys.exit(1)

if __name__ == "__main__":
    main()
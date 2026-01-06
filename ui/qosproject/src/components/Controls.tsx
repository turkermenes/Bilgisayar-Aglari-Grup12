import React, { useState, useEffect } from 'react';
import { GraphData, PathResult } from '../App';
import './Controls.css';

interface ControlsProps {
  // UI tarafında seçilen CSV dosya yolları (Electron üzerinden Python solver’a gider)
  csvPaths: { nodes: string; edges: string; demand: string };
  // GraphView vb. bileşenlerin kullandığı node/edge datası
  graphData: GraphData;
  // Solver başarılı olunca bulunan yolu ve metrikleri App’e geri taşır
  onPathFound: (path: number[], result: PathResult) => void;
  // Run sırasında buton disable/loader kontrolü
  loading: boolean;
  setLoading: (loading: boolean) => void;
}

const Controls: React.FC<ControlsProps> = ({
  csvPaths,
  graphData,
  onPathFound,
  loading,
  setLoading
}) => {
  // Kullanıcının seçtiği algoritma (Python tarafında solver bu değere göre ACO/GA çağırar)
  const [algorithm, setAlgorithm] = useState<'ACO' | 'GA'>('ACO');
  // UI inputları (string tutulup payload oluştururken sayıya çevriliyor)
  const [source, setSource] = useState<string>('');
  const [target, setTarget] = useState<string>('');
  const [demand, setDemand] = useState<string>('');
  // Multi-objective ağırlıklar (solver’a weights olarak gönderilir)
  const [wDelay, setWDelay] = useState(0.5);
  const [wReliability, setWReliability] = useState(0.25);
  const [wResource, setWResource] = useState(0.25);

  // Demand CSV’den (src,dst,demand) seçeneklerini çekip dropdown’da göstermek için
  const [demandOptions, setDemandOptions] = useState<Array<{ src: number; dst: number; demand: number }>>([]);

  // Demand CSV’yi Electron üzerinden okuyup seçenekleri hazırlar
  useEffect(() => {
    const loadDemandOptions = async () => {
      try {
        // Browser modunda Electron API olmayacağı için güvenli fallback
        if (!window.electronAPI) {
          console.warn('Electron API not available');
          setDemandOptions([]);
          return;
        }

        if (!csvPaths.demand) {
          setDemandOptions([]);
          return;
        }

        const result = await window.electronAPI.readCSV(csvPaths.demand);

        if (!result?.success) {
          console.warn('Could not load demand CSV:', result?.error);
          setDemandOptions([]);
          return;
        }

        const text = result.content ?? '';
        if (!text.trim()) {
          console.warn('Demand CSV content is empty');
          setDemandOptions([]);
          return;
        }

        // Basit CSV parser: ; veya , ayracını header satırına göre seçer
        const rawLines = text.split(/\r?\n/).filter((l) => l.trim().length > 0);
        if (rawLines.length < 2) {
          console.warn('Demand CSV has no data rows');
          setDemandOptions([]);
          return;
        }

        const headerLine = rawLines[0];
        const sep = headerLine.includes(';') ? ';' : ',';
        const headers = headerLine.split(sep).map((h) => h.trim().toLowerCase());

        const srcIdx = headers.findIndex((h) => h.includes('src'));
        const dstIdx = headers.findIndex((h) => h.includes('dst'));
        const demIdx = headers.findIndex((h) => h.includes('demand'));

        if (srcIdx < 0 || dstIdx < 0 || demIdx < 0) {
          console.warn('Demand CSV headers not found:', headers);
          setDemandOptions([]);
          return;
        }

        const options: Array<{ src: number; dst: number; demand: number }> = [];

        for (let i = 1; i < rawLines.length; i++) {
          const parts = rawLines[i].split(sep).map((p) => p.trim());
          if (parts.length <= Math.max(srcIdx, dstIdx, demIdx)) continue;

          const src = parseInt(parts[srcIdx], 10);
          const dst = parseInt(parts[dstIdx], 10);
          // Ondalık ayırıcı virgül gelirse noktaya çevirip parse ediyoruz
          const dem = parseFloat((parts[demIdx] ?? '').replace(',', '.'));

          if (Number.isFinite(src) && Number.isFinite(dst) && Number.isFinite(dem)) {
            options.push({ src, dst, demand: dem });
          }
        }

        setDemandOptions(options);
      } catch (err) {
        console.error('Failed to load demand options', err);
        setDemandOptions([]);
      }
    };

    loadDemandOptions();
  }, [csvPaths.demand]);

  // Ağırlıkların toplamını 1.0 tutmak için küçük bir normalize işlemi (UI tarafı güvenlik)
  useEffect(() => {
    const total = wDelay + wReliability + wResource;
    if (!Number.isFinite(total) || total <= 0) return;

    if (Math.abs(total - 1.0) > 0.001) {
      const scale = 1.0 / total;
      setWDelay((prev) => prev * scale);
      setWReliability((prev) => prev * scale);
      setWResource((prev) => prev * scale);
    }
  }, [wDelay, wReliability, wResource]);

  // CSV’deki demand seçilince source/target/demand alanlarını otomatik doldurur
  const handleDemandSelect = (option: { src: number; dst: number; demand: number }) => {
    setSource(option.src.toString());
    setTarget(option.dst.toString());
    setDemand(option.demand.toString());
  };

  // "Run" tıklandığında payload oluşturup Electron üzerinden Python solver’ı çağırır
  const handleRun = async () => {
    if (!source || !target || !demand) {
      alert('Please select source, target, and demand');
      return;
    }

    if (!csvPaths.nodes || !csvPaths.edges) {
      alert('Please load Nodes and Edges CSV first.');
      return;
    }

    setLoading(true);

    try {
      // Electron ortam kontrolü (browser modunda solver çalıştırılamaz)
      if (!window.electronAPI) {
        throw new Error(
          'Electron API not available. Please run the application in Electron (not browser).\n' +
          'Use: npm run dev'
        );
      }

      if (!window.electronAPI.runSolver) {
        throw new Error('runSolver method not found in Electron API');
      }

      // Python solver’ın beklediği formatta çağrı payload’ı
      const payload = {
        algorithm,
        nodes_csv: csvPaths.nodes,
        edges_csv: csvPaths.edges,
        source: parseInt(source, 10),
        target: parseInt(target, 10),
        demand_mbps: parseFloat(demand.replace(',', '.')),
        weights: {
          delay: wDelay,
          reliability: wReliability,
          resource: wResource
        },
        // Algoritma parametreleri (UI’dan sabit/varsayılan veriliyor)
        params: {
          aco: {
            ants: 30,
            iters: 200
          },
          ga: {
            population: 100,
            generations: 25,
            mutation_rate: 0.2
          }
        }
      };

      console.log('Calling runSolver with payload:', payload);
      const result = await window.electronAPI.runSolver(payload);
      console.log('Solver result:', result);

      // Başarılıysa bulunan en iyi yolu App seviyesine taşı
      if (result?.ok && result.best_path) {
        onPathFound(result.best_path, result);
      } else {
        const errorMsg = result?.error || 'No path found';
        console.error('Solver error:', errorMsg);
        alert(`Error: ${errorMsg}`);
      }
    } catch (error: any) {
      console.error(error);
      alert(`Failed to run solver: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  // GraphData içinden node id’leri çekip dropdown için sıralar
  const nodeIds = graphData.nodes
    .map((n) => parseInt(n.id, 10))
    .filter(Number.isFinite)
    .sort((a, b) => a - b);

  return (
    <div className="controls">
      <h2>Controls</h2>

      <div className="control-group">
        <label>Algorithm</label>
        <select value={algorithm} onChange={(e) => setAlgorithm(e.target.value as 'ACO' | 'GA')}>
          <option value="ACO">Ant Colony Optimization (ACO)</option>
          <option value="GA">Genetic Algorithm (GA)</option>
        </select>
      </div>

      <div className="control-group">
        <label>Source Node</label>
        <select value={source} onChange={(e) => setSource(e.target.value)}>
          <option value="">Select source...</option>
          {nodeIds.map((id) => (
            <option key={id} value={id}>
              {id}
            </option>
          ))}
        </select>
      </div>

      <div className="control-group">
        <label>Target Node</label>
        <select value={target} onChange={(e) => setTarget(e.target.value)}>
          <option value="">Select target...</option>
          {nodeIds.map((id) => (
            <option key={id} value={id}>
              {id}
            </option>
          ))}
        </select>
      </div>

      <div className="control-group">
        <label>Demand (Mbps)</label>

        <div className="demand-selector">
          <select
            value=""
            onChange={(e) => {
              const idx = parseInt(e.target.value, 10);
              if (Number.isFinite(idx) && idx >= 0 && idx < demandOptions.length) {
                handleDemandSelect(demandOptions[idx]);
              }
            }}
          >
            <option value="">Select from CSV...</option>
            {demandOptions.map((opt, idx) => (
              <option key={idx} value={idx}>
                {opt.src} → {opt.dst} ({opt.demand} Mbps)
              </option>
            ))}
          </select>
        </div>

        <input
          type="number"
          value={demand}
          onChange={(e) => setDemand(e.target.value)}
          placeholder="Or enter manually"
          step="0.1"
          min="0"
        />
      </div>

      <div className="control-group">
        <label>Weights (must sum to 1.0)</label>

        <div className="weight-controls">
          <div className="weight-item">
            <label>Delay: {wDelay.toFixed(3)}</label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.01"
              value={wDelay}
              onChange={(e) => {
                const val = parseFloat(e.target.value);
                const remaining = 1.0 - val;
                const otherTotal = wReliability + wResource;

                if (otherTotal > 0) {
                  setWDelay(val);
                  setWReliability(wReliability * (remaining / otherTotal));
                  setWResource(wResource * (remaining / otherTotal));
                } else {
                  setWDelay(val);
                  setWReliability(remaining / 2);
                  setWResource(remaining / 2);
                }
              }}
            />
          </div>

          <div className="weight-item">
            <label>Reliability: {wReliability.toFixed(3)}</label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.01"
              value={wReliability}
              onChange={(e) => {
                const val = parseFloat(e.target.value);
                const remaining = 1.0 - val;
                const otherTotal = wDelay + wResource;

                if (otherTotal > 0) {
                  setWReliability(val);
                  setWDelay(wDelay * (remaining / otherTotal));
                  setWResource(wResource * (remaining / otherTotal));
                } else {
                  setWReliability(val);
                  setWDelay(remaining / 2);
                  setWResource(remaining / 2);
                }
              }}
            />
          </div>

          <div className="weight-item">
            <label>Resource: {wResource.toFixed(3)}</label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.01"
              value={wResource}
              onChange={(e) => {
                const val = parseFloat(e.target.value);
                const remaining = 1.0 - val;
                const otherTotal = wDelay + wReliability;

                if (otherTotal > 0) {
                  setWResource(val);
                  setWDelay(wDelay * (remaining / otherTotal));
                  setWReliability(wReliability * (remaining / otherTotal));
                } else {
                  setWResource(val);
                  setWDelay(remaining / 2);
                  setWReliability(remaining / 2);
                }
              }}
            />
          </div>

          <div className="weight-sum">Sum: {(wDelay + wReliability + wResource).toFixed(3)}</div>
        </div>
      </div>

      <button
        className="run-button"
        onClick={handleRun}
        disabled={loading || !source || !target || !demand || !window.electronAPI}
        title={!window.electronAPI ? 'Electron API not available' : ''}
      >
        {loading ? 'Running...' : 'Run Algorithm'}
      </button>
    </div>
  );
};

export default Controls;

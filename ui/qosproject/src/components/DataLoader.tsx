import React, { useState, useRef } from 'react';
import { GraphData } from '../App';
import './DataLoader.css';

// Browser/Electron farkında dosya adı göstermek için basit basename helper
const path = {
  basename: (filePath: string) => {
    const parts = filePath.split(/[/\\]/);
    return parts[parts.length - 1];
  }
};

interface DataLoaderProps {
  // CSV'lerden graph üretildiğinde App'e node/edge verisi + özet bilgi + dosya yolları döner
  onGraphLoaded: (
    data: GraphData,
    info: { nodeCount: number; edgeCount: number; connected: boolean },
    paths: { nodes: string; edges: string; demand: string }
  ) => void;
}

const DataLoader: React.FC<DataLoaderProps> = ({ onGraphLoaded }) => {
  // Seçilen dosya yolları, isimleri (Electron'da full path, browser'da name)
  const [nodesFilePath, setNodesFilePath] = useState<string>('');
  const [edgesFilePath, setEdgesFilePath] = useState<string>('');
  const [demandFilePath, setDemandFilePath] = useState<string>('');
  // UI durumları
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

 
  const nodesInputRef = useRef<HTMLInputElement>(null);
  const edgesInputRef = useRef<HTMLInputElement>(null);
  const demandInputRef = useRef<HTMLInputElement>(null);

  // Basit CSV parser: separator varsayılan ';', tırnak içindeki ayraçları bölmez
  const parseCSV = (text: string, separator: string = ';'): string[][] => {
    const lines = text.split('\n').filter(line => line.trim());
    return lines.map(line => {
      const result: string[] = [];
      let current = '';
      let inQuotes = false;

      for (let i = 0; i < line.length; i++) {
        const char = line[i];
        if (char === '"') {
          inQuotes = !inQuotes;
        } else if (char === separator && !inQuotes) {
          result.push(current.trim());
          current = '';
        } else {
          current += char;
        }
      }
      result.push(current.trim());
      return result;
    });
  };

  // CSV'de ondalık virgül gelirse noktaya çevirerek parse eder
  const normalizeDecimal = (value: string): number => {
    return parseFloat(value.replace(',', '.'));
  };

  // Seçilen CSV'leri okuyup GraphData formatına çevirir 
  const loadGraph = async () => {
    let nodesText: string;
    let edgesText: string;
    let demandText: string;
    let finalPaths: { nodes: string; edges: string; demand: string };

    setLoading(true);
    setError(null);

    try {
      // Electron modunda dosyalar path ile okunur
      if (window.electronAPI && (nodesFilePath || edgesFilePath || demandFilePath)) {
        if (!nodesFilePath || !edgesFilePath || !demandFilePath) {
          setError('Please select all three CSV files');
          setLoading(false);
          return;
        }

        const nodesResult = await window.electronAPI.readCSV(nodesFilePath);
        const edgesResult = await window.electronAPI.readCSV(edgesFilePath);
        const demandResult = await window.electronAPI.readCSV(demandFilePath);

        if (!nodesResult.success || !edgesResult.success || !demandResult.success) {
          setError(`Failed to read files: ${nodesResult.error || edgesResult.error || demandResult.error}`);
          setLoading(false);
          return;
        }

        nodesText = nodesResult.content;
        edgesText = edgesResult.content;
        demandText = demandResult.content;
        finalPaths = { nodes: nodesFilePath, edges: edgesFilePath, demand: demandFilePath };
      } else {
        // Browser modunda dosya içeriği FileReader ile okunur
        const nodesFileObj = nodesInputRef.current?.files?.[0];
        const edgesFileObj = edgesInputRef.current?.files?.[0];
        const demandFileObj = demandInputRef.current?.files?.[0];

        if (!nodesFileObj || !edgesFileObj || !demandFileObj) {
          setError('Please select all three CSV files');
          setLoading(false);
          return;
        }

        const readFile = (file: File): Promise<string> => {
          return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target?.result as string);
            reader.onerror = reject;
            reader.readAsText(file);
          });
        };

        nodesText = await readFile(nodesFileObj);
        edgesText = await readFile(edgesFileObj);
        demandText = await readFile(demandFileObj);
        finalPaths = { nodes: nodesFileObj.name, edges: edgesFileObj.name, demand: demandFileObj.name };
      }

      // CSV içeriklerini satır/sütun matrisine dönüştür
      const nodesRows = parseCSV(nodesText);
      const edgesRows = parseCSV(edgesText);
      const demandRows = parseCSV(demandText);

      if (nodesRows.length < 2 || edgesRows.length < 2) {
        throw new Error('Invalid CSV files');
      }

      // Header satırlarından kolon indekslerini esnek şekilde bul (schema farklarına tolerans)
      const nodeHeaders = nodesRows[0].map(h => h.toLowerCase());
      const edgeHeaders = edgesRows[0].map(h => h.toLowerCase());
      const demandHeaders = demandRows[0].map(h => h.toLowerCase()); // (şu an kullanılmıyor, ileride gerekebilir)

      const nodeIdIdx = nodeHeaders.findIndex(h => h.includes('node_id') || h.includes('id'));
      const procIdx = nodeHeaders.findIndex(h => h.includes('s_ms') || h.includes('processing'));
      const rNodeIdx = nodeHeaders.findIndex(h => h.includes('r_node') || h.includes('reliability'));

      const srcIdx = edgeHeaders.findIndex(h => h.includes('src') || h.includes('source'));
      const dstIdx = edgeHeaders.findIndex(h => h.includes('dst') || h.includes('target') || h.includes('dest'));
      const capIdx = edgeHeaders.findIndex(h => h.includes('capacity') || h.includes('bandwidth'));
      const delayIdx = edgeHeaders.findIndex(h => h.includes('delay'));
      const rLinkIdx = edgeHeaders.findIndex(h => h.includes('r_link') || h.includes('reliability'));

      // GraphData.nodes oluştur (GraphView tarafının beklediği format)
      const nodes: GraphData['nodes'] = [];
      const nodeMap = new Map<number, any>(); // İleride lookup için kullanılabilir

      for (let i = 1; i < nodesRows.length; i++) {
        const row = nodesRows[i];
        if (row.length <= nodeIdIdx) continue;

        const nodeId = parseInt(row[nodeIdIdx]);
        const procDelay = procIdx >= 0 ? normalizeDecimal(row[procIdx] || '0') : 0;
        const reliability = rNodeIdx >= 0 ? normalizeDecimal(row[rNodeIdx] || '1') : 1;

        nodes.push({
          id: nodeId.toString(),
          data: { processingDelay: procDelay, reliability }
        });
        nodeMap.set(nodeId, { processingDelay: procDelay, reliability });
      }

      // GraphData.edges oluştur (undirected graph olduğu için iki yön ekleniyor)
      const edges: GraphData['edges'] = [];
      const edgeSet = new Set<string>(); // Aynı edge'i iki kere eklememek için

      for (let i = 1; i < edgesRows.length; i++) {
        const row = edgesRows[i];
        if (row.length <= Math.max(srcIdx, dstIdx)) continue;

        const src = parseInt(row[srcIdx]);
        const dst = parseInt(row[dstIdx]);
        const capacity = capIdx >= 0 ? normalizeDecimal(row[capIdx] || '0') : 0;
        const delay = delayIdx >= 0 ? normalizeDecimal(row[delayIdx] || '0') : 0;
        const reliability = rLinkIdx >= 0 ? normalizeDecimal(row[rLinkIdx] || '1') : 1;

        const key1 = `${src}-${dst}`;
        const key2 = `${dst}-${src}`;

        if (!edgeSet.has(key1)) {
          edges.push({
            source: src.toString(),
            target: dst.toString(),
            data: { capacity, delay, reliability }
          });
          edgeSet.add(key1);
        }

        if (!edgeSet.has(key2)) {
          edges.push({
            source: dst.toString(),
            target: src.toString(),
            data: { capacity, delay, reliability }
          });
          edgeSet.add(key2);
        }
      }

      // Basit bağlantılılık bilgisi (minimum veri var mı kontrolü)
      const connected = nodes.length > 0 && edges.length > 0;

      const graphData: GraphData = { nodes, edges };
      const info = {
        nodeCount: nodes.length,
        edgeCount: edges.length / 2, // iki yönlü eklediğimiz için gerçek edge sayısı /2
        connected
      };

      // Hazırlanan graph verisini App'e ilet (App -> Controls/GraphView/Results akışında kullanılır)
      onGraphLoaded(graphData, info, finalPaths);
    } catch (err: any) {
      setError(err.message || 'Failed to load graph');
    } finally {
      setLoading(false);
    }
  };

  // Dosya seçimini Electron (dialog) veya browser (input) moduna göre yönetir
  const handleFileSelect = async (
    event: React.ChangeEvent<HTMLInputElement> | null,
    type: 'nodes' | 'edges' | 'demand'
  ) => {
    if (window.electronAPI && !event) {
      const result = await window.electronAPI.selectFile({
        title: `Select ${type === 'nodes' ? 'Node' : type === 'edges' ? 'Edge' : 'Demand'} Data CSV`,
        filters: [{ name: 'CSV Files', extensions: ['csv'] }]
      });

      if (result.success && result.filePath) {
        if (type === 'nodes') setNodesFilePath(result.filePath);
        else if (type === 'edges') setEdgesFilePath(result.filePath);
        else if (type === 'demand') setDemandFilePath(result.filePath);
      }
    } else if (event) {
      const file = event.target.files?.[0];
      if (file) {
        const fileName = file.name;
        if (type === 'nodes') setNodesFilePath(fileName);
        else if (type === 'edges') setEdgesFilePath(fileName);
        else if (type === 'demand') setDemandFilePath(fileName);
      }
    }
  };

  // UI butonuna basınca doğru dosya seçme yöntemini tetikler
  const handleFileButtonClick = (type: 'nodes' | 'edges' | 'demand') => {
    if (window.electronAPI) {
      handleFileSelect(null, type);
    } else {
      if (type === 'nodes') nodesInputRef.current?.click();
      else if (type === 'edges') edgesInputRef.current?.click();
      else if (type === 'demand') demandInputRef.current?.click();
    }
  };

  return (
    <div className="data-loader">
      <h2>Data Loader</h2>

      <div className="file-input-group">
        <label>Node Data CSV</label>
        <div className="file-selector">
          <input
            ref={nodesInputRef}
            type="file"
            accept=".csv"
            onChange={(e) => handleFileSelect(e, 'nodes')}
            style={{ display: 'none' }}
          />
          <button
            type="button"
            className="file-button"
            onClick={() => handleFileButtonClick('nodes')}
          >
            {nodesFilePath ? path.basename(nodesFilePath) : 'Select File...'}
          </button>
        </div>
      </div>

      <div className="file-input-group">
        <label>Edge Data CSV</label>
        <div className="file-selector">
          <input
            ref={edgesInputRef}
            type="file"
            accept=".csv"
            onChange={(e) => handleFileSelect(e, 'edges')}
            style={{ display: 'none' }}
          />
          <button
            type="button"
            className="file-button"
            onClick={() => handleFileButtonClick('edges')}
          >
            {edgesFilePath ? path.basename(edgesFilePath) : 'Select File...'}
          </button>
        </div>
      </div>

      <div className="file-input-group">
        <label>Demand Data CSV</label>
        <div className="file-selector">
          <input
            ref={demandInputRef}
            type="file"
            accept=".csv"
            onChange={(e) => handleFileSelect(e, 'demand')}
            style={{ display: 'none' }}
          />
          <button
            type="button"
            className="file-button"
            onClick={() => handleFileButtonClick('demand')}
          >
            {demandFilePath ? path.basename(demandFilePath) : 'Select File...'}
          </button>
        </div>
      </div>

      <button
        className="load-button"
        onClick={loadGraph}
        disabled={loading || !nodesFilePath || !edgesFilePath || !demandFilePath}
      >
        {loading ? 'Loading...' : 'Load Graph'}
      </button>

      {error && <div className="error-message">{error}</div>}
    </div>
  );
};

export default DataLoader;

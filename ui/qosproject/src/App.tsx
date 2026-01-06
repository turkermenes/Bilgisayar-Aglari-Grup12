import React, { useState, useCallback, useEffect } from 'react';
import DataLoader from './components/DataLoader';
import GraphView from './components/GraphView';
import Controls from './components/Controls';
import Results from './components/Results';
import { checkElectronAPI } from './utils/electronCheck';
import './App.css';

export interface GraphData {
  nodes: Array<{ id: string; data: any }>;
  edges: Array<{ source: string; target: string; data: any }>;
}

export interface PathResult {
  ok: boolean;
  best_path?: number[];
  best_path_str?: string;
  metrics?: {
    total_cost: number;
    delay_ms: number;
    reliability_cost: number;
    resource_cost: number;
  };
  time_sec: number;
  error?: string;
}

function App() {
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [graphInfo, setGraphInfo] = useState<{ nodeCount: number; edgeCount: number; connected: boolean } | null>(null);
  const [csvPaths, setCsvPaths] = useState<{ nodes: string; edges: string; demand: string } | null>(null);
  const [selectedPath, setSelectedPath] = useState<number[] | null>(null);
  const [result, setResult] = useState<PathResult | null>(null);
  const [loading, setLoading] = useState(false);

  const [isElectron, setIsElectron] = useState(false);

  
  useEffect(() => {
    const checkElectron = async () => {
  
      await new Promise(resolve => setTimeout(resolve, 500));
      
      
      if (!window.electronAPI) {
        console.log('[App] window.electronAPI not available - running in browser mode');
        setIsElectron(false);
        return;
      }

      try {
        const pingResult = await window.electronAPI.ping();
        if (pingResult === 'pong') {
          console.log('[App] React log: ping -> pong');
          setIsElectron(true);
        } else {
          console.warn('[App] Ping test returned unexpected result:', pingResult);
          setIsElectron(false);
        }
      } catch (err) {
        console.error('[App] Ping test failed:', err);
        setIsElectron(false);
      }
    };

    checkElectron();
  }, []);

  const handleGraphLoaded = useCallback((data: GraphData, info: { nodeCount: number; edgeCount: number; connected: boolean }, paths: { nodes: string; edges: string; demand: string }) => {
    setGraphData(data);
    setGraphInfo(info);
    setCsvPaths(paths);
    setSelectedPath(null);
    setResult(null);
  }, []);

  const handlePathFound = useCallback((path: number[], result: PathResult) => {
    setSelectedPath(path);
    setResult(result);
  }, []);

  return (
    <div className="app-container">
      <div className="app-header">
        <h1>QoS Multi-Objective Routing</h1>
        <p>ACO & Genetic Algorithm Path Optimization</p>
        {!isElectron && (
          <div style={{ 
            background: '#ff9800', 
            color: 'white', 
            padding: '0.5rem 1rem', 
            marginTop: '0.5rem',
            borderRadius: '4px',
            fontSize: '0.9rem'
          }}>
            ⚠️ Running in browser mode. Please run in Electron for full functionality.
          </div>
        )}
      </div>
      <div className="app-content">
        <div className="app-sidebar left">
          <DataLoader onGraphLoaded={handleGraphLoaded} />
          {graphData && csvPaths && (
            <Controls
              csvPaths={csvPaths}
              graphData={graphData}
              onPathFound={handlePathFound}
              loading={loading}
              setLoading={setLoading}
            />
          )}
        </div>
        <div className="app-main">
          <GraphView
            graphData={graphData}
            selectedPath={selectedPath}
          />
        </div>
        <div className="app-sidebar right">
          {graphInfo && (
            <div className="graph-info-panel">
              <h3>Graph Info</h3>
              <p>Nodes: {graphInfo.nodeCount}</p>
              <p>Edges: {graphInfo.edgeCount}</p>
              <p>Connected: {graphInfo.connected ? 'Yes' : 'No'}</p>
            </div>
          )}
          <Results result={result} />
        </div>
      </div>
    </div>
  );
}

export default App;


import React from 'react';
import { PathResult } from '../App';
import './Results.css';

interface ResultsProps {
  // Solver’dan dönen sonuç objesi (ok/error + path + metrikler + süre)
  result: PathResult | null;
}

const Results: React.FC<ResultsProps> = ({ result }) => {
  // Henüz solver çalışmadıysa kullanıcıya boş durum ekranı göster
  if (!result) {
    return (
      <div className="results">
        <h2>Results</h2>
        <p className="results-empty">Run an algorithm to see results</p>
      </div>
    );
  }

  // Solver hata döndürdüyse hata mesajını göster
  if (!result.ok) {
    return (
      <div className="results">
        <h2>Results</h2>
        <div className="results-error">
          <strong>Error:</strong> {result.error || 'No path found'}
        </div>
      </div>
    );
  }

  // Başarılı durumda solver’ın formatladığı path string + metrikler + çalışma süresi
  const { best_path_str, metrics, time_sec } = result;

  return (
    <div className="results">
      <h2>Results</h2>

      <div className="result-section">
        <h3>Best Path</h3>
        <div className="path-display">{best_path_str}</div>
      </div>

      {/* Metrikler solver’dan geliyorsa ekranda göster (bazı durumlarda null olabilir) */}
      {metrics && (
        <div className="result-section">
          <h3>Metrics</h3>
          <div className="metrics-grid">
            <div className="metric-item">
              <label>Total Cost</label>
              <value>{metrics.total_cost.toFixed(4)}</value>
            </div>
            <div className="metric-item">
              <label>Total Delay</label>
              <value>{metrics.delay_ms.toFixed(2)} ms</value>
            </div>
            <div className="metric-item">
              <label>Reliability Cost</label>
              <value>{metrics.reliability_cost.toFixed(4)}</value>
            </div>
            <div className="metric-item">
              <label>Resource Cost</label>
              <value>{metrics.resource_cost.toFixed(4)}</value>
            </div>
          </div>
        </div>
      )}

      <div className="result-section">
        <h3>Performance</h3>
        <div className="metric-item">
          <label>Runtime</label>
          <value>{time_sec.toFixed(3)} seconds</value>
        </div>
      </div>
    </div>
  );
};

export default Results;

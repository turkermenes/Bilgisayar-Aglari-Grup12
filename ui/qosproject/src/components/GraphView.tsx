import React, { useEffect, useRef } from 'react';
import cytoscape from 'cytoscape';
import { GraphData } from '../App';
import { generateLandPositions } from '../utils/generateLandPositions';
import './GraphView.css';

interface GraphViewProps {
  // Yüklenen graph verisi . Null ise çizim yapılmaz.
  graphData: GraphData | null;
  // Solver’dan gelen en iyi yol (node id listesi). Null ise sadece node’lar görünür.
  selectedPath: number[] | null;
}

const GraphView: React.FC<GraphViewProps> = ({ graphData, selectedPath }) => {
  // Cytoscape’in render edeceği DOM container
  const cyContainerRef = useRef<HTMLDivElement>(null);
  // Cytoscape instance’ını saklayıp update/destroy yönetmek için
  const cyRef = useRef<cytoscape.Core | null>(null);

  // GraphData değişince cytoscape graph’ını yeniden kurar 
  useEffect(() => {
    if (!cyContainerRef.current || !graphData) return;

    const initGraph = async () => {
      const container = cyContainerRef.current;
      if (!container) return;

      // Yeni graph çizmeden önce eski instance varsa temizle
      if (cyRef.current) {
        cyRef.current.destroy();
      }

      const width = container.offsetWidth;
      const height = container.offsetHeight;

      // Node’ları harita üzerinde daha düzgün konumlandırmak için pozisyon üret
      const nodeIds = graphData.nodes.map(n => n.id.toString());
      const positions = await generateLandPositions('/world-map.jpg', nodeIds, {
        width,
        height,
        landThreshold: 220,
        minDistPx: 25
      });

      // Cytoscape: UI tarafındaki GraphData -> cytoscape elements dönüşümü
      const cy = cytoscape({
        container: container,
        elements: {
          nodes: graphData.nodes.map(node => ({
            data: { id: node.id, ...node.data },
            // Eğer pozisyon üretilemezse rastgele fallback konum
            position: positions[node.id.toString()] || { x: Math.random() * width, y: Math.random() * height }
          })),
          edges: graphData.edges.map(edge => ({
            data: {
              id: `${edge.source}-${edge.target}`,
              source: edge.source,
              target: edge.target
            }
          }))
        },
        // Görsel stil: default edge’leri gizleyip sadece seçilen path’i vurguluyoruz
        style: [
          {
            selector: 'node',
            style: {
              'width': 12,
              'height': 12,
              'background-color': '#667eea',
              'label': 'data(id)',
              'font-size': '8px',
              'color': '#333',
              'text-valign': 'center',
              'text-halign': 'center',
            }
          },
          {
            selector: 'edge',
            style: { 'display': 'none' }
          },
          {
            selector: 'edge.path-edge',
            style: {
              'display': 'element',
              'line-color': '#ff0000',
              'width': 6,
              'opacity': 1,
              'curve-style': 'bezier',
              'z-index': 999
            }
          },
          {
            selector: 'node.path-node',
            style: {
              'background-color': '#ff0000',
              'width': 25,
              'height': 25,
              'color': '#fff',
              'z-index': 1000,
              'text-outline-color': '#ff0000',
              'text-outline-width': 2
            }
          }
        ],
        // preset layout: position’ları biz veriyoruz
        layout: { name: 'preset' },

        // Kullanıcı etkileşimlerini kapatıp harita gibi “sabit” görünüm sağlıyoruz
        userZoomingEnabled: false,
        userPanningEnabled: false,
        boxSelectionEnabled: false,
        autoungrabify: true
      });

      cyRef.current = cy;
      // İlk ekranda graph’ı container içine oturt
      cy.fit(undefined, 40);
    };

    initGraph();

    // Component unmount veya graph değişiminde cytoscape instance’ını temizle
    return () => {
      if (cyRef.current) {
        cyRef.current.destroy();
        cyRef.current = null;
      }
    };
  }, [graphData]);

  // Solver’dan yeni bir path geldiğinde sadece vurgulamayı günceller (yeniden çizim yapmaz)
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    // Önce eski path highlight sınıflarını temizle
    cy.elements().removeClass('path-node path-edge');
    if (!selectedPath || selectedPath.length < 2) return;

    // Path üzerindeki node’ları işaretle
    selectedPath.forEach(nodeId => {
      cy.getElementById(nodeId.toString()).addClass('path-node');
    });

    // Path üzerindeki edge’leri işaretle (graph undirected olduğu için iki yön kontrol ediliyor)
    for (let i = 0; i < selectedPath.length - 1; i++) {
      const source = selectedPath[i].toString();
      const target = selectedPath[i + 1].toString();
      const edge = cy.edges(`[source="${source}"][target="${target}"], [source="${target}"][target="${source}"]`);
      edge.addClass('path-edge');
    }
  }, [selectedPath]);

  return (
    <div className="graph-view">
      <div className="graph-bg" />
      <div ref={cyContainerRef} className="graph-cy" />
    </div>
  );
};

export default GraphView;

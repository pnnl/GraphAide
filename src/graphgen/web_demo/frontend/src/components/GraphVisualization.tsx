import React, { useEffect, useRef } from 'react';
import Graph from 'graphology';
import { random } from 'graphology-layout';
import Sigma from 'sigma';
import type { Node, Edge } from '../types/api';
import './GraphVisualization.css';

interface Props {
  nodes: Node[];
  edges: Edge[];
}

// Simple rotating color palettes
const NODE_COLORS = [
  '#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8',
  '#F7DC6F', '#BB8FCE', '#85C1E2', '#F38181', '#42A5F5',
  '#66BB6A', '#AB47BC', '#FFB347', '#DDA0DD', '#20B2AA'
];

const EDGE_COLORS = [
  '#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8',
  '#F7DC6F', '#BB8FCE', '#85C1E2', '#F38181', '#42A5F5'
];

export function GraphVisualization({ nodes, edges }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || nodes.length === 0) return;

    // Delay to ensure DOM ready
    const timeoutId = setTimeout(() => {
      try {
        // Create type to color maps
        const nodeTypeMap: Record<string, string> = {};
        const edgeTypeMap: Record<string, string> = {};

        let nodeTypeIndex = 0;
        let edgeTypeIndex = 0;

        nodes.forEach(node => {
          if (!nodeTypeMap[node.node_type]) {
            nodeTypeMap[node.node_type] = NODE_COLORS[nodeTypeIndex % NODE_COLORS.length];
            nodeTypeIndex++;
          }
        });

        edges.forEach(edge => {
          if (!edgeTypeMap[edge.edge_type]) {
            edgeTypeMap[edge.edge_type] = EDGE_COLORS[edgeTypeIndex % EDGE_COLORS.length];
            edgeTypeIndex++;
          }
        });

        // Build graph
        const graph = new Graph();

        // Add nodes
        nodes.forEach(node => {
          const color = nodeTypeMap[node.node_type];
          const degree = edges.filter(
            e => e.source_id === node.node_id || e.target_id === node.node_id
          ).length;
          const size = Math.max(8, Math.min(25, 12 + degree * 1.5));

          graph.addNode(node.node_id, {
            label: node.node_name,
            size: size,
            color: color,
            x: Math.random() * 100,
            y: Math.random() * 100,
          });
        });

        // Add edges
        edges.forEach(edge => {
          if (graph.hasNode(edge.source_id) && graph.hasNode(edge.target_id)) {
            const color = edgeTypeMap[edge.edge_type];
            try {
              graph.addDirectedEdge(edge.source_id, edge.target_id, {
                color: color,
                size: 1.5,
              });
            } catch {
              // Edge already exists
            }
          }
        });

        // Apply random layout
        if (graph.order > 0) {
          random.assign(graph);
        }

        // Create Sigma
        if (containerRef.current) {
          const sigma = new Sigma(graph, containerRef.current, {
            renderLabels: true,
            renderEdgeLabels: false,
            labelDensity: 0.3,
            labelGridCellSize: 100,
            labelRenderedSizeThreshold: 8,
            labelSize: 12,
            labelFont: 'Arial',
            allowInvalidContainer: true,
          });

          return () => sigma.kill();
        }
      } catch (err) {
        console.error('Error initializing graph:', err);
      }
    }, 100);

    return () => clearTimeout(timeoutId);
  }, [nodes, edges]);

  const nodeTypeStats = React.useMemo(() => {
    const stats: Record<string, number> = {};
    nodes.forEach(node => {
      stats[node.node_type] = (stats[node.node_type] || 0) + 1;
    });
    return stats;
  }, [nodes]);

  const edgeTypeStats = React.useMemo(() => {
    const stats: Record<string, number> = {};
    edges.forEach(edge => {
      stats[edge.edge_type] = (stats[edge.edge_type] || 0) + 1;
    });
    return stats;
  }, [edges]);

  return (
    <div className="graph-visualization">
      <div className="graph-header">
        <h3>Knowledge Graph Network</h3>
        <div className="header-stats">
          <span>🔹 {nodes.length} nodes</span>
          <span>🔗 {edges.length} edges</span>
        </div>
      </div>

      <div className="graph-main">
        <div className="graph-canvas" ref={containerRef} />

        <div className="graph-sidebar">
          <div className="sidebar-section">
            <h4>📈 Statistics</h4>
            <div className="stat-items">
              <div className="stat-item">
                <span className="stat-label">Nodes</span>
                <span className="stat-value">{nodes.length}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Edges</span>
                <span className="stat-value">{edges.length}</span>
              </div>
            </div>
          </div>

          <div className="sidebar-section">
            <h4>🏷️ Node Types</h4>
            <div className="legend">
              {Object.entries(nodeTypeStats).map(([type, count], idx) => (
                <div key={`node-${type}`} className="legend-item">
                  <span
                    className="legend-color"
                    style={{ backgroundColor: NODE_COLORS[idx % NODE_COLORS.length] }}
                  />
                  <span className="legend-label">{type}</span>
                  <span className="legend-count">({count})</span>
                </div>
              ))}
            </div>
          </div>

          <div className="sidebar-section">
            <h4>🔗 Edge Types</h4>
            <div className="legend">
              {Object.entries(edgeTypeStats).map(([type, count], idx) => (
                <div key={`edge-${type}`} className="legend-item">
                  <span
                    className="legend-color"
                    style={{ backgroundColor: EDGE_COLORS[idx % EDGE_COLORS.length] }}
                  />
                  <span className="legend-label">{type}</span>
                  <span className="legend-count">({count})</span>
                </div>
              ))}
            </div>
          </div>

          <div className="sidebar-section tips">
            <h4>💡 Tips</h4>
            <ul>
              <li>Scroll to zoom</li>
              <li>Drag to pan</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

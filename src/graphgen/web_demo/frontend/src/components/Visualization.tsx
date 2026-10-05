import React, { useMemo } from 'react';
import { SigmaContainer, ZoomControl, FullScreenControl } from '@react-sigma/core';
import Graph from 'graphology';
import { circular, random } from 'graphology-layout';
import FA2Layout from 'graphology-layout-forceatlas2';
import { Node, Edge } from '../types/api';
import './Visualization.css';

interface Props {
  nodes: Node[];
  edges: Edge[];
}

const NODE_TYPE_COLORS: Record<string, string> = {
  'Person': '#FF6B6B',
  'Organization': '#4ECDC4',
  'Location': '#45B7D1',
  'Event': '#FFA07A',
  'Product': '#98D8C8',
  'Technology': '#F7DC6F',
  'Document': '#BB8FCE',
  'Concept': '#85C1E2',
};

const getNodeColor = (nodeType: string): string => {
  return NODE_TYPE_COLORS[nodeType] || '#999';
};

export function Visualization({ nodes, edges }: Props) {
  const [layoutType, setLayoutType] = React.useState<'force' | 'circular'>('force');

  // Build graph
  const graph = useMemo(() => {
    const g = new Graph();

    // Add nodes
    nodes.forEach(node => {
      const color = getNodeColor(node.node_type);
      g.addNode(node.node_id, {
        label: node.node_name,
        size: 15,
        color: color,
        type: node.node_type,
      });
    });

    // Add edges
    edges.forEach((edge, idx) => {
      try {
        const sourceId = edge.source_id || edge.source;
        const targetId = edge.target_id || edge.target;

        if (g.hasNode(sourceId) && g.hasNode(targetId)) {
          g.addDirectedEdge(sourceId, targetId, {
            label: edge.edge_type,
            type: 'arrow',
          });
        }
      } catch (e) {
        // Edge references node that doesn't exist, skip it
      }
    });

    // Apply layout
    if (layoutType === 'force') {
      const fa2 = new FA2Layout(g);
      fa2.start();
      setTimeout(() => fa2.stop(), 2000);
    } else {
      circular.assign(g);
    }

    return g;
  }, [nodes, edges, layoutType]);

  // Statistics
  const nodeTypeStats = useMemo(() => {
    const stats: Record<string, number> = {};
    nodes.forEach(node => {
      stats[node.node_type] = (stats[node.node_type] || 0) + 1;
    });
    return stats;
  }, [nodes]);

  const avgConnections = edges.length > 0 ? (edges.length / nodes.length).toFixed(2) : '0';

  return (
    <div className="visualization">
      <div className="viz-controls">
        <button
          className={`btn ${layoutType === 'force' ? 'active' : ''}`}
          onClick={() => setLayoutType('force')}
        >
          Force-Directed Layout
        </button>
        <button
          className={`btn ${layoutType === 'circular' ? 'active' : ''}`}
          onClick={() => setLayoutType('circular')}
        >
          Circular Layout
        </button>
      </div>

      <div className="graph-container">
        {graph.order > 0 ? (
          <SigmaContainer
            graph={graph}
            settings={{
              nodeProgramClasses: {},
              edgeProgramClasses: {},
              renderLabels: true,
              renderEdgeLabels: false,
              defaultNodeType: 'circle',
              defaultEdgeType: 'arrow',
              labelDensity: 0.3,
              labelGridCellSize: 60,
              labelRenderedSizeThreshold: 15,
              labelFont: 'Arial',
              zoomToFitMarginPx: 50,
            }}
          >
            <ZoomControl />
            <FullScreenControl />
          </SigmaContainer>
        ) : (
          <div className="empty-graph">
            <p>No graph data to visualize</p>
          </div>
        )}
      </div>

      <div className="viz-info">
        <p>
          Showing {nodes.length} nodes and {edges.length} edges
          {nodes.length > 100 && ' (large graph - may be slow)'}
        </p>
        <p style={{ fontSize: '11px', color: '#aaa' }}>
          💡 Tip: Scroll to zoom, drag to pan, double-click to reset view
        </p>
      </div>

      <div className="graph-stats">
        <h3>Graph Statistics</h3>
        <div className="stats-grid">
          <div className="stat-card">
            <span className="stat-label">Total Nodes</span>
            <span className="stat-value">{nodes.length}</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Total Edges</span>
            <span className="stat-value">{edges.length}</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Avg Connections</span>
            <span className="stat-value">{avgConnections}</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Node Types</span>
            <span className="stat-value">{Object.keys(nodeTypeStats).length}</span>
          </div>
        </div>

        <h4>Node Types Breakdown</h4>
        <div className="node-types-list">
          {Object.entries(nodeTypeStats).map(([type, count]) => (
            <div key={type} className="type-item">
              <span
                className="type-color"
                style={{ backgroundColor: getNodeColor(type) }}
              />
              <span className="type-name">{type}</span>
              <span className="type-count">{count}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

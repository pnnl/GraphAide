import React, { useState } from 'react';
import { WorkflowResult } from '../types/api';
import { GraphVisualization } from './GraphVisualization';
import './ResultViewer.css';

interface Props {
  result: WorkflowResult;
}

export function ResultViewer({ result }: Props) {
  const [tab, setTab] = useState<'graph' | 'nodes' | 'edges' | 'json'>('graph');

  const downloadJSON = () => {
    const json = JSON.stringify(result, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `graphaide_result_${Date.now()}.json`;
    a.click();
  };

  const copyJSON = () => {
    navigator.clipboard.writeText(JSON.stringify(result, null, 2));
    alert('JSON copied to clipboard!');
  };

  return (
    <div className="result-viewer">
      <div className="result-tabs">
        <button
          className={`tab ${tab === 'graph' ? 'active' : ''}`}
          onClick={() => setTab('graph')}
        >
          📊 Graph
        </button>
        <button
          className={`tab ${tab === 'nodes' ? 'active' : ''}`}
          onClick={() => setTab('nodes')}
        >
          Nodes ({result.nodes?.length || 0})
        </button>
        <button
          className={`tab ${tab === 'edges' ? 'active' : ''}`}
          onClick={() => setTab('edges')}
        >
          Edges ({result.edges?.length || 0})
        </button>
        <button
          className={`tab ${tab === 'json' ? 'active' : ''}`}
          onClick={() => setTab('json')}
        >
          JSON
        </button>
      </div>

      <div className="tab-content">
        {tab === 'graph' && (
          <div className="graph-tab">
            <GraphVisualization
              nodes={result.nodes || []}
              edges={result.edges || []}
            />
          </div>
        )}

        {tab === 'nodes' && (
          <div className="nodes-list">
            {result.nodes?.slice(0, 50).map((node, idx) => (
              <div key={idx} className="node-item">
                <strong>{node.node_name}</strong>
                <span className="node-type">{node.node_type}</span>
                {node.wikidata_id && <span className="wikidata">{node.wikidata_id}</span>}
              </div>
            ))}
            {result.nodes && result.nodes.length > 50 && (
              <p className="more">+{result.nodes.length - 50} more nodes</p>
            )}
          </div>
        )}

        {tab === 'edges' && (
          <div className="edges-list">
            {result.edges?.slice(0, 50).map((edge, idx) => (
              <div key={idx} className="edge-item">
                <span className="source">{edge.source_id}</span>
                <span className="relation">--[{edge.edge_type}]--&gt;</span>
                <span className="target">{edge.target_id}</span>
              </div>
            ))}
            {result.edges && result.edges.length > 50 && (
              <p className="more">+{result.edges.length - 50} more edges</p>
            )}
          </div>
        )}

        {tab === 'json' && (
          <div className="json-viewer">
            <div className="json-actions">
              <button onClick={copyJSON}>📋 Copy</button>
              <button onClick={downloadJSON}>⬇️ Download</button>
            </div>
            <pre>{JSON.stringify(result, null, 2)}</pre>
          </div>
        )}
      </div>
    </div>
  );
}

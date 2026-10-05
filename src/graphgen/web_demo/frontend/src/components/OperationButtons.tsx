import React from 'react';
import './OperationButtons.css';

interface Props {
  onOperation: (op: string) => void;
  disabled?: boolean;
}

export function OperationButtons({ onOperation, disabled = false }: Props) {
  return (
    <div className="operation-buttons">
      <button
        className="btn btn-primary"
        onClick={() => onOperation('extract')}
        disabled={disabled}
      >
        🔄 Extract Nodes & Edges
      </button>
      <button
        className="btn btn-primary"
        onClick={() => onOperation('extract-merge')}
        disabled={disabled}
      >
        ⚡ Extract & Merge Duplicates
      </button>
      <button
        className="btn btn-primary"
        onClick={() => onOperation('ingest')}
        disabled={disabled}
      >
        💾 Ingest to Neo4j
      </button>
      <button
        className="btn btn-primary"
        onClick={() => onOperation('load-json')}
        disabled={disabled}
      >
        📥 Load Pre-extracted JSON
      </button>
      <button
        className="btn btn-primary"
        onClick={() => onOperation('load-vector')}
        disabled={disabled}
      >
        📊 Load to Vector Store
      </button>
    </div>
  );
}

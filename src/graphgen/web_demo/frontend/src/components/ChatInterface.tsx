import React, { useState } from 'react';
import { Node, Edge } from '../types/api';
import { graphaideAPI } from '../services/graphaideAPI';
import './ChatInterface.css';

interface Props {
  nodes: Node[];
  edges: Edge[];
}

export function ChatInterface({ nodes, edges }: Props) {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [useVectorStore, setUseVectorStore] = useState(true);

  const handleQuery = async () => {
    if (!question.trim()) return;

    setLoading(true);
    try {
      const result = await graphaideAPI.query(question, useVectorStore);
      setAnswer(result.answer || 'No answer generated');
    } catch (error) {
      setAnswer(`Error: ${error instanceof Error ? error.message : 'Query failed'}`);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleQuery();
    }
  };

  return (
    <div className="chat-interface">
      <div className="chat-options">
        <label>
          <input
            type="checkbox"
            checked={useVectorStore}
            onChange={(e) => setUseVectorStore(e.target.checked)}
          />
          Use Vector Store (RAG)
        </label>
      </div>

      <div className="chat-input">
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Ask a question about the knowledge graph..."
          disabled={loading}
        />
        <button onClick={handleQuery} disabled={loading || !question.trim()}>
          {loading ? 'Querying...' : 'Send'}
        </button>
      </div>

      {answer && (
        <div className="chat-response">
          <div className="response-header">Assistant</div>
          <div className="response-text">{answer}</div>
        </div>
      )}

      <div className="stats">
        <p>📊 Nodes available: <strong>{nodes.length}</strong></p>
        <p>🔗 Edges available: <strong>{edges.length}</strong></p>
      </div>
    </div>
  );
}

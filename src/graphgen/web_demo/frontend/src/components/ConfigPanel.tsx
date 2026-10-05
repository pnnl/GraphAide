import React from 'react';
import { ConfigState } from '../types/api';
import './ConfigPanel.css';

interface Props {
  config: ConfigState;
  onConfigChange: (config: ConfigState) => void;
}

export function ConfigPanel({ config, onConfigChange }: Props) {
  const [expanded, setExpanded] = React.useState({
    llm: true,
    neo4j: false,
    vectorstore: false,
    langfuse: false,
    optional: false,
  });

  const toggleSection = (key: keyof typeof expanded) => {
    setExpanded(p => ({ ...p, [key]: !p[key] }));
  };

  const updateConfig = (key: keyof ConfigState, value: any) => {
    onConfigChange({ ...config, [key]: value });
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    alert('Copied to clipboard!');
  };

  return (
    <div className="config-panel">
      <h2>⚙️ Configuration</h2>

      {/* LLM Settings */}
      <div className="config-section">
        <button
          className="section-toggle"
          onClick={() => toggleSection('llm')}
        >
          {expanded.llm ? '▼' : '▶'} LLM Settings
        </button>
        {expanded.llm && (
          <div className="section-content">
            <label>Provider</label>
            <select
              value={config.modelProvider}
              onChange={(e) => updateConfig('modelProvider', e.target.value)}
            >
              <option>openai</option>
              <option>anthropic</option>
              <option>google</option>
              <option>bedrock</option>
            </select>

            <label>Model Name</label>
            <input
              type="text"
              value={config.modelName}
              onChange={(e) => updateConfig('modelName', e.target.value)}
            />

            <label>API Key</label>
            <div className="input-with-button">
              <input
                type="password"
                value={config.apiKey}
                onChange={(e) => updateConfig('apiKey', e.target.value)}
                placeholder="sk-..."
              />
              <button onClick={() => copyToClipboard(config.apiKey)}>Copy</button>
            </div>

            <label>Temperature</label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={config.temperature}
              onChange={(e) => updateConfig('temperature', parseFloat(e.target.value))}
            />
            <span>{config.temperature.toFixed(1)}</span>

            <label>Max Tokens</label>
            <input
              type="number"
              value={config.maxTokens}
              onChange={(e) => updateConfig('maxTokens', parseInt(e.target.value))}
            />

            <label>Proxy URL (Optional)</label>
            <input
              type="text"
              value={config.proxyUrl}
              onChange={(e) => updateConfig('proxyUrl', e.target.value)}
              placeholder="http://proxy.example.com:8080"
            />
          </div>
        )}
      </div>

      {/* Neo4j Settings */}
      <div className="config-section">
        <button
          className="section-toggle"
          onClick={() => toggleSection('neo4j')}
        >
          {expanded.neo4j ? '▼' : '▶'} Neo4j Configuration
        </button>
        {expanded.neo4j && (
          <div className="section-content">
            <label>URI</label>
            <input
              type="text"
              value={config.neoUri}
              onChange={(e) => updateConfig('neoUri', e.target.value)}
            />

            <label>Username</label>
            <input
              type="text"
              value={config.neoUsername}
              onChange={(e) => updateConfig('neoUsername', e.target.value)}
            />

            <label>Password</label>
            <div className="input-with-button">
              <input
                type="password"
                value={config.neoPassword}
                onChange={(e) => updateConfig('neoPassword', e.target.value)}
              />
              <button onClick={() => copyToClipboard(config.neoPassword)}>Copy</button>
            </div>

            <button className="test-button">Test Connection</button>
          </div>
        )}
      </div>

      {/* Vector Store Settings */}
      <div className="config-section">
        <button
          className="section-toggle"
          onClick={() => toggleSection('vectorstore')}
        >
          {expanded.vectorstore ? '▼' : '▶'} Vector Store Config
        </button>
        {expanded.vectorstore && (
          <div className="section-content">
            <label>Provider</label>
            <select
              value={config.vectorStoreProvider}
              onChange={(e) => updateConfig('vectorStoreProvider', e.target.value)}
            >
              <option>ChromaDB</option>
              <option>Qdrant</option>
            </select>

            <label>Store Name</label>
            <input
              type="text"
              value={config.vectorStoreName}
              onChange={(e) => updateConfig('vectorStoreName', e.target.value)}
            />

            <label>Store Path</label>
            <input
              type="text"
              value={config.vectorStorePath}
              onChange={(e) => updateConfig('vectorStorePath', e.target.value)}
            />

            <button className="test-button">Test Connection</button>
          </div>
        )}
      </div>

      {/* Observability: Langfuse */}
      <div className="config-section">
        <button
          className="section-toggle"
          onClick={() => toggleSection('langfuse')}
        >
          {expanded.langfuse ? '▼' : '▶'} 📊 Observability: Langfuse
        </button>
        {expanded.langfuse && (
          <div className="section-content">
            <div className="langfuse-warning">
              💡 <strong>Note:</strong> Values are stored in browser memory only (not persisted). They'll be passed to API calls when enabled.
            </div>

            <label>
              <input
                type="checkbox"
                checked={config.langfuseEnabled}
                onChange={(e) => updateConfig('langfuseEnabled', e.target.checked)}
              />
              Enable Langfuse Observability
            </label>

            {config.langfuseEnabled && (
              <>
                <label>Public Key</label>
                <div className="input-with-button">
                  <input
                    type="password"
                    value={config.langfusePublicKey}
                    onChange={(e) => updateConfig('langfusePublicKey', e.target.value)}
                    placeholder="pk-lf-..."
                  />
                  <button onClick={() => copyToClipboard(config.langfusePublicKey)}>Copy</button>
                </div>

                <label>Secret Key</label>
                <div className="input-with-button">
                  <input
                    type="password"
                    value={config.langfuseSecretKey}
                    onChange={(e) => updateConfig('langfuseSecretKey', e.target.value)}
                    placeholder="sk-lf-..."
                  />
                  <button onClick={() => copyToClipboard(config.langfuseSecretKey)}>Copy</button>
                </div>

                <label>Base URL</label>
                <input
                  type="text"
                  value={config.langfuseBaseUrl}
                  onChange={(e) => updateConfig('langfuseBaseUrl', e.target.value)}
                  placeholder="https://us.cloud.langfuse.com"
                />

                <label>Service Name</label>
                <input
                  type="text"
                  value={config.langfuseServiceName}
                  onChange={(e) => updateConfig('langfuseServiceName', e.target.value)}
                  placeholder="graphaide"
                />

                <label>Session Name</label>
                <input
                  type="text"
                  value={config.langfuseSessionName}
                  onChange={(e) => updateConfig('langfuseSessionName', e.target.value)}
                  placeholder="GraphAide-Development"
                />

                <label>Environment</label>
                <select
                  value={config.langfuseEnvironment}
                  onChange={(e) => updateConfig('langfuseEnvironment', e.target.value)}
                >
                  <option>development</option>
                  <option>staging</option>
                  <option>production</option>
                </select>

                <label>
                  <input
                    type="checkbox"
                    checked={config.langfuseDebug}
                    onChange={(e) => updateConfig('langfuseDebug', e.target.checked)}
                  />
                  Debug Mode
                </label>
              </>
            )}
          </div>
        )}
      </div>

      {/* Save/Load */}
      <div className="config-actions">
        <button className="btn-secondary">Load Config</button>
        <button className="btn-secondary">Save Config</button>
        <button className="btn-secondary">Use Defaults</button>
      </div>
    </div>
  );
}

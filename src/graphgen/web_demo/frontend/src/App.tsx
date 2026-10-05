import React, { useState, useEffect } from 'react';
import { ConfigPanel } from './components/ConfigPanel';
import { FileUpload } from './components/FileUpload';
import { OperationButtons } from './components/OperationButtons';
import { ResultViewer } from './components/ResultViewer';
import { ChatInterface } from './components/ChatInterface';
import { LoadingSpinner } from './components/LoadingSpinner';
import { Visualization } from './components/Visualization';
import { WorkflowResult, ConfigState, Node, Edge } from './types/api';
import './App.css';

type Tab = 'operations' | 'chat' | 'visualize';

export function App() {
  const [config, setConfig] = useState<ConfigState>({
    modelProvider: 'openai',
    modelName: 'gpt-4o',
    apiKey: '',
    temperature: 0.0,
    maxTokens: 8192,
    proxyUrl: '',
    neoUri: 'bolt://localhost:7687',
    neoUsername: 'neo4j',
    neoPassword: '',
    vectorStoreProvider: 'ChromaDB',
    vectorStorePath: './chroma',
    vectorStoreName: 'GA_VDB',
    langfuseEnabled: false,
    langfusePublicKey: '',
    langfuseSecretKey: '',
    langfuseBaseUrl: 'https://us.cloud.langfuse.com',
    langfuseDebug: false,
    langfuseServiceName: 'graphaide',
    langfuseSessionName: 'GraphAide-Development',
    langfuseEnvironment: 'development',
  });

  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<WorkflowResult | null>(null);
  const [executionTime, setExecutionTime] = useState<number>(0);
  const [activeTab, setActiveTab] = useState<Tab>('operations');
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Load all config from backend on mount
  useEffect(() => {
    const loadConfigFromBackend = async () => {
      try {
        console.log('[GraphAide] Loading config from backend...');
        const { graphaideAPI } = await import('./services/graphaideAPI');
        const backendConfig = await graphaideAPI.getFullConfig();

        console.log('[GraphAide] Backend config received:', backendConfig);

        if (backendConfig) {
          console.log('[GraphAide] ✅ Updating ConfigPanel with backend values');
          setConfig(prevConfig => ({
            modelProvider: backendConfig.modelProvider || prevConfig.modelProvider,
            modelName: backendConfig.modelName || prevConfig.modelName,
            apiKey: backendConfig.apiKey || prevConfig.apiKey,
            temperature: backendConfig.temperature !== undefined ? backendConfig.temperature : prevConfig.temperature,
            maxTokens: backendConfig.maxTokens || prevConfig.maxTokens,
            proxyUrl: backendConfig.proxyUrl || prevConfig.proxyUrl,
            neoUri: backendConfig.neoUri || prevConfig.neoUri,
            neoUsername: backendConfig.neoUsername || prevConfig.neoUsername,
            neoPassword: backendConfig.neoPassword || prevConfig.neoPassword,
            vectorStoreProvider: backendConfig.vectorStoreProvider || prevConfig.vectorStoreProvider,
            vectorStorePath: backendConfig.vectorStorePath || prevConfig.vectorStorePath,
            vectorStoreName: backendConfig.vectorStoreName || prevConfig.vectorStoreName,
            langfuseEnabled: backendConfig.langfuseEnabled || false,
            langfusePublicKey: backendConfig.langfusePublicKey || '',
            langfuseSecretKey: backendConfig.langfuseSecretKey || '',
            langfuseBaseUrl: backendConfig.langfuseBaseUrl || 'https://us.cloud.langfuse.com',
            langfuseDebug: backendConfig.langfuseDebug || false,
            langfuseServiceName: backendConfig.langfuseServiceName || 'graphaide',
            langfuseSessionName: backendConfig.langfuseSessionName || 'GraphAide-Development',
            langfuseEnvironment: backendConfig.langfuseEnvironment || 'development',
          }));
        } else {
          console.log('[GraphAide] ⚠️  No backend config returned, using defaults');
        }
      } catch (error) {
        console.error('[GraphAide] ❌ Error loading config from backend:', error);
        console.log('[GraphAide] Using default values');
      }
    };

    loadConfigFromBackend();
  }, []);

  const handleFileUpload = (file: File) => {
    setUploadedFile(file);
    setError(null);
    setResults(null);
  };

  const handleOperation = async (operation: string) => {
    if (!uploadedFile) {
      setError('Please upload a file first');
      return;
    }

    setIsLoading(true);
    setError(null);
    const startTime = Date.now();

    try {
      const { graphaideAPI } = await import('./services/graphaideAPI');

      // Set proxy if configured
      if (config.proxyUrl) {
        graphaideAPI.setProxyUrl(config.proxyUrl);
      }

      // Set Langfuse observability config
      graphaideAPI.setLangfuseConfig(config);

      let result: WorkflowResult;
      switch (operation) {
        case 'extract':
          result = await graphaideAPI.extract(uploadedFile);
          break;
        case 'extract-merge':
          result = await graphaideAPI.extractMerge(uploadedFile);
          break;
        case 'ingest':
          result = await graphaideAPI.ingest(uploadedFile);
          break;
        case 'load-json':
          result = await graphaideAPI.loadJson(uploadedFile);
          break;
        case 'load-vector':
          result = await graphaideAPI.loadVector(uploadedFile);
          break;
        default:
          throw new Error(`Unknown operation: ${operation}`);
      }

      const elapsed = (Date.now() - startTime) / 1000;
      setExecutionTime(elapsed);
      setResults(result);

      if (!result.success) {
        const errorMsg = result.errors?.[0] || 'Operation failed';
        console.error('[GraphAide] Workflow error:', errorMsg);
        console.error('[GraphAide] Full result:', result);
        setError(errorMsg);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error occurred';
      console.error('[GraphAide] Catch error:', message, err);
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="app-container">
      {/* Sidebar */}
      <aside className={`sidebar ${sidebarOpen ? 'open' : 'closed'}`}>
        <button
          className="sidebar-toggle"
          onClick={() => setSidebarOpen(!sidebarOpen)}
        >
          {sidebarOpen ? '◀' : '▶'}
        </button>
        {sidebarOpen && <ConfigPanel config={config} onConfigChange={setConfig} />}
      </aside>

      {/* Main Content */}
      <main className="main-content">
        <header className="header">
          <img src="/graphaide-logo.png" alt="GraphAide Logo" className="logo" />
          <div className="header-text">
            <h1>GraphAide: Multi-agentic Digital Assistant</h1>
            <p>Extract, ingest, and query knowledge graphs</p>
          </div>
        </header>

        {/* Tab Navigation */}
        <div className="tabs">
          <button
            className={`tab ${activeTab === 'operations' ? 'active' : ''}`}
            onClick={() => setActiveTab('operations')}
          >
            📁 Operations
          </button>
          <button
            className={`tab ${activeTab === 'chat' ? 'active' : ''}`}
            onClick={() => setActiveTab('chat')}
          >
            💬 Query
          </button>
          <button
            className={`tab ${activeTab === 'visualize' ? 'active' : ''}`}
            onClick={() => setActiveTab('visualize')}
          >
            📈 Visualize
          </button>
        </div>

        {/* Content Area */}
        <div className="content">
          {activeTab === 'operations' && (
            <>
              <section className="section">
                <h2>Upload File</h2>
                <FileUpload onFileUpload={handleFileUpload} />
                {uploadedFile && (
                  <p className="file-info">
                    ✓ Uploaded: <strong>{uploadedFile.name}</strong> ({(uploadedFile.size / 1024).toFixed(2)} KB)
                  </p>
                )}
              </section>

              <section className="section">
                <h2>Operations</h2>
                <OperationButtons onOperation={handleOperation} disabled={isLoading || !uploadedFile} />
              </section>

              {isLoading && <LoadingSpinner />}

              {error && (
                <div className="error-box">
                  <strong>❌ Error:</strong> {error}
                </div>
              )}

              {results && (
                <section className="section">
                  <h2>Results</h2>
                  <p className="stats">
                    ✓ Success | ⏱️ {executionTime.toFixed(2)}s | 📝 {results.nodes?.length || 0} nodes, {results.edges?.length || 0} edges
                  </p>
                  <ResultViewer result={results} />
                </section>
              )}
            </>
          )}

          {activeTab === 'chat' && (
            <section className="section">
              <h2>Query Knowledge Graph</h2>
              {results ? (
                <ChatInterface nodes={results.nodes || []} edges={results.edges || []} />
              ) : (
                <p className="placeholder">Extract or ingest data first, then query</p>
              )}
            </section>
          )}

          {activeTab === 'visualize' && (
            <section className="section">
              <h2>Visualization</h2>
              {results ? (
                <Visualization nodes={results.nodes || []} edges={results.edges || []} />
              ) : (
                <p className="placeholder">No data to visualize yet</p>
              )}
            </section>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;

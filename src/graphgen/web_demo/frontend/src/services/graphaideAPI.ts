import axios, { AxiosInstance } from 'axios';
import { WorkflowResult, ConfigState } from '../types/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

interface LangfuseConfig {
  langfuse_enabled: boolean;
  langfuse_public_key?: string;
  langfuse_secret_key?: string;
  langfuse_base_url?: string;
  langfuse_debug?: boolean;
  langfuse_service_name?: string;
  langfuse_session_name?: string;
  langfuse_environment?: string;
}

class GraphAideAPIClient {
  private client: AxiosInstance;
  private langfuseConfig: LangfuseConfig | null = null;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 300000, // 5 minutes
    });
  }

  setProxyUrl(proxyUrl: string) {
    if (proxyUrl) {
      this.client = axios.create({
        baseURL: API_BASE_URL,
        httpAgent: new (require('http').Agent)({
          httpProxy: proxyUrl
        }),
        httpsAgent: new (require('https').Agent)({
          httpsProxy: proxyUrl
        }),
        headers: {
          'Content-Type': 'application/json',
        },
        timeout: 300000,
      });
    }
  }

  setLangfuseConfig(config: Partial<ConfigState>) {
    if (config.langfuseEnabled) {
      this.langfuseConfig = {
        langfuse_enabled: true,
        langfuse_public_key: config.langfusePublicKey,
        langfuse_secret_key: config.langfuseSecretKey,
        langfuse_base_url: config.langfuseBaseUrl,
        langfuse_debug: config.langfuseDebug,
        langfuse_service_name: config.langfuseServiceName,
        langfuse_session_name: config.langfuseSessionName,
        langfuse_environment: config.langfuseEnvironment,
      };
    } else {
      this.langfuseConfig = { langfuse_enabled: false };
    }
  }

  private getLangfusePayload() {
    return this.langfuseConfig || { langfuse_enabled: false };
  }

  async extract(
    file: File,
    ontologyPath?: string,
    configPath?: string
  ): Promise<WorkflowResult> {
    const formData = new FormData();
    formData.append('file', file);
    if (ontologyPath) formData.append('ontology', ontologyPath);

    console.log('[GraphAideAPI] Posting to /extract/file');
    try {
      const response = await this.client.post('/extract/file', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      console.log('[GraphAideAPI] Extract response:', response.data);
      return response.data;
    } catch (error) {
      console.error('[GraphAideAPI] Extract error:', error);
      if (error instanceof Error) {
        console.error('[GraphAideAPI] Error message:', error.message);
      }
      throw error;
    }
  }

  async extractMerge(
    file: File,
    configPath?: string
  ): Promise<WorkflowResult> {
    const formData = new FormData();
    formData.append('file', file);

    console.log('[GraphAideAPI] Posting to /extract-merge/file');
    const response = await this.client.post('/extract-merge/file', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    console.log('[GraphAideAPI] Extract-merge response:', response.data);
    console.log('[GraphAideAPI] Nodes:', response.data.nodes);
    console.log('[GraphAideAPI] Edges:', response.data.edges);
    return response.data;
  }

  async ingest(
    file: File,
    configPath?: string
  ): Promise<WorkflowResult> {
    const formData = new FormData();
    formData.append('file', file);

    console.log('[GraphAideAPI] Posting to /ingest/file');
    const response = await this.client.post('/ingest/file', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    console.log('[GraphAideAPI] Ingest response:', response.data);
    return response.data;
  }

  async loadJson(
    jsonFile: File,
    configPath?: string
  ): Promise<WorkflowResult> {
    const formData = new FormData();
    formData.append('file', jsonFile);

    console.log('[GraphAideAPI] Posting to /load-json');
    const response = await this.client.post('/load-json', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    console.log('[GraphAideAPI] Load-json response:', response.data);
    return response.data;
  }

  async loadVector(
    file: File,
    configPath?: string
  ): Promise<WorkflowResult> {
    const formData = new FormData();
    formData.append('file', file);

    console.log('[GraphAideAPI] Posting to /load-vector');
    const response = await this.client.post('/load-vector', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    console.log('[GraphAideAPI] Load-vector response:', response.data);
    return response.data;
  }

  async visualizeVectorStore(configPath?: string): Promise<WorkflowResult> {
    const response = await this.client.post('/visualize-vector-db', {
      config_path: configPath,
    });
    return response.data;
  }

  async query(
    question: string,
    useVectorStore: boolean = true,
    configPath?: string
  ): Promise<WorkflowResult> {
    const response = await this.client.post('/query', {
      question,
      use_vector_store: useVectorStore,
      config_path: configPath,
      observability_config: this.getLangfusePayload(),
    });
    return response.data;
  }

  async health(): Promise<any> {
    const response = await this.client.get('/health');
    return response.data;
  }

  async testLLMConnection(): Promise<any> {
    const response = await this.client.post('/test-llm');
    return response.data;
  }

  async testNeo4jConnection(): Promise<any> {
    const response = await this.client.post('/test-neo4j');
    return response.data;
  }

  async getFullConfig(): Promise<any> {
    try {
      console.log('[GraphAideAPI] Calling /get-config endpoint...');
      const response = await this.client.get('/get-config');
      console.log('[GraphAideAPI] ✅ Response status:', response.status);
      console.log('[GraphAideAPI] ✅ Response data:', response.data);
      return response.data;
    } catch (error) {
      console.error('[GraphAideAPI] ❌ Failed to load config from backend:');
      console.error('   Error:', error);
      if (error instanceof Error) {
        console.error('   Message:', error.message);
      }
      return null;
    }
  }

  async getObservabilityConfig(): Promise<LangfuseConfig> {
    try {
      const response = await this.client.get('/get-observability-config');
      return response.data;
    } catch (error) {
      console.warn('Failed to load observability config from backend:', error);
      return { langfuse_enabled: false };
    }
  }
}

export const graphaideAPI = new GraphAideAPIClient();

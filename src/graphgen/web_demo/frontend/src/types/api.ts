export interface Node {
  node_name: string;
  node_type: string;
  english_name: string;
  wikidata_id?: string;
  node_id: string;
  raw_source?: string | null;
  character_span?: { start: number; end: number } | null;
  token_span?: { start: number; end: number } | null;
  chunk_id?: string | null;
  raw_source_line?: string | null;
}

export interface Edge {
  source_id: string;
  target_id: string;
  edge_type: string;
  argument_role?: string | null;
  start_datetime?: string | null;
  end_datetime?: string | null;
  raw_source?: string | null;
  character_span?: { start: number; end: number } | null;
  token_span?: { start: number; end: number } | null;
  chunk_id?: string | null;
  raw_source_line?: string | null;
}

export interface WorkflowResult {
  success: boolean;
  workflow_name?: string;
  execution_time_seconds?: number;
  data?: Record<string, any>;
  nodes?: Node[];
  edges?: Edge[];
  answer?: string;
  stats?: Record<string, any>;
  messages?: string[];
  errors?: string[];
  nodes_extracted?: number;
  edges_extracted?: number;
  segments_processed?: number;
  output_json_path?: string;
}

export interface ConfigState {
  modelProvider: string;
  modelName: string;
  apiKey: string;
  temperature: number;
  maxTokens: number;
  proxyUrl: string;
  neoUri: string;
  neoUsername: string;
  neoPassword: string;
  vectorStoreProvider: string;
  vectorStorePath: string;
  vectorStoreName: string;
  langfuseEnabled: boolean;
  langfusePublicKey: string;
  langfuseSecretKey: string;
  langfuseBaseUrl: string;
  langfuseDebug: boolean;
  langfuseServiceName: string;
  langfuseSessionName: string;
  langfuseEnvironment: string;
}

export interface WorkflowState {
  status: 'idle' | 'running' | 'complete' | 'error';
  progress: number;
  error: string | null;
  executionTime?: number;
}

export interface ResultsState {
  nodes: Node[];
  edges: Edge[];
  stats: Record<string, any>;
  rawJson?: string;
  executionTime?: number;
}

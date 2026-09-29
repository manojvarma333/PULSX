// Mirrors the shapes returned by backend/app/api/*.py -- kept intentionally small.
export interface ExperimentSummary {
  id: string;
  name: string;
  created_at: string | null;
  dataset: string;
  protocol: string;
  worker_language: string;
  worker_count: number;
  strategy: string;
  status: string;
}

export interface WorkerInfo {
  worker_id: string;
  language: string;
  status: string;
  cpu_usage: number;
  memory_usage: number;
}

export interface MetricInfo {
  worker_id: string;
  event_count: number;
  throughput: number;
  avg_latency: number;
  p95_latency: number;
  p99_latency: number;
}

export interface FailureInfo {
  worker_id: string;
  failure_type: string;
  detected_at: string | null;
  recovery_time: number | null;
}

export interface ExperimentDetail extends ExperimentSummary {
  workers: WorkerInfo[];
  metrics: MetricInfo[];
  failures: FailureInfo[];
}

export interface RunStatus {
  experiment_id: string;
  name: string;
  status: 'running' | 'completed' | 'failed';
  error: string | null;
}

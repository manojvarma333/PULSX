import type { ExperimentDetail, ExperimentSummary, RunStatus } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${init?.method ?? 'GET'} ${path} failed (${response.status}): ${body}`);
  }
  return response.json() as Promise<T>;
}

export interface RunExperimentRequest {
  name: string;
  dataset_file: string;
  protocol: string;
  worker_language: string;
  worker_count: number;
  strategy: string;
  replay_mode: string;
}

export const api = {
  health: () => request<{ status: string }>('/health'),
  listExperiments: () => request<ExperimentSummary[]>('/experiments'),
  getExperiment: (id: string) => request<ExperimentDetail>(`/experiments/${id}`),
  getStatus: (id: string) => request<RunStatus>(`/experiments/${id}/status`),
  runExperiment: (body: RunExperimentRequest) =>
    request<{ experiment_id: string; status: string }>('/experiments/run', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
};

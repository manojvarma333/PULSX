import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../services/api';
import type { ExperimentDetail as ExperimentDetailType, RunStatus } from '../types';

export default function ExperimentDetail() {
  const { id } = useParams<{ id: string }>();
  const [status, setStatus] = useState<RunStatus | null>(null);
  const [detail, setDetail] = useState<ExperimentDetailType | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    let timer: number | undefined;

    const poll = async () => {
      try {
        const s = await api.getStatus(id);
        if (cancelled) return;
        setStatus(s);
        if (s.status === 'running') {
          timer = window.setTimeout(poll, 1000);
        } else {
          const d = await api.getExperiment(id);
          if (!cancelled) setDetail(d);
        }
      } catch (err) {
        if (!cancelled) setError(String(err));
      }
    };
    poll();

    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [id]);

  if (error) return <p className="error">{error}</p>;
  if (!status) return <p>Loading...</p>;

  return (
    <div>
      <p>
        <Link to="/">&larr; Back to experiments</Link>
      </p>
      <h1>{status.name}</h1>
      <p>
        Status: <span className={`status status-${status.status}`}>{status.status}</span>
      </p>
      {status.status === 'running' && <p>Live experiment in progress -- polling every second...</p>}
      {status.status === 'failed' && <p className="error">{status.error}</p>}

      {detail && (
        <>
          <section className="card">
            <h2>Configuration</h2>
            <ul className="kv-list">
              <li>Dataset: {detail.dataset}</li>
              <li>Protocol: {detail.protocol}</li>
              <li>Worker language: {detail.worker_language}</li>
              <li>Worker count: {detail.worker_count}</li>
              <li>Strategy: {detail.strategy}</li>
            </ul>
          </section>

          <section className="card">
            <h2>Workers</h2>
            <table>
              <thead>
                <tr>
                  <th>Worker</th>
                  <th>Language</th>
                  <th>Status</th>
                  <th>CPU %</th>
                  <th>Memory %</th>
                </tr>
              </thead>
              <tbody>
                {detail.workers.map((w) => (
                  <tr key={w.worker_id}>
                    <td>{w.worker_id}</td>
                    <td>{w.language}</td>
                    <td>{w.status}</td>
                    <td>{w.cpu_usage.toFixed(1)}</td>
                    <td>{w.memory_usage.toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="card">
            <h2>Throughput &amp; Latency (ms)</h2>
            {detail.metrics.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={detail.metrics}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="worker_id" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="avg_latency" fill="#8884d8" name="avg latency (ms)" />
                  <Bar dataKey="p95_latency" fill="#82ca9d" name="p95 latency (ms)" />
                  <Bar dataKey="p99_latency" fill="#ff7f50" name="p99 latency (ms)" />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p>No metrics recorded.</p>
            )}
            <table>
              <thead>
                <tr>
                  <th>Worker</th>
                  <th>Events</th>
                  <th>Throughput (events/sec)</th>
                  <th>Avg latency (ms)</th>
                  <th>P95 (ms)</th>
                  <th>P99 (ms)</th>
                </tr>
              </thead>
              <tbody>
                {detail.metrics.map((m) => (
                  <tr key={m.worker_id}>
                    <td>{m.worker_id}</td>
                    <td>{m.event_count}</td>
                    <td>{m.throughput.toFixed(2)}</td>
                    <td>{m.avg_latency.toFixed(4)}</td>
                    <td>{m.p95_latency.toFixed(4)}</td>
                    <td>{m.p99_latency.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="card">
            <h2>Failures</h2>
            {detail.failures.length === 0 ? (
              <p>No worker failures during this experiment.</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Worker</th>
                    <th>Type</th>
                    <th>Detected at</th>
                    <th>Recovery time (s)</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.failures.map((f, i) => (
                    <tr key={i}>
                      <td>{f.worker_id}</td>
                      <td>{f.failure_type}</td>
                      <td>{f.detected_at ? new Date(f.detected_at).toLocaleString() : '-'}</td>
                      <td>{f.recovery_time?.toFixed(3) ?? '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}
    </div>
  );
}

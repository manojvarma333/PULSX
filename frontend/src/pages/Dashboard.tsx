import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import type { ExperimentSummary } from '../types';

const STRATEGIES = ['passthrough', 'moving_average', 'statistics', 'cpu_stress', 'failure'];

export default function Dashboard() {
  const [experiments, setExperiments] = useState<ExperimentSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  const [form, setForm] = useState({
    name: '',
    dataset_file: 'data/sample/sample.csv',
    protocol: 'json',
    worker_language: 'python',
    worker_count: 1,
    strategy: 'passthrough',
    replay_mode: 'maximum',
  });

  const refresh = () => {
    api.listExperiments().then(setExperiments).catch((err) => setError(String(err)));
  };

  useEffect(refresh, []);

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const { experiment_id } = await api.runExperiment(form);
      navigate(`/experiments/${experiment_id}`);
    } catch (err) {
      setError(String(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <h1>PulseX Dashboard</h1>
      <p className="subtitle">
        Local market-data replay &amp; distributed simulation research platform. All numbers below
        come from real experiment runs -- nothing here is hardcoded.
      </p>

      <section className="card">
        <h2>Run a new experiment</h2>
        <form onSubmit={onSubmit} className="run-form">
          <label>
            Name
            <input
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="e.g. binary-4workers"
            />
          </label>
          <label>
            Dataset file (path on the backend host)
            <input
              required
              value={form.dataset_file}
              onChange={(e) => setForm({ ...form, dataset_file: e.target.value })}
            />
          </label>
          <label>
            Protocol
            <select value={form.protocol} onChange={(e) => setForm({ ...form, protocol: e.target.value })}>
              <option value="json">JSON</option>
              <option value="binary">Binary</option>
            </select>
          </label>
          <label>
            Worker language
            <select
              value={form.worker_language}
              onChange={(e) => setForm({ ...form, worker_language: e.target.value })}
            >
              <option value="python">Python</option>
              <option value="cpp">C++</option>
            </select>
          </label>
          <label>
            Worker count
            <input
              type="number"
              min={1}
              value={form.worker_count}
              onChange={(e) => setForm({ ...form, worker_count: Number(e.target.value) })}
            />
          </label>
          <label>
            Strategy
            <select value={form.strategy} onChange={(e) => setForm({ ...form, strategy: e.target.value })}>
              {STRATEGIES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <label>
            Replay mode
            <select value={form.replay_mode} onChange={(e) => setForm({ ...form, replay_mode: e.target.value })}>
              <option value="maximum">Maximum</option>
              <option value="original">Original timing</option>
              <option value="accelerated">Accelerated</option>
            </select>
          </label>
          <button type="submit" disabled={submitting}>
            {submitting ? 'Starting...' : 'Run experiment'}
          </button>
        </form>
        {error && <p className="error">{error}</p>}
      </section>

      <section className="card">
        <div className="section-header">
          <h2>Experiments</h2>
          <button onClick={refresh}>Refresh</button>
        </div>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Status</th>
              <th>Protocol</th>
              <th>Language</th>
              <th>Workers</th>
              <th>Strategy</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {experiments.map((e) => (
              <tr key={e.id}>
                <td>
                  <Link to={`/experiments/${e.id}`}>{e.name}</Link>
                </td>
                <td>
                  <span className={`status status-${e.status}`}>{e.status}</span>
                </td>
                <td>{e.protocol}</td>
                <td>{e.worker_language}</td>
                <td>{e.worker_count}</td>
                <td>{e.strategy}</td>
                <td>{e.created_at ? new Date(e.created_at).toLocaleString() : '-'}</td>
              </tr>
            ))}
            {experiments.length === 0 && (
              <tr>
                <td colSpan={7}>No experiments yet -- run one above.</td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}

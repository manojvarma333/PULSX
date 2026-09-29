import { Route, Routes } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import ExperimentDetail from './pages/ExperimentDetail';
import './App.css';

export default function App() {
  return (
    <div className="app">
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/experiments/:id" element={<ExperimentDetail />} />
      </Routes>
    </div>
  );
}

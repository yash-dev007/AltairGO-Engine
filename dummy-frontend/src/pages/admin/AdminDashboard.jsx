import { useState, useEffect, useRef, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Users, Map, Database, Zap, Brain, RefreshCw, Activity, TrendingUp, Cpu } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import toast from 'react-hot-toast';
import { getDashboardSummary, triggerJob, triggerAgent, getAdminToken } from '../../services/api';
import { StatCard, Card, Button, Badge, Spinner } from '../../components/ui/index';

const JOBS = [
  { name: 'run_score_update', label: 'Score Update' },
  { name: 'run_cache_warm', label: 'Cache Warm' },
  { name: 'run_osm_ingestion', label: 'OSM Ingestion' },
  { name: 'run_enrichment', label: 'Enrichment' },
  { name: 'run_price_sync', label: 'Price Sync' },
  { name: 'run_quality_scoring', label: 'Quality Scoring' },
];

const BASE = import.meta.env.VITE_API_URL || '';

export default function AdminDashboard() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [triggeringJob, setTriggeringJob] = useState(null);
  const [liveEvents, setLiveEvents] = useState([]);
  const [sseConnected, setSseConnected] = useState(false);
  const liveRef = useRef(null);

  const loadSummary = useCallback(() => {
    getDashboardSummary()
      .then(setSummary)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { loadSummary(); }, [loadSummary]);

  // Auto-refresh every 30s
  useEffect(() => {
    const iv = setInterval(loadSummary, 30000);
    return () => clearInterval(iv);
  }, [loadSummary]);

  // SSE live-metrics
  useEffect(() => {
    const token = getAdminToken();
    const url = `${BASE}/api/ops/live-metrics${token ? `?token=${encodeURIComponent(token)}` : ''}`;
    const es = new EventSource(url);
    es.onopen = () => setSseConnected(true);
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        setLiveEvents((prev) => [data, ...prev].slice(0, 20));
      } catch { /* ignore */ }
    };
    es.onerror = () => setSseConnected(false);
    return () => es.close();
  }, []);

  const handleTriggerJob = async (name) => {
    setTriggeringJob(name);
    try {
      const res = await triggerJob(name);
      toast.success(`Job ${name} triggered — task: ${res.task_id || 'queued'}`);
    } catch (err) { toast.error(err.message || 'Trigger failed'); }
    finally { setTriggeringJob(null); }
  };

  if (loading) return <div className="flex justify-center py-16"><Spinner size="lg" className="text-indigo-600" /></div>;

  const app = summary?.app || {};
  const gemini = summary?.gemini || {};
  const cache = summary?.cache || {};
  const pipeline = summary?.pipeline || {};
  const agents = summary?.agents || {};

  const cacheData = [
    { name: 'Hits', value: cache.hits_today || 0 },
    { name: 'Misses', value: cache.misses_today || 0 },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Mission Control</h1>
          <p className="text-sm text-slate-500 mt-0.5">Real-time system overview</p>
        </div>
        <Button variant="secondary" size="sm" onClick={loadSummary}>
          <RefreshCw className="w-4 h-4" /> Refresh
        </Button>
      </div>

      {/* App Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Users} label="Total Users" value={app.users_total?.toLocaleString() || '—'} color="indigo" />
        <StatCard icon={Map} label="Total Trips" value={app.trips_total?.toLocaleString() || '—'} color="violet" />
        <StatCard icon={Database} label="Destinations" value={app.destinations_total?.toLocaleString() || '—'} color="green" />
        <StatCard icon={Zap} label="Trips Today" value={app.trips_generated_today?.toLocaleString() || '0'} color="amber" />
      </div>

      {/* Gemini + Cache + Pipeline */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Gemini */}
        <Card className="p-5">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-8 h-8 rounded-xl bg-violet-50 flex items-center justify-center">
              <Brain className="w-4 h-4 text-violet-600" />
            </div>
            <h3 className="font-semibold text-slate-700 text-sm">Gemini AI</h3>
          </div>
          <div className="space-y-2.5 text-sm">
            <div className="flex justify-between"><span className="text-slate-500">Calls today</span><span className="font-bold text-slate-800">{gemini.calls_today || 0}</span></div>
            <div className="flex justify-between"><span className="text-slate-500">Tokens today</span><span className="font-bold text-slate-800">{(gemini.tokens_today || 0).toLocaleString()}</span></div>
            <div className="flex justify-between"><span className="text-slate-500">Error rate</span>
              <span className={`font-bold ${(gemini.error_rate_pct || 0) > 10 ? 'text-red-600' : 'text-green-600'}`}>{gemini.error_rate_pct || 0}%</span>
            </div>
          </div>
        </Card>

        {/* Cache */}
        <Card className="p-5">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-8 h-8 rounded-xl bg-sky-50 flex items-center justify-center">
              <Database className="w-4 h-4 text-sky-600" />
            </div>
            <h3 className="font-semibold text-slate-700 text-sm">Cache</h3>
          </div>
          <div className="h-28">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={cacheData} margin={{ top: 0, right: 0, bottom: 0, left: -20 }}>
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="value" radius={[4,4,0,0]}>
                  <Cell fill="#6366f1" />
                  <Cell fill="#e0e7ff" />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="text-center text-sm font-semibold text-indigo-600 mt-1">
            Hit rate: {cache.hit_rate_pct || 0}%
          </p>
        </Card>

        {/* Pipeline */}
        <Card className="p-5">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-8 h-8 rounded-xl bg-green-50 flex items-center justify-center">
              <TrendingUp className="w-4 h-4 text-green-600" />
            </div>
            <h3 className="font-semibold text-slate-700 text-sm">Pipeline</h3>
          </div>
          <div className="space-y-2.5 text-sm">
            <div className="flex justify-between"><span className="text-slate-500">Avg generation</span><span className="font-bold text-slate-800">{pipeline.avg_generation_ms ? `${pipeline.avg_generation_ms}ms` : '—'}</span></div>
            <div className="flex justify-between"><span className="text-slate-500">P95 generation</span><span className="font-bold text-slate-800">{pipeline.p95_generation_ms ? `${pipeline.p95_generation_ms}ms` : '—'}</span></div>
            <div className="flex justify-between"><span className="text-slate-500">Pending requests</span><span className="font-bold text-slate-800">{app.pending_requests || 0}</span></div>
          </div>
        </Card>
      </div>

      {/* Job triggers + Agents */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Job triggers */}
        <Card className="p-5">
          <h3 className="font-semibold text-slate-700 mb-4 text-sm flex items-center gap-2">
            <Zap className="w-4 h-4 text-amber-500" /> Manual Job Triggers
          </h3>
          <div className="grid grid-cols-2 gap-2">
            {JOBS.map((job) => (
              <button
                key={job.name}
                onClick={() => handleTriggerJob(job.name)}
                disabled={triggeringJob === job.name}
                className="flex items-center gap-2 px-3 py-2.5 rounded-xl border border-slate-200 text-sm font-medium text-slate-700 hover:bg-indigo-50 hover:border-indigo-200 transition-all disabled:opacity-60"
              >
                {triggeringJob === job.name ? <Spinner size="sm" /> : <Zap className="w-3.5 h-3.5 text-amber-500" />}
                {job.label}
              </button>
            ))}
          </div>
        </Card>

        {/* Agent status */}
        <Card className="p-5">
          <h3 className="font-semibold text-slate-700 mb-4 text-sm flex items-center gap-2">
            <Cpu className="w-4 h-4 text-violet-500" /> AI Agents
          </h3>
          {Object.keys(agents).length === 0 ? (
            <p className="text-sm text-slate-400">No agent data available.</p>
          ) : (
            <div className="space-y-2">
              {Object.entries(agents).slice(0, 6).map(([key, agent]) => (
                <div key={key} className="flex items-center justify-between text-sm py-1.5 border-b border-slate-100 last:border-0">
                  <span className="text-slate-700 font-medium capitalize">{key.replace(/_/g, ' ')}</span>
                  <div className="flex items-center gap-2">
                    <Badge status={agent.status === 'ok' || agent.status === 'success' ? 'completed' : agent.status === 'error' ? 'failed' : 'pending'}>
                      {agent.status || 'idle'}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Live SSE feed */}
      <Card className="p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-slate-700 text-sm flex items-center gap-2">
            <Activity className="w-4 h-4 text-green-500" /> Live Event Stream
          </h3>
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${sseConnected ? 'bg-green-400 animate-pulse' : 'bg-slate-300'}`} />
            <span className="text-xs text-slate-500">{sseConnected ? 'Connected' : 'Disconnected'}</span>
          </div>
        </div>
        <div ref={liveRef} className="space-y-1.5 max-h-56 overflow-y-auto font-mono text-xs">
          {liveEvents.length === 0 ? (
            <p className="text-slate-400 text-center py-4">Waiting for events...</p>
          ) : (
            liveEvents.map((event, i) => (
              <motion.div key={i} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}
                className="flex items-start gap-2 px-3 py-2 bg-slate-50 rounded-lg">
                <span className="text-slate-400 flex-shrink-0">{event.timestamp || new Date().toLocaleTimeString()}</span>
                <span className="text-slate-700">{event.type || event.event || 'event'}</span>
                {event.data && <span className="text-slate-500 truncate">{typeof event.data === 'string' ? event.data : JSON.stringify(event.data)}</span>}
              </motion.div>
            ))
          )}
        </div>
      </Card>
    </div>
  );
}

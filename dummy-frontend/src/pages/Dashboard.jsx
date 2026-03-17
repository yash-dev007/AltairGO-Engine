import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import {
    Activity,
    TrendingUp,
    ShieldCheck,
    Zap,
    RefreshCw,
    Database,
    Users,
    MapPin,
    AlertCircle,
    Play,
    CheckCircle2,
    Loader2,
    XCircle,
    Gauge,
    Signal,
    Star,
    Radio,
    Layers,
    FileCheck,
    AlertTriangle,
    ChevronRight,
} from 'lucide-react';
import { api } from '../services/api';

const AVAILABLE_JOBS = [
    { key: 'osm_ingestion', label: 'OSM Ingestion', desc: 'Import OpenStreetMap POI data', icon: Database },
    { key: 'enrichment', label: 'Enrichment', desc: 'Enrich destination metadata', icon: Layers },
    { key: 'scoring', label: 'Score Update', desc: 'Recalculate behavioral scores', icon: TrendingUp },
    { key: 'price_sync', label: 'Price Sync', desc: 'Sync hotel/flight prices', icon: RefreshCw },
    { key: 'cache_warm', label: 'Cache Warm', desc: 'Pre-generate popular itineraries', icon: Zap },
    { key: 'quality_scoring', label: 'Quality Scoring', desc: 'Run QA on saved trips', icon: FileCheck },
    { key: 'affiliate_health', label: 'Affiliate Health', desc: 'Check partner APIs', icon: Activity },
    { key: 'destination_validation', label: 'Dest. Validation', desc: 'Validate pending requests', icon: ShieldCheck },
];

/** Static Tailwind class map — dynamic interpolation breaks JIT purging */
const COLOR_MAP = {
    blue:   { bg: 'bg-blue-50',   text: 'text-blue-500',   iconBg: 'text-blue-500' },
    purple: { bg: 'bg-purple-50', text: 'text-purple-500', iconBg: 'text-purple-500' },
    green:  { bg: 'bg-green-50',  text: 'text-green-500',  iconBg: 'text-green-500' },
    amber:  { bg: 'bg-amber-50',  text: 'text-amber-500',  iconBg: 'text-amber-500' },
};

/** Formats large numbers compactly: 1200 → "1.2K" */
const fmtNum = (n) => {
    if (n == null) return '0';
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
    return n.toLocaleString();
};

/** Relative time: ISO → "2m ago" */
const fmtRelTime = (iso) => {
    if (!iso || iso === 'Never') return 'Never';
    try {
        const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
        if (diff < 60) return `${diff}s ago`;
        if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
        return `${Math.floor(diff / 86400)}d ago`;
    } catch { return iso; }
};

const Dashboard = () => {
    const [stats, setStats] = useState(null);
    const [ops, setOps] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [jobStatus, setJobStatus] = useState({});
    const [liveEvents, setLiveEvents] = useState([]);
    const [sseConnected, setSseConnected] = useState(false);
    const [lastRefresh, setLastRefresh] = useState(null);
    const eventSourceRef = useRef(null);
    const pollIntervalsRef = useRef({});

    // ── Fetch all dashboard data ──────────────────────────────
    const fetchData = useCallback(async () => {
        try {
            const [adminStats, opsSummary] = await Promise.all([
                api.getAdminStats(),
                api.getOpsSummary(),
            ]);
            setStats(adminStats);
            setOps(opsSummary);
            setError(null);
            setLastRefresh(new Date());
        } catch (err) {
            console.error('Failed to fetch dashboard data:', err);
            setError('Failed to connect to backend engine.');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 30000);
        return () => clearInterval(interval);
    }, [fetchData]);

    // ── SSE Live Metrics ──────────────────────────────────────
    useEffect(() => {
        const token = api.getToken();
        if (!token) {
            setSseConnected(false);
            return;
        }

        const url = `${api.getLiveMetricsURL()}?token=${encodeURIComponent(token)}`;
        let errorCount = 0;

        try {
            const es = new EventSource(url);
            eventSourceRef.current = es;

            es.onopen = () => {
                setSseConnected(true);
                errorCount = 0;
            };
            es.onmessage = (event) => {
                errorCount = 0;
                try {
                    const data = JSON.parse(event.data);
                    if (!data.heartbeat) {
                        setLiveEvents((prev) => [
                            { ...data, _ts: Date.now(), _id: Math.random().toString(36).slice(2) },
                            ...prev,
                        ].slice(0, 50));
                    }
                } catch { /* skip malformed */ }
            };
            es.onerror = () => {
                errorCount++;
                setSseConnected(false);
                // Stop reconnecting after 3 consecutive failures (likely auth issue)
                if (errorCount >= 3) {
                    es.close();
                }
            };
        } catch {
            setSseConnected(false);
        }

        return () => {
            if (eventSourceRef.current) {
                eventSourceRef.current.close();
            }
        };
    }, []);

    // ── Job Trigger with real polling ─────────────────────────
    const triggerJob = async (jobName) => {
        setJobStatus((prev) => ({ ...prev, [jobName]: { state: 'running', taskId: null } }));
        try {
            const resp = await api.triggerJob(jobName);
            const taskId = resp.task_id;
            setJobStatus((prev) => ({ ...prev, [jobName]: { state: 'polling', taskId } }));

            // Poll for real completion
            const pollId = setInterval(async () => {
                try {
                    const status = await api.getJobStatus(taskId);
                    if (status.status === 'SUCCESS') {
                        setJobStatus((prev) => ({ ...prev, [jobName]: { state: 'success', taskId } }));
                        clearInterval(pollId);
                        delete pollIntervalsRef.current[jobName];
                        setTimeout(() => setJobStatus((prev) => ({ ...prev, [jobName]: null })), 6000);
                        fetchData(); // Refresh dashboard data
                    } else if (status.status === 'FAILURE') {
                        setJobStatus((prev) => ({ ...prev, [jobName]: { state: 'error', taskId } }));
                        clearInterval(pollId);
                        delete pollIntervalsRef.current[jobName];
                        setTimeout(() => setJobStatus((prev) => ({ ...prev, [jobName]: null })), 6000);
                    }
                } catch {
                    // Polling error — keep trying
                }
            }, 3000);
            pollIntervalsRef.current[jobName] = pollId;
        } catch {
            setJobStatus((prev) => ({ ...prev, [jobName]: { state: 'error', taskId: null } }));
            setTimeout(() => setJobStatus((prev) => ({ ...prev, [jobName]: null })), 5000);
        }
    };

    // Cleanup poll intervals
    useEffect(() => {
        return () => {
            Object.values(pollIntervalsRef.current).forEach(clearInterval);
        };
    }, []);

    // ── Derived data ──────────────────────────────────────────
    const agentHealth = Object.entries(ops?.agents || {}).map(([name, data]) => ({
        name: name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
        key: name,
        status: data.status === 'never_run' ? 'IDLE' : (data.status || 'IDLE').toUpperCase(),
        ok: ['ok', 'success', 'complete', 'optimal'].includes(data.status),
        lastRun: data.last_run,
    }));

    const totalAgentsOk = agentHealth.filter((a) => a.ok).length;
    const totalAgents = agentHealth.length;
    const pendingRequests = ops?.app?.pending_destination_requests || 0;
    const tripsToday = ops?.app?.trips_generated_today || 0;
    const signalsToday = ops?.app?.signals_recorded_today || 0;

    // ── Loading state ─────────────────────────────────────────
    if (loading && !stats) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
                <div className="relative">
                    <div className="size-16 rounded-full border-4 border-slate-100 border-t-green-500 animate-spin" />
                    <div className="absolute inset-0 flex items-center justify-center">
                        <Gauge size={20} className="text-green-500" />
                    </div>
                </div>
                <p className="text-slate-500 font-bold tracking-widest uppercase text-xs">Synchronizing with Intelligence Engine...</p>
            </div>
        );
    }

    if (error && !stats) {
        return (
            <div className="max-w-xl mx-auto mt-20">
                <div className="bg-red-50 border border-red-200 p-8 rounded-3xl flex flex-col items-center gap-4 text-center">
                    <div className="size-16 bg-red-100 rounded-2xl flex items-center justify-center">
                        <AlertCircle size={32} className="text-red-500" />
                    </div>
                    <h3 className="font-black text-red-800 text-lg">Backend Connection Failure</h3>
                    <p className="text-sm text-red-600">{error}</p>
                    <button onClick={fetchData} className="mt-2 px-6 py-2 bg-red-600 text-white rounded-xl font-bold text-sm hover:bg-red-700 transition-all active:scale-95">
                        Retry Connection
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-8 max-w-[1400px] mx-auto w-full animate-fade-in">

            {/* ── Top Bar: Status + Refresh ────────────────────── */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-100 rounded-2xl shadow-sm">
                        <div className={`size-2 rounded-full ${sseConnected ? 'bg-green-500 animate-pulse' : 'bg-slate-300'}`} />
                        <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">
                            {sseConnected ? 'Live' : 'Polling'}
                        </span>
                    </div>
                    {lastRefresh && (
                        <span className="text-[10px] text-slate-400 font-bold">
                            Last sync: {lastRefresh.toLocaleTimeString()}
                        </span>
                    )}
                </div>
                <button
                    onClick={fetchData}
                    className="flex items-center gap-2 px-5 py-2.5 bg-white border border-slate-100 rounded-2xl shadow-sm hover:bg-slate-50 transition-all active:scale-95 text-xs font-bold text-slate-600"
                >
                    <RefreshCw size={14} /> Refresh
                </button>
            </div>

            {/* ── Row 1: Primary KPIs ──────────────────────────── */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {[
                    { label: 'Total Users', value: stats?.total_users, icon: Users, color: 'blue', sub: `${tripsToday} trips today` },
                    { label: 'Trips Generated', value: stats?.total_trips, icon: MapPin, color: 'purple', sub: `${signalsToday} signals today` },
                    { label: 'Destinations', value: stats?.total_destinations, icon: Database, color: 'green', sub: pendingRequests > 0 ? `${pendingRequests} pending` : 'All reviewed' },
                    { label: 'Attractions', value: stats?.total_attractions, icon: Star, color: 'amber', sub: `${totalAgentsOk}/${totalAgents} agents online` },
                ].map((m, i) => (
                    <div
                        key={i}
                        className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm hover:shadow-lg hover:-translate-y-0.5 transition-all group relative overflow-hidden"
                    >
                        <div className={`absolute -right-3 -top-3 size-20 opacity-[0.04] group-hover:opacity-[0.08] transition-opacity ${COLOR_MAP[m.color].text}`}>
                            <m.icon size={80} />
                        </div>
                        <div className="relative z-10">
                            <div className={`size-10 ${COLOR_MAP[m.color].bg} ${COLOR_MAP[m.color].text} rounded-xl flex items-center justify-center mb-4 shadow-inner`}>
                                <m.icon size={20} />
                            </div>
                            <p className="text-3xl font-black text-slate-900 tracking-tight">{fmtNum(m.value)}</p>
                            <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mt-1">{m.label}</p>
                            <p className="text-[10px] font-bold text-slate-300 mt-2">{m.sub}</p>
                        </div>
                    </div>
                ))}
            </div>

            {/* ── Row 2: Today's Activity + System Health ────── */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Today's Metrics */}
                <div className="lg:col-span-2 bg-white rounded-2xl shadow-sm border border-slate-100 p-6">
                    <h3 className="font-bold text-slate-900 flex items-center gap-2 mb-6 text-sm">
                        <TrendingUp className="text-green-500" size={18} /> Gemini & Pipeline Performance
                    </h3>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div className="p-4 bg-slate-50 rounded-xl border border-slate-100 hover:bg-green-50 hover:border-green-100 transition-all">
                            <p className="text-2xl font-black text-slate-900">{ops?.gemini?.calls_today || 0}</p>
                            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mt-1">API Calls Today</p>
                        </div>
                        <div className="p-4 bg-slate-50 rounded-xl border border-slate-100 hover:bg-blue-50 hover:border-blue-100 transition-all">
                            <p className="text-2xl font-black text-slate-900">{fmtNum(ops?.gemini?.tokens_today)}</p>
                            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mt-1">Tokens Used</p>
                        </div>
                        <div className={`p-4 rounded-xl border transition-all ${
                            (ops?.gemini?.error_rate_pct || 0) > 5
                                ? 'bg-red-50 border-red-100'
                                : 'bg-slate-50 border-slate-100 hover:bg-green-50 hover:border-green-100'
                        }`}>
                            <div className="flex items-center gap-2">
                                <p className={`text-2xl font-black ${(ops?.gemini?.error_rate_pct || 0) > 5 ? 'text-red-600' : 'text-slate-900'}`}>
                                    {ops?.gemini?.error_rate_pct || 0}%
                                </p>
                                {(ops?.gemini?.error_rate_pct || 0) > 5 && <AlertTriangle size={16} className="text-red-500" />}
                            </div>
                            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mt-1">Error Rate</p>
                        </div>
                        <div className="p-4 bg-green-50 rounded-xl border border-green-100">
                            <p className="text-2xl font-black text-green-600">ACTIVE</p>
                            <p className="text-[10px] font-bold text-green-500 uppercase tracking-wider mt-1">Orchestrator</p>
                        </div>
                    </div>

                    {/* Cache + Latency row */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
                        <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <p className="text-xl font-black text-slate-900">{ops?.cache?.hit_rate_pct || 0}%</p>
                            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mt-1">Cache Hit Rate</p>
                        </div>
                        <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <p className="text-xl font-black text-slate-900">{ops?.pipeline?.avg_generation_ms || 0}<span className="text-sm text-slate-400 ml-0.5">ms</span></p>
                            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mt-1">Avg Latency</p>
                        </div>
                        <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <p className="text-xl font-black text-slate-900">{ops?.pipeline?.p95_generation_ms || 0}<span className="text-sm text-slate-400 ml-0.5">ms</span></p>
                            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mt-1">P95 Latency</p>
                        </div>
                        <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <p className="text-xl font-black text-slate-900">{ops?.quality?.scored_count || 0}</p>
                            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mt-1">QA Scored</p>
                        </div>
                    </div>
                </div>

                {/* Agent Health Panel */}
                <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-6 flex flex-col">
                    <div className="flex items-center justify-between mb-5">
                        <h3 className="font-bold text-slate-900 flex items-center gap-2 text-sm">
                            <ShieldCheck className="text-green-500" size={18} /> Agent Fleet
                        </h3>
                        <span className={`px-2.5 py-1 rounded-lg text-[10px] font-black ${
                            totalAgentsOk === totalAgents
                                ? 'bg-green-50 text-green-600'
                                : 'bg-amber-50 text-amber-600'
                        }`}>
                            {totalAgents > 0 ? `${totalAgentsOk}/${totalAgents}` : '—'}
                        </span>
                    </div>
                    <div className="space-y-2 flex-1">
                        {agentHealth.length > 0 ? agentHealth.map((agent) => (
                            <div key={agent.key} className="flex items-center justify-between py-2 px-3 rounded-xl hover:bg-slate-50 transition-all group">
                                <div className="flex items-center gap-2.5 min-w-0">
                                    <div className={`size-2 rounded-full shrink-0 ${agent.ok ? 'bg-green-500' : agent.status === 'IDLE' ? 'bg-slate-300' : 'bg-amber-500 animate-pulse'}`} />
                                    <span className="text-xs font-semibold text-slate-600 truncate">{agent.name}</span>
                                </div>
                                <div className="flex items-center gap-2 shrink-0">
                                    <span className="text-[9px] text-slate-400 font-bold hidden group-hover:block">{fmtRelTime(agent.lastRun)}</span>
                                    <span className={`px-2 py-0.5 text-[9px] font-black rounded-md ${
                                        agent.ok ? 'bg-green-100 text-green-700' :
                                        agent.status === 'IDLE' ? 'bg-slate-100 text-slate-500' :
                                        'bg-amber-100 text-amber-700'
                                    }`}>
                                        {agent.status}
                                    </span>
                                </div>
                            </div>
                        )) : (
                            <div className="flex-1 flex items-center justify-center">
                                <p className="text-xs text-slate-400 italic">No agent data available</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* ── Row 3: Pipeline Job Control + Live Feed ──── */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Job Control */}
                <div className="lg:col-span-2 bg-white rounded-2xl shadow-sm border border-slate-100 p-6">
                    <h3 className="font-bold text-slate-900 flex items-center gap-2 mb-5 text-sm">
                        <Play className="text-green-500" size={18} /> Pipeline Job Control
                    </h3>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        {AVAILABLE_JOBS.map((job) => {
                            const status = jobStatus[job.key];
                            const state = status?.state;
                            const isRunning = state === 'running' || state === 'polling';
                            const JobIcon = job.icon;
                            return (
                                <button
                                    key={job.key}
                                    onClick={() => triggerJob(job.key)}
                                    disabled={isRunning}
                                    className={`group p-4 rounded-xl transition-all text-left active:scale-[0.97] disabled:cursor-wait border ${
                                        state === 'success' ? 'bg-green-50 border-green-200' :
                                        state === 'error' ? 'bg-red-50 border-red-200' :
                                        isRunning ? 'bg-blue-50 border-blue-200' :
                                        'bg-slate-50 border-slate-100 hover:bg-green-50 hover:border-green-200'
                                    }`}
                                >
                                    <div className="flex items-center justify-between mb-2">
                                        <JobIcon size={16} className={`${
                                            state === 'success' ? 'text-green-500' :
                                            state === 'error' ? 'text-red-500' :
                                            isRunning ? 'text-blue-500' :
                                            'text-slate-400 group-hover:text-green-500'
                                        } transition-colors`} />
                                        {isRunning && <Loader2 size={14} className="animate-spin text-blue-500" />}
                                        {state === 'success' && <CheckCircle2 size={14} className="text-green-500" />}
                                        {state === 'error' && <XCircle size={14} className="text-red-500" />}
                                        {!state && <Play size={12} className="text-slate-300 group-hover:text-green-500 transition-colors" />}
                                    </div>
                                    <span className="text-xs font-bold text-slate-700 block leading-tight">{job.label}</span>
                                    <p className="text-[10px] text-slate-400 font-medium mt-1 leading-tight">{job.desc}</p>
                                    {state === 'polling' && (
                                        <div className="mt-2 w-full bg-blue-100 h-1 rounded-full overflow-hidden">
                                            <div className="bg-blue-500 h-full animate-progress" />
                                        </div>
                                    )}
                                </button>
                            );
                        })}
                    </div>
                </div>

                {/* Live Activity Feed */}
                <div className="bg-slate-950 rounded-2xl shadow-sm border border-slate-800 p-6 flex flex-col">
                    <div className="flex items-center justify-between mb-5">
                        <h3 className="font-bold text-white flex items-center gap-2 text-sm">
                            <Radio size={16} className={`${sseConnected ? 'text-green-400 animate-pulse' : 'text-slate-500'}`} />
                            Live Activity
                        </h3>
                        <span className={`text-[9px] font-black uppercase tracking-widest px-2 py-0.5 rounded ${sseConnected ? 'text-green-400 bg-green-400/10' : 'text-slate-500 bg-slate-800'}`}>
                            {sseConnected ? 'Connected' : 'Offline'}
                        </span>
                    </div>
                    <div className="flex-1 space-y-2 max-h-[320px] overflow-y-auto custom-scrollbar pr-1">
                        {liveEvents.length > 0 ? liveEvents.map((evt) => (
                            <div key={evt._id} className="p-3 bg-white/5 border border-white/5 rounded-xl text-xs animate-fade-in">
                                <div className="flex items-center justify-between mb-1">
                                    <span className="text-green-400 font-bold truncate mr-2">{evt.event_type || evt.type || 'event'}</span>
                                    <span className="text-slate-600 text-[9px] font-mono shrink-0">{new Date(evt._ts).toLocaleTimeString()}</span>
                                </div>
                                <p className="text-slate-400 text-[10px] truncate">
                                    {evt.message || evt.details || JSON.stringify(evt).slice(0, 80)}
                                </p>
                            </div>
                        )) : (
                            <div className="flex-1 flex flex-col items-center justify-center py-12 gap-3">
                                <Signal size={32} className="text-slate-700" />
                                <p className="text-[10px] text-slate-600 font-bold uppercase tracking-widest text-center">
                                    {sseConnected ? 'Waiting for events...' : 'Connect to see live events'}
                                </p>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* ── Row 4: Pending Requests Quick Panel ──────── */}
            {pendingRequests > 0 && (
                <div className="bg-amber-50 border border-amber-200 rounded-2xl p-5 flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <div className="size-10 bg-amber-100 rounded-xl flex items-center justify-center">
                            <AlertTriangle size={20} className="text-amber-600" />
                        </div>
                        <div>
                            <p className="font-bold text-amber-800 text-sm">
                                {pendingRequests} Destination Request{pendingRequests !== 1 ? 's' : ''} Pending Review
                            </p>
                            <p className="text-[10px] text-amber-600 font-medium">
                                Community submissions awaiting admin approval or rejection.
                            </p>
                        </div>
                    </div>
                    <Link
                        to="/data"
                        className="flex items-center gap-1 px-4 py-2 bg-amber-600 text-white rounded-xl text-xs font-bold hover:bg-amber-700 transition-all active:scale-95"
                    >
                        Review <ChevronRight size={14} />
                    </Link>
                </div>
            )}
        </div>
    );
};

export default Dashboard;

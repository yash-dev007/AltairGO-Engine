import React, { useState, useEffect, useCallback } from 'react';
import {
    Activity,
    TrendingUp,
    ShieldCheck,
    Zap,
    Clock,
    RefreshCw,
    Database,
    Users,
    MapPin,
    AlertCircle,
    Play,
    CheckCircle2,
    Loader2,
    XCircle
} from 'lucide-react';
import { api } from '../services/api';

const AVAILABLE_JOBS = [
    { key: 'osm_ingestion', label: 'OSM Ingestion', desc: 'Import OpenStreetMap POI data' },
    { key: 'enrichment', label: 'Enrichment', desc: 'Enrich destination metadata' },
    { key: 'scoring', label: 'Score Update', desc: 'Recalculate behavioral scores' },
    { key: 'price_sync', label: 'Price Sync', desc: 'Sync hotel/flight prices' },
    { key: 'cache_warm', label: 'Cache Warm', desc: 'Pre-generate popular itineraries' },
    { key: 'quality_scoring', label: 'Quality Scoring', desc: 'Run QA on saved trips' },
    { key: 'affiliate_health', label: 'Affiliate Health', desc: 'Check partner APIs' },
    { key: 'destination_validation', label: 'Destination Validation', desc: 'Validate pending requests' },
];

const Dashboard = () => {
    const [stats, setStats] = useState(null);
    const [ops, setOps] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [jobStatus, setJobStatus] = useState({});

    const fetchData = useCallback(async () => {
        try {
            const [adminStats, opsSummary] = await Promise.all([
                api.getAdminStats(),
                api.getOpsSummary(),
            ]);
            setStats(adminStats);
            setOps(opsSummary);
            setError(null);
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

    const triggerJob = async (jobName) => {
        setJobStatus((prev) => ({ ...prev, [jobName]: 'running' }));
        try {
            await api.triggerJob(jobName);
            setJobStatus((prev) => ({ ...prev, [jobName]: 'triggered' }));
            setTimeout(() => {
                setJobStatus((prev) => ({ ...prev, [jobName]: null }));
            }, 5000);
        } catch {
            setJobStatus((prev) => ({ ...prev, [jobName]: 'error' }));
            setTimeout(() => {
                setJobStatus((prev) => ({ ...prev, [jobName]: null }));
            }, 5000);
        }
    };

    const agentHealth = Object.entries(ops?.agents || {}).map(([name, data]) => ({
        name: name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
        status: data.status === 'never_run' ? 'IDLE' : (data.status || 'IDLE').toUpperCase(),
        ok: data.status === 'ok' || data.status === 'success' || data.status === 'complete' || data.status === 'optimal',
        lastRun: data.last_run,
    }));

    if (loading && !stats) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
                <RefreshCw className="text-[var(--accent)] animate-spin" size={40} />
                <p className="text-slate-500 font-medium tracking-wide">Synchronizing with Intelligence Engine...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="bg-red-50 border border-red-200 p-6 rounded-xl flex items-center gap-4 text-red-700">
                <AlertCircle size={24} />
                <div>
                    <h3 className="font-bold">Backend Connection Failure</h3>
                    <p className="text-sm">{error}</p>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-8 max-w-7xl mx-auto w-full">
            {/* Core Metrics */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <div className="lg:col-span-2 grid grid-cols-2 md:grid-cols-4 gap-4">
                    {[
                        { label: 'Total Users', value: stats?.total_users || 0, icon: Users },
                        { label: 'Trips Generated', value: stats?.total_trips || 0, icon: MapPin },
                        { label: 'Destinations', value: stats?.total_destinations || 0, icon: Database },
                        { label: 'Agent Tokens', value: ops?.gemini?.tokens_today || 0, icon: Zap },
                    ].map((m, i) => (
                        <div key={i} className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm transition-all hover:shadow-md">
                            <m.icon size={20} className="text-green-500 mb-4" />
                            <p className="text-2xl font-extrabold text-slate-900">{(m.value || 0).toLocaleString()}</p>
                            <p className="text-xs font-bold text-slate-400 uppercase tracking-tight">{m.label}</p>
                        </div>
                    ))}
                </div>

                {/* Network Vitals */}
                <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-6">
                    <h3 className="font-bold text-slate-900 flex items-center gap-2 mb-6">
                        <Activity className="text-green-500" size={20} /> Network Vitals
                    </h3>
                    <div className="grid grid-cols-2 gap-4">
                        <div className="flex flex-col items-center gap-2">
                            <div className="text-2xl font-bold text-green-500">{ops?.cache?.hit_rate_pct || 0}%</div>
                            <p className="text-[10px] font-bold text-slate-500 uppercase">Cache Hit Rate</p>
                        </div>
                        <div className="flex flex-col items-center gap-2">
                            <div className="text-2xl font-bold text-blue-500">{ops?.pipeline?.avg_generation_ms || 0}ms</div>
                            <p className="text-[10px] font-bold text-slate-500 uppercase">Gen Latency</p>
                        </div>
                    </div>
                </div>
            </div>

            {/* Gemini + Agent Health */}
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
                <div className="lg:col-span-3 bg-white rounded-2xl shadow-sm border border-slate-100 p-6">
                    <h3 className="font-bold text-slate-900 flex items-center gap-2 mb-6">
                        <TrendingUp className="text-green-500" size={20} /> Gemini Operational Metrics
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <p className="text-3xl font-bold text-slate-900">{ops?.gemini?.calls_today || 0}</p>
                            <p className="text-xs text-slate-500">API Calls Today</p>
                        </div>
                        <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <p className="text-3xl font-bold text-slate-900">{ops?.gemini?.error_rate_pct || 0}%</p>
                            <p className="text-xs text-slate-500">Error Rate</p>
                        </div>
                        <div className="p-4 bg-green-50 rounded-xl border border-green-100">
                            <p className="text-3xl font-bold text-green-600">ACTIVE</p>
                            <p className="text-xs text-green-600 opacity-80">Orchestrator Status</p>
                        </div>
                    </div>
                </div>

                <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-6">
                    <h3 className="font-bold text-slate-900 flex items-center gap-2 mb-6">
                        <ShieldCheck className="text-green-500" size={20} /> Agent Health
                    </h3>
                    <div className="space-y-4">
                        {agentHealth.length > 0 ? agentHealth.slice(0, 6).map((agent) => (
                            <div key={agent.name} className="flex items-center justify-between py-2 border-b border-slate-50 last:border-0">
                                <span className="text-xs font-semibold text-slate-600 truncate mr-2">{agent.name}</span>
                                <span className={`px-2 py-0.5 text-[9px] font-bold rounded shrink-0 ${agent.ok ? 'bg-green-100 text-green-700' : agent.status === 'IDLE' ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'}`}>
                                    {agent.status}
                                </span>
                            </div>
                        )) : (
                            <p className="text-xs text-slate-400 italic">No agent data available...</p>
                        )}
                    </div>
                </div>
            </div>

            {/* Job Trigger Panel */}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-6">
                <h3 className="font-bold text-slate-900 flex items-center gap-2 mb-6 text-sm">
                    <Play className="text-green-500" size={18} /> Pipeline Job Control
                </h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {AVAILABLE_JOBS.map((job) => {
                        const status = jobStatus[job.key];
                        return (
                            <button
                                key={job.key}
                                onClick={() => triggerJob(job.key)}
                                disabled={status === 'running'}
                                className="group p-4 bg-slate-50 hover:bg-green-50 border border-slate-100 hover:border-green-200 rounded-xl transition-all text-left disabled:opacity-60 active:scale-[0.98]"
                            >
                                <div className="flex items-center justify-between mb-2">
                                    <span className="text-xs font-bold text-slate-700 group-hover:text-green-700">{job.label}</span>
                                    {status === 'running' && <Loader2 size={14} className="animate-spin text-blue-500" />}
                                    {status === 'triggered' && <CheckCircle2 size={14} className="text-green-500" />}
                                    {status === 'error' && <XCircle size={14} className="text-red-500" />}
                                    {!status && <Play size={14} className="text-slate-400 group-hover:text-green-500" />}
                                </div>
                                <p className="text-[10px] text-slate-400 font-medium">{job.desc}</p>
                            </button>
                        );
                    })}
                </div>
            </div>
        </div>
    );
};

export default Dashboard;

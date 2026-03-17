import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
    Bot,
    Cpu,
    Brain,
    Search,
    FileCheck,
    Zap,
    Settings2,
    Activity,
    RefreshCw,
    Play,
    CheckCircle2,
    XCircle,
    Loader2,
    Globe,
} from 'lucide-react';
import { api } from '../services/api';

const AGENT_META = {
    memory_agent: { icon: Brain, desc: 'User preference learning from behavioral signals' },
    itinerary_qa: { icon: FileCheck, desc: 'Post-generation quality assurance and auto-fixing' },
    token_optimizer: { icon: Cpu, desc: 'Prompt compression for Gemini API cost reduction' },
    mcp_context: { icon: Globe, desc: 'Live weather, festivals, and travel alerts enrichment' },
    destination_validator: { icon: Search, desc: 'Validates new destination requests via external checks' },
    web_scraper: { icon: Zap, desc: 'Scrapes pricing and hours from attraction websites' },
    cache_warmer: { icon: RefreshCw, desc: 'Pre-generates itineraries for popular destinations' },
    quality_scorer: { icon: FileCheck, desc: 'Scores saved itineraries for quality metrics' },
    affiliate_health: { icon: Activity, desc: 'Monitors partner booking API health status' },
};

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

const AIAgentHub = () => {
    const [ops, setOps] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [triggering, setTriggering] = useState({});
    const [triggerSuccess, setTriggerSuccess] = useState({});

    const fetchData = useCallback(async () => {
        try {
            const data = await api.getOpsSummary();
            setOps(data);
            setError(null);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 15000);
        return () => clearInterval(interval);
    }, [fetchData]);

    const handleTriggerAgent = async (key) => {
        setTriggering(prev => ({ ...prev, [key]: true }));
        setTriggerSuccess(prev => ({ ...prev, [key]: null }));
        try {
            await api.triggerAgent(key);
            setTriggerSuccess(prev => ({ ...prev, [key]: 'ok' }));
            setTimeout(() => setTriggerSuccess(prev => ({ ...prev, [key]: null })), 4000);
            setTimeout(fetchData, 3000);
        } catch (err) {
            setTriggerSuccess(prev => ({ ...prev, [key]: 'error' }));
            setTimeout(() => setTriggerSuccess(prev => ({ ...prev, [key]: null })), 4000);
        } finally {
            setTriggering(prev => ({ ...prev, [key]: false }));
        }
    };

    const agents = Object.entries(ops?.agents || {}).map(([name, data]) => {
        const meta = AGENT_META[name] || { icon: Bot, desc: 'Agent component' };
        const status = data.status || 'never_run';
        const isOk = status === 'ok' || status === 'success' || status === 'complete' || status === 'optimal';
        return {
            name: name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
            key: name,
            icon: meta.icon,
            description: meta.desc,
            status: status === 'never_run' ? 'idle' : status,
            isOk,
            lastRun: data.last_run || 'Never',
            details: data.details || null,
        };
    });

    const celeryTasks = Object.entries(ops?.celery_tasks || {}).map(([name, data]) => ({
        name: name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
        status: data.status || 'never_run',
        lastRun: data.last_run || 'Never',
        isOk: data.status === 'ok',
    }));

    const totalOk = agents.filter((a) => a.isOk).length;
    const totalAgents = agents.length;

    if (loading && !ops) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
                <RefreshCw className="text-green-500 animate-spin" size={40} />
                <p className="text-slate-500 font-bold uppercase tracking-widest text-xs">Synchronizing Neural Network...</p>
            </div>
        );
    }

    return (
        <div className="space-y-10 animate-fade-in">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-4xl font-black text-slate-900 tracking-tight">AI Agent Matrix</h2>
                    <p className="text-sm text-slate-500 font-medium">Global orchestration layer for autonomous sub-processes.</p>
                </div>
                <div className="flex gap-4">
                    <div className="bg-white px-6 py-3 rounded-[1.5rem] border border-slate-100 shadow-xl shadow-slate-200/50 flex items-center gap-4">
                        <div className={`size-10 rounded-2xl flex items-center justify-center shadow-inner ${totalOk === totalAgents ? 'bg-green-50 text-green-600' : 'bg-amber-50 text-amber-600'}`}>
                            <Activity size={20} />
                        </div>
                        <div className="flex flex-col">
                            <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest leading-none mb-1">Fleet Health</span>
                            <span className="text-lg font-black text-slate-900 leading-none">
                                {totalAgents > 0 ? `${totalOk}/${totalAgents} ONLINE` : 'INIT...'}
                            </span>
                        </div>
                    </div>
                    <button onClick={fetchData} className="size-14 flex items-center justify-center rounded-2xl bg-white border border-slate-100 shadow-xl shadow-slate-200/50 hover:bg-slate-50 transition-all active:scale-95">
                        <RefreshCw size={24} className="text-slate-500" />
                    </button>
                </div>
            </div>

            {error && (
                <div className="bg-red-50 border border-red-200 p-6 rounded-[2rem] flex items-center gap-4 text-red-700 font-bold">
                    <XCircle size={24} />
                    <p>Matrix Connection Interrupted: {error}</p>
                </div>
            )}

            {/* Agent Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                {agents.map((agent) => (
                    <div key={agent.key} className="bg-white rounded-[2.5rem] shadow-xl shadow-slate-200/40 border border-slate-100 p-8 hover:shadow-2xl hover:-translate-y-1 transition-all group overflow-hidden relative">
                        {/* Background Decor */}
                        <div className={`absolute -right-4 -top-4 size-32 opacity-[0.03] group-hover:opacity-[0.08] transition-opacity ${agent.isOk ? 'text-green-500' : 'text-amber-500'}`}>
                            <agent.icon size={128} />
                        </div>

                        <div className="flex justify-between items-start mb-6 relative z-10">
                            <div className={`size-16 rounded-[1.5rem] flex items-center justify-center shadow-lg ${agent.isOk ? 'bg-green-500 text-white shadow-green-500/20' : agent.status === 'idle' ? 'bg-slate-100 text-slate-400 shadow-none' : 'bg-amber-500 text-white shadow-amber-500/20'}`}>
                                <agent.icon size={32} />
                            </div>
                            <div className="flex flex-col items-end">
                                <span className="text-[10px] font-black text-slate-300 uppercase tracking-widest mb-1">{fmtRelTime(agent.lastRun)}</span>
                                <span className={`px-3 py-1 text-[10px] font-black rounded-lg uppercase tracking-tighter ${agent.isOk ? 'bg-green-100 text-green-700' : agent.status === 'idle' ? 'bg-slate-100 text-slate-500' : 'bg-amber-100 text-amber-700'}`}>
                                    {agent.status}
                                </span>
                            </div>
                        </div>

                        <div className="relative z-10 space-y-2 mb-8">
                            <h4 className="text-xl font-black text-slate-900 leading-tight">{agent.name}</h4>
                            <p className="text-xs text-slate-500 leading-relaxed font-bold">{agent.description}</p>
                        </div>

                        <div className="relative z-10 flex gap-4 pt-6 border-t border-slate-50">
                            <button
                                onClick={() => handleTriggerAgent(agent.key)}
                                disabled={triggering[agent.key]}
                                className={`flex-1 py-3 rounded-2xl font-black text-[10px] uppercase tracking-widest shadow-lg transition-all flex items-center justify-center gap-2 active:scale-95 disabled:opacity-50 ${
                                    triggerSuccess[agent.key] === 'ok'
                                        ? 'bg-green-500 text-white shadow-green-500/20'
                                        : triggerSuccess[agent.key] === 'error'
                                        ? 'bg-red-500 text-white shadow-red-500/20'
                                        : 'bg-slate-900 text-white shadow-slate-900/20 hover:bg-slate-800'
                                }`}
                            >
                                {triggering[agent.key] ? <Loader2 size={14} className="animate-spin" /> :
                                 triggerSuccess[agent.key] === 'ok' ? <CheckCircle2 size={14} /> :
                                 triggerSuccess[agent.key] === 'error' ? <XCircle size={14} /> :
                                 <Play size={14} fill="currentColor" />}
                                {triggering[agent.key] ? 'QUEUING...' :
                                 triggerSuccess[agent.key] === 'ok' ? 'DISPATCHED!' :
                                 triggerSuccess[agent.key] === 'error' ? 'FAILED' :
                                 'TRIGGER AGENT'}
                            </button>
                            <Link to="/settings" className="p-3 bg-slate-50 text-slate-400 rounded-2xl border border-slate-100 hover:text-slate-600 transition-all">
                                <Settings2 size={18} />
                            </Link>
                        </div>
                    </div>
                ))}
            </div>

            {/* System Engine Health */}
            {celeryTasks.length > 0 && (
                <div className="bg-slate-950 rounded-[3rem] shadow-2xl p-10 relative overflow-hidden group">
                    <div className="absolute top-0 right-0 w-96 h-96 bg-green-500/10 blur-[120px] -mr-48 -mt-48 transition-all duration-1000 group-hover:bg-green-500/20" />

                    <div className="relative z-10 flex flex-col md:flex-row gap-10 items-start justify-between">
                        <div className="space-y-4">
                            <div className="inline-flex items-center gap-2 px-3 py-1 bg-green-500 text-white rounded-full text-[10px] font-black uppercase tracking-widest">
                                <Cpu size={12} /> System Core
                            </div>
                            <h3 className="text-3xl font-black text-white">Distributed Pipeline Health</h3>
                            <p className="text-slate-400 font-medium max-w-sm">Status of background worker threads managing heavy computational geometry and LLM reasoning.</p>
                        </div>

                        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 w-full md:w-auto">
                            {celeryTasks.map((task) => (
                                <div key={task.name} className="p-5 bg-white/5 border border-white/10 rounded-[1.5rem] backdrop-blur-md flex flex-col justify-between group/task hover:bg-white/10 transition-all">
                                    <div className="flex items-center justify-between mb-4">
                                        <span className="text-[10px] font-black text-white uppercase tracking-widest truncate mr-4">{task.name}</span>
                                        {task.isOk ? <CheckCircle2 size={16} className="text-green-500" /> : <Activity size={16} className="text-amber-500 animate-pulse" />}
                                    </div>
                                    <div className="space-y-1">
                                        <p className="text-[9px] text-slate-500 font-black uppercase tracking-widest">Last Execution</p>
                                        <p className="text-xs text-slate-300 font-bold">{fmtRelTime(task.lastRun)}</p>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default AIAgentHub;

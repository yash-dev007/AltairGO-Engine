import React, { useState, useEffect, useCallback } from 'react';
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
    Globe
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

const AIAgentHub = () => {
    const [ops, setOps] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

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
                <p className="text-slate-500 font-medium">Loading agent status...</p>
            </div>
        );
    }

    return (
        <div className="space-y-8 max-w-7xl mx-auto w-full">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-3xl font-extrabold text-slate-900 tracking-tight">AI Agent Matrix</h2>
                    <p className="text-sm text-slate-500 font-medium">Real-time monitoring of autonomous agent coordination.</p>
                </div>
                <div className="flex gap-3">
                    <div className="bg-white px-4 py-2.5 rounded-2xl border border-slate-100 shadow-sm flex items-center gap-3">
                        <div className={`size-8 rounded-full flex items-center justify-center ${totalOk === totalAgents ? 'bg-green-100 text-green-600' : 'bg-amber-100 text-amber-600'}`}>
                            <Activity size={16} />
                        </div>
                        <div className="flex flex-col">
                            <span className="text-[10px] font-bold text-slate-400 uppercase leading-none">Global Health</span>
                            <span className="text-sm font-bold text-slate-900 uppercase leading-none mt-1">
                                {totalAgents > 0 ? `${totalOk}/${totalAgents} OK` : 'No Data'}
                            </span>
                        </div>
                    </div>
                    <button onClick={fetchData} className="size-10 flex items-center justify-center rounded-xl bg-white border border-slate-100 shadow-sm hover:bg-slate-50 transition-colors">
                        <RefreshCw size={16} className="text-slate-500" />
                    </button>
                </div>
            </div>

            {error && (
                <div className="bg-red-50 border border-red-200 p-4 rounded-xl flex items-center gap-3 text-red-700 text-sm">
                    <XCircle size={18} />
                    {error}
                </div>
            )}

            {/* Agent Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {agents.map((agent) => (
                    <div key={agent.key} className="bg-white rounded-2xl shadow-sm border border-slate-100 p-6 hover:shadow-md transition-shadow group">
                        <div className="flex justify-between items-start mb-4">
                            <div className={`size-12 rounded-xl flex items-center justify-center ${agent.isOk ? 'bg-green-100 text-green-600' : agent.status === 'idle' ? 'bg-slate-100 text-slate-400' : 'bg-amber-100 text-amber-600'}`}>
                                <agent.icon size={24} />
                            </div>
                            <div className="flex flex-col items-end">
                                <span className="text-[10px] font-bold text-slate-400">{agent.lastRun}</span>
                                <span className={`px-2 py-0.5 text-[10px] font-bold rounded mt-1 uppercase ${agent.isOk ? 'bg-green-100 text-green-700' : agent.status === 'idle' ? 'bg-slate-100 text-slate-500' : 'bg-amber-100 text-amber-700'}`}>
                                    {agent.status}
                                </span>
                            </div>
                        </div>
                        <h4 className="font-bold text-slate-900 mb-2">{agent.name}</h4>
                        <p className="text-xs text-slate-500 mb-4 leading-relaxed font-medium">{agent.description}</p>
                    </div>
                ))}
            </div>

            {/* Celery Tasks */}
            {celeryTasks.length > 0 && (
                <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-6">
                    <h3 className="font-bold text-slate-900 flex items-center gap-2 mb-4 text-sm">
                        <Settings2 className="text-green-500" size={18} /> Celery Task Status
                    </h3>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        {celeryTasks.map((task) => (
                            <div key={task.name} className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                                <div className="flex items-center justify-between mb-1">
                                    <span className="text-xs font-bold text-slate-700 truncate">{task.name}</span>
                                    {task.isOk ? <CheckCircle2 size={14} className="text-green-500" /> : <XCircle size={14} className="text-slate-300" />}
                                </div>
                                <p className="text-[10px] text-slate-400">{task.lastRun}</p>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};

export default AIAgentHub;

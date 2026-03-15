import React, { useState, useEffect } from 'react';
import { Settings, Shield, Sliders, Zap, Database, AlertTriangle, RefreshCw, Key, Globe } from 'lucide-react';
import { api } from '../services/api';

const IntelligenceHub = () => {
    const [config, setConfig] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const fetchConfig = async () => {
        setLoading(true);
        try {
            const data = await api.getEngineConfig();
            setConfig(data);
            setError(null);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchConfig();
    }, []);

    if (loading && !config) {
        return (
            <div className="flex justify-center items-center min-h-[50vh]">
                <RefreshCw className="animate-spin text-green-500" size={32} />
            </div>
        );
    }

    return (
        <div className="space-y-8 max-w-5xl mx-auto w-full">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-3xl font-extrabold text-slate-900 tracking-tight">Intelligence Config</h2>
                    <p className="text-sm text-slate-500 font-medium">Core engine routing and threshold tuning.</p>
                </div>
                <button
                    onClick={fetchConfig}
                    className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 rounded-xl text-sm font-bold shadow-sm hover:bg-slate-50 transition-colors"
                >
                    <RefreshCw size={16} /> REFRESH
                </button>
            </div>

            {error && (
                <div className="bg-red-50 border border-red-200 p-4 rounded-xl flex items-center gap-3 text-red-700 text-sm">
                    <AlertTriangle size={18} />
                    {error}
                </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Engine Thresholds */}
                <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-6 space-y-6">
                    <div className="flex items-center gap-3 pb-4 border-b border-slate-100">
                        <div className="size-10 bg-green-50 text-green-600 rounded-xl flex items-center justify-center">
                            <Sliders size={20} />
                        </div>
                        <div>
                            <h3 className="font-bold text-slate-900">Engine Variables</h3>
                            <p className="text-xs text-slate-500">Live configuration states</p>
                        </div>
                    </div>

                    <div className="space-y-4">
                        <div className="flex justify-between items-center p-3 bg-slate-50 rounded-xl border border-slate-100">
                            <div>
                                <p className="text-sm font-bold text-slate-700">Strict Validation</p>
                                <p className="text-[10px] text-slate-500">Enforce schema matching</p>
                            </div>
                            <span className={`px-2 py-1 text-[10px] uppercase font-bold rounded ${config?.VALIDATION_STRICT ? 'bg-green-100 text-green-700' : 'bg-slate-200 text-slate-500'}`}>
                                {config?.VALIDATION_STRICT ? 'Enabled' : 'Disabled'}
                            </span>
                        </div>
                        <div className="flex justify-between items-center p-3 bg-slate-50 rounded-xl border border-slate-100">
                            <div>
                                <p className="text-sm font-bold text-slate-700">Theme Threshold</p>
                                <p className="text-[10px] text-slate-500">Minimum topical relevance</p>
                            </div>
                            <span className="font-mono text-sm font-bold text-blue-600 bg-blue-50 px-2 py-1 rounded border border-blue-100">
                                {config?.THEME_THRESHOLD || '0.2'}
                            </span>
                        </div>
                        <div className="flex justify-between items-center p-3 bg-slate-50 rounded-xl border border-slate-100">
                            <div>
                                <p className="text-sm font-bold text-slate-700">Active LLM Model</p>
                                <p className="text-[10px] text-slate-500">Core reasoning engine</p>
                            </div>
                            <span className="font-mono text-xs font-bold text-purple-600 bg-purple-50 px-2 py-1 rounded border border-purple-100">
                                {config?.GEMINI_MODEL || 'gemini-1.5-pro'}
                            </span>
                        </div>
                    </div>
                </div>

                {/* API Auth Limits */}
                <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-6 space-y-6">
                    <div className="flex items-center gap-3 pb-4 border-b border-slate-100">
                        <div className="size-10 bg-blue-50 text-blue-600 rounded-xl flex items-center justify-center">
                            <Shield size={20} />
                        </div>
                        <div>
                            <h3 className="font-bold text-slate-900">Security & Limits</h3>
                            <p className="text-xs text-slate-500">Rate limiting constraints</p>
                        </div>
                    </div>

                    <div className="space-y-4">
                        <div className="flex items-center gap-3 p-3 border-l-4 border-blue-500 bg-slate-50 rounded-r-xl">
                            <Globe className="text-slate-400" size={16} />
                            <div>
                                <p className="text-xs font-bold text-slate-700">Public Destinations API</p>
                                <p className="text-[10px] text-slate-500">30 requests / minute / IP</p>
                            </div>
                        </div>
                        <div className="flex items-center gap-3 p-3 border-l-4 border-purple-500 bg-slate-50 rounded-r-xl">
                            <Zap className="text-slate-400" size={16} />
                            <div>
                                <p className="text-xs font-bold text-slate-700">Attraction Signals</p>
                                <p className="text-[10px] text-slate-500">60 requests / minute / IP</p>
                            </div>
                        </div>
                        <div className="flex items-center gap-3 p-3 border-l-4 border-red-500 bg-slate-50 rounded-r-xl">
                            <Key className="text-slate-400" size={16} />
                            <div>
                                <p className="text-xs font-bold text-slate-700">Admin Authentication</p>
                                <p className="text-[10px] text-slate-500">10 requests / minute / IP</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default IntelligenceHub;

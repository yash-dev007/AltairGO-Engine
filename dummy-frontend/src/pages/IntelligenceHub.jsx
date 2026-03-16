import React, { useState, useEffect } from 'react';
import { Settings, Shield, Sliders, Zap, Database, AlertTriangle, RefreshCw, Key, Globe, Save, CheckCircle2 } from 'lucide-react';
import { api } from '../services/api';

const IntelligenceHub = () => {
    const [config, setConfig] = useState({
        VALIDATION_STRICT: false,
        GEMINI_MODEL: 'gemini-1.5-pro',
        THEME_THRESHOLD: 0.20
    });
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(false);

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

    const handleSave = async (e) => {
        e.preventDefault();
        setSaving(true);
        setSuccess(false);
        try {
            await api.updateEngineConfig(config);
            setSuccess(true);
            setTimeout(() => setSuccess(false), 3000);
        } catch (err) {
            setError(err.message);
        } finally {
            setSaving(false);
        }
    };

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
                <div className="flex gap-3">
                    <button
                        onClick={fetchConfig}
                        className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 rounded-xl text-sm font-bold shadow-sm hover:bg-slate-50 transition-colors"
                    >
                        <RefreshCw size={16} /> REFRESH
                    </button>
                    <button
                        onClick={handleSave}
                        disabled={saving}
                        className="flex items-center gap-2 px-6 py-2 bg-green-500 text-white rounded-xl text-sm font-bold shadow-lg shadow-green-500/20 hover:bg-green-600 transition-all active:scale-95 disabled:opacity-50"
                    >
                        {saving ? <RefreshCw size={16} className="animate-spin" /> : <Save size={16} />}
                        {success ? 'SAVED!' : 'SAVE CHANGES'}
                    </button>
                </div>
            </div>

            {error && (
                <div className="bg-red-50 border border-red-200 p-4 rounded-xl flex items-center gap-3 text-red-700 text-sm">
                    <AlertTriangle size={18} />
                    {error}
                </div>
            )}

            {success && (
                <div className="bg-green-50 border border-green-200 p-4 rounded-xl flex items-center gap-3 text-green-700 text-sm animate-fade-in">
                    <CheckCircle2 size={18} />
                    Configuration updated successfully and applied to active workers.
                </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {/* Engine Thresholds */}
                <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-8 space-y-8">
                    <div className="flex items-center gap-4">
                        <div className="size-12 bg-green-50 text-green-600 rounded-2xl flex items-center justify-center shadow-inner">
                            <Sliders size={24} />
                        </div>
                        <div>
                            <h3 className="font-bold text-slate-900 text-lg">Engine Variables</h3>
                            <p className="text-xs text-slate-500 font-medium">Calibrate reasoning and filtering</p>
                        </div>
                    </div>

                    <div className="space-y-6">
                        <div className="space-y-2">
                            <div className="flex justify-between items-center">
                                <label className="text-sm font-bold text-slate-700">Strict Validation</label>
                                <button
                                    onClick={() => setConfig({ ...config, VALIDATION_STRICT: !config.VALIDATION_STRICT })}
                                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${config.VALIDATION_STRICT ? 'bg-green-500' : 'bg-slate-200'}`}
                                >
                                    <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${config.VALIDATION_STRICT ? 'translate-x-6' : 'translate-x-1'}`} />
                                </button>
                            </div>
                            <p className="text-[10px] text-slate-400 font-medium leading-relaxed">
                                When enabled, the engine will discard any LLM outputs that do not exactly match the requested JSON schema.
                            </p>
                        </div>

                        <div className="space-y-4">
                            <div className="flex justify-between items-center">
                                <label className="text-sm font-bold text-slate-700">Theme Threshold</label>
                                <span className="font-mono text-sm font-black text-green-600 tabular-nums">
                                    {(config.THEME_THRESHOLD * 100).toFixed(0)}%
                                </span>
                            </div>
                            <input
                                type="range" min="0" max="1" step="0.05"
                                value={config.THEME_THRESHOLD}
                                onChange={(e) => setConfig({ ...config, THEME_THRESHOLD: parseFloat(e.target.value) })}
                                className="w-full h-2 bg-slate-100 rounded-lg appearance-none cursor-pointer accent-green-500"
                            />
                            <p className="text-[10px] text-slate-400 font-medium leading-relaxed">
                                Minimum relevance score required to include an attraction in a themed itinerary.
                            </p>
                        </div>

                        <div className="space-y-3 pt-2">
                            <label className="text-sm font-bold text-slate-700">Reasoning Model</label>
                            <select
                                value={config.GEMINI_MODEL}
                                onChange={(e) => setConfig({ ...config, GEMINI_MODEL: e.target.value })}
                                className="w-full px-4 py-3 bg-slate-50 border border-slate-100 rounded-xl text-sm font-bold text-slate-900 outline-none focus:ring-2 focus:ring-green-500/20 focus:border-green-500 transition-all"
                            >
                                <option value="gemini-1.5-pro">Gemini 1.5 Pro (Balanced)</option>
                                <option value="gemini-1.5-flash">Gemini 1.5 Flash (Fast)</option>
                                <option value="gemini-2.0-pro">Gemini 2.0 Pro Experimental</option>
                            </select>
                        </div>
                    </div>
                </div>

                {/* API Auth Limits (Read Only for now) */}
                <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-8 space-y-8 opacity-90 transition-opacity hover:opacity-100">
                    <div className="flex items-center gap-4">
                        <div className="size-12 bg-blue-50 text-blue-600 rounded-2xl flex items-center justify-center shadow-inner">
                            <Shield size={24} />
                        </div>
                        <div>
                            <h3 className="font-bold text-slate-900 text-lg">Guardrails & Quotas</h3>
                            <p className="text-xs text-slate-500 font-medium">Environmental safety constraints</p>
                        </div>
                    </div>

                    <div className="space-y-4">
                        {[
                            { icon: Globe, label: 'Public Destinations API', limit: '30 req/min', color: 'blue' },
                            { icon: Zap, label: 'Attraction Signals', limit: '60 req/min', color: 'purple' },
                            { icon: Key, label: 'Admin Access Control', limit: '10 req/min', color: 'red' },
                        ].map((item, i) => (
                            <div key={i} className="flex items-center gap-4 p-4 bg-slate-50/50 rounded-2xl border border-slate-100 group">
                                <item.icon className={`text-slate-400 group-hover:text-${item.color}-500 transition-colors`} size={18} />
                                <div>
                                    <p className="text-xs font-extrabold text-slate-700 tracking-tight">{item.label}</p>
                                    <p className="text-[10px] text-slate-500 font-bold uppercase">{item.limit}</p>
                                </div>
                            </div>
                        ))}

                        <div className="mt-8 p-4 bg-amber-50 rounded-2xl border border-amber-100 flex gap-3">
                            <AlertTriangle className="text-amber-500 shrink-0" size={16} />
                            <p className="text-[10px] text-amber-700 font-bold leading-relaxed">
                                Quotas are managed at the infrastructure layer (Nginx/Cloudflare) and cannot be overridden from this panel.
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default IntelligenceHub;

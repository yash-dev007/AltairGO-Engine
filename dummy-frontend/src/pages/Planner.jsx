import React, { useState } from 'react';
import {
    MapPin,
    Calendar,
    Briefcase,
    Globe,
    Sparkles,
    AlertCircle,
    RefreshCw,
    Send,
    DollarSign,
    Clock,
    Database
} from 'lucide-react';
import { api } from '../services/api';

const Planner = () => {
    const [formData, setFormData] = useState({
        destination: '',
        budget: 2000,
        duration: 7,
        travelers: 1,
        style: 'balanced'
    });
    const [generating, setGenerating] = useState(false);
    const [status, setStatus] = useState(null);
    const [error, setError] = useState(null);
    const [result, setResult] = useState(null);

    const handleGenerate = async (e) => {
        e.preventDefault();
        if (!formData.destination) return;

        setGenerating(true);
        setError(null);
        setResult(null);
        setStatus("Initializing core engine...");

        try {
            const data = await api.generateItinerary(
                formData.destination,
                formData.budget,
                formData.duration,
                formData.travelers
            );
            pollStatus(data.job_id);
        } catch (err) {
            setError(err.message);
            setGenerating(false);
        }
    };

    const pollStatus = async (id) => {
        const interval = setInterval(async () => {
            try {
                const data = await api.getItineraryStatus(id);
                setStatus(data.status);

                if (data.status === 'completed') {
                    setResult(data.result);
                    setGenerating(false);
                    clearInterval(interval);
                } else if (data.status === 'failed') {
                    setError(data.error || "Generation failed at the reasoning layer.");
                    setGenerating(false);
                    clearInterval(interval);
                }
            } catch (err) {
                console.error("Polling error:", err);
            }
        }, 2000);
    };

    return (
        <div className="max-w-6xl mx-auto space-y-12 animate-fade-in">
            <div className="text-center space-y-4">
                <h1 className="text-5xl font-black text-slate-900 tracking-tight leading-tight">
                    Autonomous <span className="text-green-500">Trip Architect</span>
                </h1>
                <p className="text-lg text-slate-500 font-medium max-w-2xl mx-auto">
                    Configure your constraints and let the intelligence engine weave a perfect itinerary using global attraction signals.
                </p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-12">
                {/* Configuration Panel */}
                <div className="lg:col-span-1 space-y-8">
                    <form onSubmit={handleGenerate} className="bg-white rounded-[2.5rem] border border-slate-100 shadow-2xl p-8 space-y-8">
                        <div className="space-y-6">
                            <div className="space-y-2">
                                <label className="text-xs font-black text-slate-400 uppercase tracking-widest ml-1">Destination Target</label>
                                <div className="relative group">
                                    <MapPin className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-300 group-focus-within:text-green-500 transition-colors" size={20} />
                                    <input
                                        type="text"
                                        placeholder="Where to explore?"
                                        className="w-full pl-12 pr-4 py-4 bg-slate-50 border border-slate-100 rounded-2xl font-bold text-slate-900 outline-none focus:ring-4 focus:ring-green-500/10 focus:border-green-500 transition-all placeholder:text-slate-300"
                                        value={formData.destination}
                                        onChange={(e) => setFormData({ ...formData, destination: e.target.value })}
                                    />
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <label className="text-xs font-black text-slate-400 uppercase tracking-widest ml-1">Total Budget</label>
                                    <div className="relative">
                                        <DollarSign className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                                        <input
                                            type="number"
                                            className="w-full pl-10 pr-4 py-3 bg-slate-50 border border-slate-100 rounded-xl font-bold text-slate-900 outline-none focus:border-green-500"
                                            value={formData.budget}
                                            onChange={(e) => setFormData({ ...formData, budget: parseInt(e.target.value) })}
                                        />
                                    </div>
                                </div>
                                <div className="space-y-2">
                                    <label className="text-xs font-black text-slate-400 uppercase tracking-widest ml-1">Duration (Days)</label>
                                    <div className="relative">
                                        <Clock className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                                        <input
                                            type="number"
                                            className="w-full pl-10 pr-4 py-3 bg-slate-50 border border-slate-100 rounded-xl font-bold text-slate-900 outline-none focus:border-green-500"
                                            value={formData.duration}
                                            onChange={(e) => setFormData({ ...formData, duration: parseInt(e.target.value) })}
                                        />
                                    </div>
                                </div>
                            </div>

                            <div className="space-y-3">
                                <label className="text-xs font-black text-slate-400 uppercase tracking-widest ml-1">Experience Style</label>
                                <div className="grid grid-cols-2 gap-2">
                                    {['balanced', 'adventure', 'luxury', 'culture'].map((style) => (
                                        <button
                                            key={style}
                                            type="button"
                                            onClick={() => setFormData({ ...formData, style })}
                                            className={`py-2 rounded-xl text-[10px] font-black uppercase tracking-wider transition-all border ${formData.style === style
                                                    ? 'bg-green-500 text-white border-green-500 shadow-lg shadow-green-500/20'
                                                    : 'bg-white text-slate-500 border-slate-100 hover:border-slate-200'
                                                }`}
                                        >
                                            {style}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        </div>

                        <button
                            type="submit"
                            disabled={generating || !formData.destination}
                            className="w-full py-5 bg-slate-900 text-white rounded-[1.5rem] font-black text-sm uppercase tracking-[0.2em] shadow-xl hover:bg-slate-800 transition-all active:scale-95 disabled:opacity-50 flex items-center justify-center gap-3"
                        >
                            {generating ? <RefreshCw className="animate-spin" size={20} /> : <Sparkles size={20} className="text-green-500" />}
                            {generating ? 'Architecting...' : 'Build Itinerary'}
                        </button>
                    </form>

                    {generating && (
                        <div className="bg-green-50 border border-green-200 rounded-3xl p-6 space-y-4 animate-pulse">
                            <div className="flex items-center gap-3">
                                <div className="size-8 bg-green-500 text-white rounded-lg flex items-center justify-center font-black text-xs">AI</div>
                                <h4 className="font-bold text-green-800 uppercase text-xs tracking-widest">Pipeline Active</h4>
                            </div>
                            <p className="text-sm font-bold text-green-700 capitalize">{status?.replace('_', ' ')}...</p>
                            <div className="w-full bg-green-200 h-1.5 rounded-full overflow-hidden">
                                <div className="bg-green-600 h-full w-1/3 animate-progress" />
                            </div>
                        </div>
                    )}

                    {error && (
                        <div className="bg-red-50 border border-red-200 rounded-3xl p-6 flex gap-4">
                            <AlertCircle className="text-red-500 shrink-0" size={20} />
                            <p className="text-sm font-bold text-red-700 leading-relaxed">{error}</p>
                        </div>
                    )}
                </div>

                {/* Result Display */}
                <div className="lg:col-span-2 space-y-8">
                    {result ? (
                        <div className="bg-white rounded-[3rem] border border-slate-100 shadow-2xl p-10 space-y-10 animate-scale-in">
                            <div className="flex justify-between items-start">
                                <div className="space-y-2">
                                    <h2 className="text-4xl font-black text-slate-900 leading-tight">{result.trip_title}</h2>
                                    <div className="flex gap-4">
                                        <span className="flex items-center gap-1.5 text-xs font-black text-green-600 bg-green-50 px-3 py-1 rounded-full uppercase tracking-tighter">
                                            <Globe size={14} /> {formData.destination}
                                        </span>
                                        <span className="flex items-center gap-1.5 text-xs font-black text-blue-600 bg-blue-50 px-3 py-1 rounded-full uppercase tracking-tighter">
                                            <Calendar size={14} /> {formData.duration} Days
                                        </span>
                                    </div>
                                </div>
                                <button className="p-4 bg-slate-50 text-slate-400 rounded-2xl border border-slate-100 hover:text-slate-600 transition-all">
                                    <Send size={24} />
                                </button>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                {result.itinerary?.map((day, idx) => (
                                    <div key={idx} className="p-6 bg-slate-50 rounded-3xl border border-slate-100 space-y-4 group hover:bg-white hover:shadow-xl transition-all flex flex-col">
                                        <h3 className="font-black text-slate-400 group-hover:text-green-500 transition-colors uppercase tracking-widest text-[10px]">Day {day.day_number}</h3>
                                        <p className="font-bold text-slate-800 text-sm leading-relaxed mb-4">{day.description}</p>
                                        <div className="space-y-2 pt-2 border-t border-slate-200/50">
                                            {day.activities?.map((act, i) => (
                                                <div key={i} className="flex items-start gap-2">
                                                    <div className="size-1 bg-green-500 rounded-full mt-2 shrink-0" />
                                                    <p className="text-xs text-slate-500 font-medium">{act}</p>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    ) : !generating ? (
                        <div className="h-full flex flex-col items-center justify-center p-20 border-4 border-dashed border-slate-100 rounded-[4rem] text-center space-y-6">
                            <div className="size-24 bg-slate-50 rounded-full flex items-center justify-center text-slate-200">
                                <Briefcase size={48} />
                            </div>
                            <div className="space-y-2">
                                <h3 className="text-2xl font-black text-slate-400">Awaiting Specifications</h3>
                                <p className="text-sm text-slate-300 font-medium max-w-xs">Fill out the parameters on the left to activate the generation pipeline.</p>
                            </div>
                        </div>
                    ) : null}
                </div>
            </div>
        </div>
    );
};

export default Planner;

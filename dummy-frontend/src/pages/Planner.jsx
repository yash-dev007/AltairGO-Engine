import React, { useState } from 'react';
import {
    Compass,
    MapPin,
    Settings2,
    Sparkles,
    AlertCircle,
    Calendar,
    Wallet,
    Users as UsersIcon
} from 'lucide-react';

async function waitForItinerary(apiBase, jobId) {
    for (let attempt = 0; attempt < 30; attempt += 1) {
        const response = await fetch(`${apiBase}/get-itinerary-status/${jobId}`);
        const payload = await response.json();

        if (!response.ok) throw new Error(payload.error || 'Failed to fetch itinerary status');
        if (payload.status === 'completed') return payload.result;
        if (payload.status === 'failed') throw new Error(payload.error || 'Itinerary generation failed');

        await new Promise((resolve) => window.setTimeout(resolve, 1000));
    }
    throw new Error('Itinerary generation timed out');
}

const PlannerApp = () => {
    const [loading, setLoading] = useState(false);
    const [itinerary, setItinerary] = useState(null);
    const [error, setError] = useState(null);
    const [city, setCity] = useState('Jaipur');
    const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:5000';

    const generateItinerary = async () => {
        setLoading(true);
        setError(null);
        setItinerary(null);

        const payload = {
            destination_country: 'India',
            start_city: city,
            selected_destinations: [{ id: 1, name: city, estimated_cost_per_day: 3000 }],
            budget: 15000,
            duration: 3,
            travelers: 2,
            style: 'luxury',
            traveler_type: 'couple',
            use_engine: true
        };

        try {
            const response = await fetch(`${apiBase}/generate-itinerary`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Failed to queue itinerary');

            const result = await waitForItinerary(apiBase, data.job_id);
            setItinerary(result);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="space-y-8 max-w-7xl mx-auto w-full">
            <div className="bg-white rounded-3xl p-8 border border-slate-100 shadow-xl relative overflow-hidden">
                <div className="absolute top-0 right-0 w-64 h-64 bg-green-500/5 blur-3xl -mr-32 -mt-32"></div>

                <div className="relative z-10 flex flex-col md:flex-row gap-8 items-start justify-between">
                    <div className="space-y-4 flex-1">
                        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-green-500/10 text-green-500 text-[10px] font-extrabold uppercase">
                            <Sparkles size={12} /> AI-Powered Discovery
                        </div>
                        <h1 className="text-4xl font-extrabold text-slate-900 leading-tight tracking-tight">
                            Where will your <span className="text-green-500 italic font-black">next adventure</span> begin?
                        </h1>
                        <p className="text-slate-500 max-w-md font-medium">
                            Select a gateway and let our neural engine curate a pixel-perfect itinerary for your style.
                        </p>
                    </div>

                    <div className="w-full md:w-80 space-y-4 shrink-0">
                        <div className="space-y-1.5">
                            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest px-1">STARTING CITY</label>
                            <div className="relative">
                                <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
                                <select
                                    value={city}
                                    onChange={(e) => setCity(e.target.value)}
                                    className="w-full pl-10 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-2xl text-sm font-semibold focus:ring-2 focus:ring-green-500 outline-none"
                                >
                                    <option value="Jaipur">Jaipur (Culture)</option>
                                    <option value="Goa">Goa (Coastal)</option>
                                    <option value="Mumbai">Mumbai (Metro)</option>
                                </select>
                            </div>
                        </div>

                        <button
                            onClick={generateItinerary}
                            disabled={loading}
                            className={`w-full py-4 rounded-2xl font-extrabold text-sm tracking-widest uppercase transition-all flex items-center justify-center gap-3 ${loading
                                ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
                                : 'bg-green-500 hover:bg-green-600 text-white shadow-lg shadow-green-500/20 active:scale-[0.98]'
                                }`}
                        >
                            {loading ? <div className="size-4 border-2 border-slate-300 border-t-slate-500 rounded-full animate-spin"></div> : <Compass size={18} />}
                            {loading ? 'CONSULTING ENGINE...' : 'GENERATE TRIP'}
                        </button>
                    </div>
                </div>

                {error && (
                    <div className="mt-8 p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center gap-3 text-red-500">
                        <AlertCircle size={20} />
                        <span className="text-sm font-bold">Error: {error}</span>
                    </div>
                )}
            </div>

            {itinerary && (
                <div className="space-y-10 animate-fade-in">
                    <div className="flex flex-col md:flex-row gap-6 items-end justify-between">
                        <div>
                            <h2 className="text-4xl font-black text-slate-900 lowercase tracking-tighter">
                                {itinerary.trip_title}
                            </h2>
                            <div className="flex gap-4 mt-4">
                                <div className="flex items-center gap-1.5 text-xs font-bold text-slate-600 bg-white px-3 py-1.5 rounded-full border border-slate-200 shadow-sm">
                                    <Wallet className="text-green-500" size={14} /> Est. Rs.{itinerary.total_cost}
                                </div>
                                <div className="flex items-center gap-1.5 text-xs font-bold text-slate-600 bg-white px-3 py-1.5 rounded-full border border-slate-200 shadow-sm">
                                    <Calendar className="text-blue-500" size={14} /> {itinerary.duration} Days
                                </div>
                                <div className="flex items-center gap-1.5 text-xs font-bold text-slate-600 bg-white px-3 py-1.5 rounded-full border border-slate-200 shadow-sm">
                                    <UsersIcon className="text-purple-500" size={14} /> {itinerary.travelers} Persons
                                </div>
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-4 w-full md:w-auto">
                            <div className="bg-white p-4 rounded-xl border border-slate-200 text-center">
                                <p className="text-[10px] font-bold text-slate-400 uppercase">Stay</p>
                                <p className="text-sm font-bold">Rs.{itinerary.cost_breakdown.accommodation}</p>
                            </div>
                            <div className="bg-white p-4 rounded-xl border border-slate-200 text-center">
                                <p className="text-[10px] font-bold text-slate-400 uppercase">Food</p>
                                <p className="text-sm font-bold">Rs.{itinerary.cost_breakdown.food}</p>
                            </div>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                        {itinerary.itinerary.map((day) => (
                            <div key={day.day} className="bg-white rounded-3xl border border-slate-100 overflow-hidden shadow-sm flex flex-col group transition-all hover:shadow-md">
                                <div className="p-6 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center">
                                    <h3 className="text-xl font-extrabold text-slate-900">Day {day.day}</h3>
                                    <span className="text-[10px] font-extrabold uppercase text-green-600 bg-green-100 px-2.5 py-1 rounded-full">{day.theme}</span>
                                </div>

                                <div className="p-6 space-y-6 flex-1">
                                    {day.activities.map((act, aIdx) => (
                                        <div key={aIdx} className="relative pl-6">
                                            <div className="absolute left-0 top-1.5 size-2 rounded-full bg-green-500"></div>
                                            {aIdx !== day.activities.length - 1 && <div className="absolute left-[3px] top-4 w-[2px] h-full bg-slate-100 dark:bg-slate-700"></div>}

                                            <div className="space-y-1">
                                                <div className="flex justify-between items-start capitalize">
                                                    <h4 className="text-sm font-bold text-slate-800">{act.activity}</h4>
                                                    <span className="text-[10px] text-slate-400 font-bold">{act.time}</span>
                                                </div>
                                                <p className="text-xs text-slate-500 leading-relaxed font-medium">
                                                    {act.description}
                                                </p>
                                                {act.smart_insight && (
                                                    <div className="mt-2 text-[10px] bg-slate-50 p-2 rounded italic text-slate-600 border-l-2 border-green-500">
                                                        "{act.smart_insight}"
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>

                                <div className="p-4 bg-slate-50 border-t border-slate-100 mt-auto">
                                    <div className="flex justify-between items-center text-[10px] font-bold text-slate-400 uppercase">
                                        <span>Daily Budget</span>
                                        <span className="text-slate-900">Rs.{day.day_total}</span>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};

export default PlannerApp;

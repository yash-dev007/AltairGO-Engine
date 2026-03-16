import React, { useState, useEffect } from 'react';
import { Users, Map, Clock, ArrowRight, Shield, Globe, Trash2, Eye, RefreshCw, AlertCircle } from 'lucide-react';
import { api } from '../services/api';

const NetworkHub = () => {
    const [users, setUsers] = useState([]);
    const [trips, setTrips] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [selectedTrip, setSelectedTrip] = useState(null);

    const fetchData = async () => {
        setLoading(true);
        try {
            const [usersData, tripsData] = await Promise.all([
                api.getUsers(1, 10),
                api.getTrips(1, 10)
            ]);
            setUsers(usersData.items || []);
            setTrips(tripsData.items || []);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, []);

    const handleDeleteTrip = async (id) => {
        if (!window.confirm("Are you sure you want to delete this trip?")) return;
        try {
            await api.deleteTrip(id);
            setTrips(trips.filter(t => t.id !== id));
        } catch (err) {
            alert("Delete failed: " + err.message);
        }
    };

    const handleDeleteUser = async (id) => {
        if (!window.confirm("Delete user and all their data? This cannot be undone.")) return;
        try {
            await api.deleteUser(id);
            setUsers(users.filter(u => u.id !== id));
        } catch (err) {
            alert("Delete failed: " + err.message);
        }
    };

    const handleInspectTrip = async (id) => {
        try {
            const fullTrip = await api.getTrip(id);
            setSelectedTrip(fullTrip);
        } catch (err) {
            alert("Fetch failed: " + err.message);
        }
    };

    if (loading) return (
        <div className="flex flex-col items-center justify-center p-12 gap-4">
            <RefreshCw className="animate-spin text-green-500" size={32} />
            <p className="text-sm text-slate-500 font-bold uppercase tracking-widest">Hydrating Network Nodes...</p>
        </div>
    );

    return (
        <div className="space-y-8 animate-fade-in">
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-3xl font-black text-slate-800 tracking-tight">Network & Core Data</h2>
                    <p className="text-sm text-slate-500 font-medium">Real-time management of user sessions and itinerary payloads.</p>
                </div>
                <button onClick={fetchData} className="p-3 bg-white border border-slate-200 rounded-2xl shadow-sm hover:bg-slate-50 transition-all active:scale-95">
                    <RefreshCw size={20} className="text-slate-600" />
                </button>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {/* Recent Users */}
                <div className="bg-white rounded-3xl border border-slate-100 shadow-xl shadow-slate-200/50 p-8">
                    <div className="flex items-center gap-4 mb-8">
                        <div className="size-12 bg-blue-50 text-blue-600 rounded-2xl flex items-center justify-center shadow-inner">
                            <Users size={24} />
                        </div>
                        <div>
                            <h3 className="text-xl font-black text-slate-800">Recent Users</h3>
                            <p className="text-xs text-slate-500 font-bold uppercase tracking-wider text-blue-600/60">Active network nodes</p>
                        </div>
                    </div>

                    <div className="space-y-4">
                        {users.map((user) => (
                            <div key={user.id} className="flex items-center justify-between p-4 bg-slate-50/50 rounded-2xl border border-slate-100 group transition-all hover:bg-white hover:shadow-lg hover:border-blue-100">
                                <div className="flex items-center gap-4">
                                    <div className="size-10 bg-white border border-slate-200 rounded-2xl flex items-center justify-center font-bold text-blue-600 shadow-sm group-hover:bg-blue-600 group-hover:text-white group-hover:border-blue-600 transition-all">
                                        {user.name?.[0] || 'U'}
                                    </div>
                                    <div>
                                        <p className="font-bold text-slate-800">{user.name}</p>
                                        <p className="text-[10px] text-slate-400 font-bold">{user.email}</p>
                                    </div>
                                </div>
                                <button
                                    onClick={() => handleDeleteUser(user.id)}
                                    className="p-2 text-slate-300 hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100"
                                    title="Delete User"
                                >
                                    <Trash2 size={18} />
                                </button>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Generated Trips */}
                <div className="bg-white rounded-3xl border border-slate-100 shadow-xl shadow-slate-200/50 p-8">
                    <div className="flex items-center gap-4 mb-8">
                        <div className="size-12 bg-purple-50 text-purple-600 rounded-2xl flex items-center justify-center shadow-inner">
                            <Map size={24} />
                        </div>
                        <div>
                            <h3 className="text-xl font-black text-slate-800">Generated Trips</h3>
                            <p className="text-xs text-slate-500 font-bold uppercase tracking-wider text-purple-600/60">Itinerary Data Assets</p>
                        </div>
                    </div>

                    <div className="space-y-4">
                        {trips.map((trip) => (
                            <div key={trip.id} className="p-4 bg-slate-50/50 rounded-2xl border border-slate-100 group transition-all hover:bg-white hover:shadow-lg hover:border-purple-100">
                                <div className="flex items-center justify-between mb-3">
                                    <h4 className="font-bold text-slate-800 line-clamp-1">{trip.trip_title}</h4>
                                    <div className="flex gap-2">
                                        <button
                                            onClick={() => handleInspectTrip(trip.id)}
                                            className="p-2 text-slate-400 hover:text-blue-500 transition-colors"
                                            title="Inspect JSON"
                                        >
                                            <Eye size={18} />
                                        </button>
                                        <button
                                            onClick={() => handleDeleteTrip(trip.id)}
                                            className="p-2 text-slate-400 hover:text-red-500 transition-colors"
                                            title="Delete Trip"
                                        >
                                            <Trash2 size={18} />
                                        </button>
                                    </div>
                                </div>
                                <div className="flex flex-wrap gap-4 text-[10px] font-bold text-slate-500">
                                    <div className="flex items-center gap-1.5 px-3 py-1 bg-white border border-slate-200 rounded-full shadow-sm">
                                        <Clock size={12} className="text-purple-500" />
                                        {trip.duration} DAYS
                                    </div>
                                    <div className="flex items-center gap-1.5 px-3 py-1 bg-white border border-slate-200 rounded-full shadow-sm uppercase">
                                        <Globe size={12} className="text-blue-500" />
                                        {trip.destination_country}
                                    </div>
                                    <div className="ml-auto text-green-600 font-black flex items-center gap-1">
                                        <span className="text-[10px] text-slate-300">$</span>{trip.budget}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* Inspection Modal */}
            {selectedTrip && (
                <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-md z-50 flex items-center justify-center p-6 animate-in fade-in zoom-in duration-200">
                    <div className="bg-white rounded-[2rem] w-full max-w-5xl max-h-[85vh] overflow-hidden flex flex-col shadow-2xl border border-white/20">
                        <div className="p-8 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
                            <div className="flex items-center gap-4">
                                <div className="size-12 bg-blue-500 text-white rounded-2xl flex items-center justify-center shadow-lg shadow-blue-500/20">
                                    <Database size={24} />
                                </div>
                                <div>
                                    <h3 className="text-2xl font-black text-slate-800">{selectedTrip.trip_title}</h3>
                                    <p className="text-xs text-slate-400 font-bold uppercase tracking-[0.2em]">Full Data Payload Reference</p>
                                </div>
                            </div>
                            <button
                                onClick={() => setSelectedTrip(null)}
                                className="px-6 py-2 bg-slate-100 hover:bg-slate-200 rounded-xl transition-all font-black text-slate-500 text-sm active:scale-95"
                            >
                                CLOSE INSPECTOR
                            </button>
                        </div>
                        <div className="flex-1 overflow-y-auto p-8 bg-slate-950">
                            <pre className="text-green-400 font-mono text-[13px] leading-relaxed custom-scrollbar">
                                {JSON.stringify(selectedTrip.itinerary || selectedTrip, null, 4)}
                            </pre>
                        </div>
                        <div className="p-4 bg-slate-50 border-t border-slate-100 text-center text-[10px] text-slate-400 font-bold tracking-widest uppercase">
                            Admin Security Layer • Read-Only Access
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default NetworkHub;

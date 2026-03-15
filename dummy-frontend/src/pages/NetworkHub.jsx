import React, { useState, useEffect, useCallback } from 'react';
import { Users, MapPin, Globe, Loader2, RefreshCw, AlertCircle, Trash2 } from 'lucide-react';
import { api } from '../services/api';

const NetworkHub = () => {
    const [users, setUsers] = useState([]);
    const [trips, setTrips] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const [usersData, tripsData] = await Promise.all([
                api.getUsers(1, 10),
                api.getTrips(1, 15)
            ]);
            setUsers(usersData.items || []);
            setTrips(tripsData.items || []);
            setError(null);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    if (loading && users.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[50vh] gap-4">
                <Loader2 className="animate-spin text-green-500" size={40} />
                <p className="text-slate-500 font-medium tracking-wide">Fetching network data...</p>
            </div>
        );
    }

    return (
        <div className="space-y-6 max-w-7xl mx-auto w-full">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-3xl font-extrabold text-slate-900 tracking-tight">Network Hub</h2>
                    <p className="text-sm text-slate-500 font-medium">Monitor user acquisition and generated itineraries.</p>
                </div>
                <button onClick={fetchData} className="px-4 py-2 border border-slate-200 bg-white rounded-xl shadow-sm flex items-center gap-2 hover:bg-slate-50 transition-colors text-slate-600 text-sm font-bold">
                    <RefreshCw size={16} /> REFRESH
                </button>
            </div>

            {error && (
                <div className="bg-red-50 border border-red-200 p-4 rounded-xl flex items-center gap-3 text-red-700 text-sm">
                    <AlertCircle size={18} />
                    {error}
                </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {/* Users List */}
                <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden flex flex-col">
                    <div className="p-4 border-b border-slate-100 flex items-center gap-3 bg-slate-50/50">
                        <Users className="text-blue-500" size={18} />
                        <h3 className="font-bold text-slate-800 text-sm">Recent Registered Users</h3>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm">
                            <thead className="bg-slate-50 border-b border-slate-100 text-[10px] font-bold uppercase tracking-wider text-slate-500">
                                <tr>
                                    <th className="px-4 py-3">ID / User</th>
                                    <th className="px-4 py-3">Email</th>
                                    <th className="px-4 py-3">Joined</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100 text-xs">
                                {users.map((user) => (
                                    <tr key={user.id} className="hover:bg-slate-50 transition-colors">
                                        <td className="px-4 py-3">
                                            <span className="font-mono text-slate-400 mr-2">#{user.id}</span>
                                            <span className="font-bold text-slate-800">{user.name}</span>
                                        </td>
                                        <td className="px-4 py-3 text-slate-600">{user.email}</td>
                                        <td className="px-4 py-3 text-slate-500">{new Date(user.created_at).toLocaleDateString()}</td>
                                    </tr>
                                ))}
                                {users.length === 0 && (
                                    <tr>
                                        <td colSpan="3" className="px-4 py-6 text-center text-slate-500">No users found.</td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>

                {/* Trips List */}
                <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden flex flex-col">
                    <div className="p-4 border-b border-slate-100 flex items-center gap-3 bg-slate-50/50">
                        <Globe className="text-green-500" size={18} />
                        <h3 className="font-bold text-slate-800 text-sm">Recently Generated Trips</h3>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm">
                            <thead className="bg-slate-50 border-b border-slate-100 text-[10px] font-bold uppercase tracking-wider text-slate-500">
                                <tr>
                                    <th className="px-4 py-3">Trip Intel</th>
                                    <th className="px-4 py-3">User ID</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100 text-xs">
                                {trips.map((trip) => (
                                    <tr key={trip.id} className="hover:bg-slate-50 transition-colors">
                                        <td className="px-4 py-3">
                                            <div className="font-bold text-slate-800 mb-0.5">{trip.trip_title || 'Untitled Trip'}</div>
                                            <div className="flex gap-2 text-[10px] font-bold text-slate-500 uppercase">
                                                <span>{trip.destination_country}</span>
                                                <span>•</span>
                                                <span>{trip.duration} Days</span>
                                            </div>
                                        </td>
                                        <td className="px-4 py-3 font-mono text-slate-500">
                                            user_{trip.user_id}
                                        </td>
                                    </tr>
                                ))}
                                {trips.length === 0 && (
                                    <tr>
                                        <td colSpan="2" className="px-4 py-6 text-center text-slate-500">No trips generated yet.</td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default NetworkHub;

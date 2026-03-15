import React, { useState, useEffect, useCallback } from 'react';
import {
    MapPin, Search, Edit2, Trash2, CheckCircle2,
    XCircle, Loader2, Save, X, RefreshCw, Filter, ShieldAlert
} from 'lucide-react';
import { api } from '../services/api';

const DataLaboratory = () => {
    const [destinations, setDestinations] = useState([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [editingId, setEditingId] = useState(null);
    const [editForm, setEditForm] = useState({});
    const [actionLoading, setActionLoading] = useState(false);

    const pageSize = 20;

    const fetchDestinations = useCallback(async () => {
        setLoading(true);
        try {
            const data = await api.getDestinations(page, pageSize);
            setDestinations(data.items || []);
            setTotal(data.total || 0);
            setError(null);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, [page]);

    useEffect(() => {
        fetchDestinations();
    }, [fetchDestinations]);

    const handleEditClick = (dest) => {
        setEditingId(dest.id);
        setEditForm({
            name: dest.name || '',
            tag: dest.tag || '',
            status: dest.status || 'active',
            estimated_cost_per_day: dest.estimated_cost_per_day || 0,
            rating: dest.rating || 0
        });
    };

    const handleSave = async (id) => {
        setActionLoading(true);
        try {
            await api.updateDestination(id, editForm);
            setEditingId(null);
            fetchDestinations();
        } catch (err) {
            alert(`Failed to update: ${err.message}`);
        } finally {
            setActionLoading(false);
        }
    };

    const handleDelete = async (id) => {
        if (!window.confirm('Are you sure you want to delete this destination? This cannot be undone.')) return;
        setActionLoading(true);
        try {
            await api.deleteDestination(id);
            fetchDestinations();
        } catch (err) {
            alert(`Failed to delete: ${err.message}`);
        } finally {
            setActionLoading(false);
        }
    };

    if (loading && destinations.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[50vh] gap-4">
                <Loader2 className="animate-spin text-green-500" size={40} />
                <p className="text-slate-500 font-medium tracking-wide">Fetching destinations...</p>
            </div>
        );
    }

    return (
        <div className="space-y-6 max-w-7xl mx-auto w-full">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-3xl font-extrabold text-slate-900 tracking-tight">Data Laboratory</h2>
                    <p className="text-sm text-slate-500 font-medium">Manage destination nodes and engine corpora.</p>
                </div>
                <div className="flex items-center gap-3">
                    <button onClick={fetchDestinations} className="px-4 py-2 border border-slate-200 bg-white rounded-xl shadow-sm flex items-center gap-2 hover:bg-slate-50 transition-colors text-slate-600 text-sm font-bold">
                        <RefreshCw size={16} /> REFRESH
                    </button>
                </div>
            </div>

            {error && (
                <div className="bg-red-50 border border-red-200 p-4 rounded-xl flex items-center gap-3 text-red-700 text-sm">
                    <ShieldAlert size={18} />
                    {error}
                </div>
            )}

            <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden flex flex-col">
                <div className="p-4 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
                    <h3 className="font-bold text-slate-800 text-sm">Destinations ({total})</h3>
                    <div className="flex items-center gap-2">
                        <button disabled={page === 1} onClick={() => setPage(p => p - 1)} className="px-3 py-1 bg-white border border-slate-200 rounded text-xs font-bold disabled:opacity-50">PREV</button>
                        <span className="text-xs font-bold text-slate-500">PAGE {page}</span>
                        <button disabled={destinations.length < pageSize} onClick={() => setPage(p => p + 1)} className="px-3 py-1 bg-white border border-slate-200 rounded text-xs font-bold disabled:opacity-50">NEXT</button>
                    </div>
                </div>

                <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm">
                        <thead>
                            <tr className="bg-slate-50 border-b border-slate-100 text-xs font-bold uppercase tracking-wider text-slate-500">
                                <th className="px-6 py-4">ID / Name</th>
                                <th className="px-6 py-4">Status</th>
                                <th className="px-6 py-4">Tag</th>
                                <th className="px-6 py-4">Cost/Day</th>
                                <th className="px-6 py-4">Rating</th>
                                <th className="px-6 py-4 text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {destinations.map((dest) => {
                                const isEditing = editingId === dest.id;
                                return (
                                    <tr key={dest.id} className="hover:bg-slate-50/50 transition-colors group">
                                        <td className="px-6 py-4">
                                            {isEditing ? (
                                                <input 
                                                    className="w-full border p-1 rounded text-sm" 
                                                    value={editForm.name} 
                                                    onChange={(e) => setEditForm({...editForm, name: e.target.value})}
                                                />
                                            ) : (
                                                <div>
                                                    <span className="text-[10px] text-slate-400 font-mono block">#{dest.id}</span>
                                                    <span className="font-bold text-slate-900">{dest.name}</span>
                                                </div>
                                            )}
                                        </td>
                                        <td className="px-6 py-4">
                                            {isEditing ? (
                                                <select 
                                                    className="border p-1 rounded text-sm"
                                                    value={editForm.status}
                                                    onChange={(e) => setEditForm({...editForm, status: e.target.value})}
                                                >
                                                    <option value="active">Active</option>
                                                    <option value="inactive">Inactive</option>
                                                    <option value="draft">Draft</option>
                                                </select>
                                            ) : (
                                                <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                                                    dest.status === 'active' ? 'bg-green-100 text-green-700' : 
                                                    dest.status === 'draft' ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 text-slate-600'
                                                }`}>
                                                    {dest.status || 'Active'}
                                                </span>
                                            )}
                                        </td>
                                        <td className="px-6 py-4">
                                            {isEditing ? (
                                                <input 
                                                    className="w-full border p-1 rounded text-sm" 
                                                    value={editForm.tag} 
                                                    onChange={(e) => setEditForm({...editForm, tag: e.target.value})}
                                                />
                                            ) : (
                                                <span className="text-slate-600">{dest.tag || '-'}</span>
                                            )}
                                        </td>
                                        <td className="px-6 py-4">
                                            {isEditing ? (
                                                <input 
                                                    type="number"
                                                    className="w-20 border p-1 rounded text-sm" 
                                                    value={editForm.estimated_cost_per_day} 
                                                    onChange={(e) => setEditForm({...editForm, estimated_cost_per_day: parseFloat(e.target.value)})}
                                                />
                                            ) : (
                                                <span className="font-mono text-slate-600">${dest.estimated_cost_per_day || 0}</span>
                                            )}
                                        </td>
                                        <td className="px-6 py-4">
                                            {isEditing ? (
                                                <input 
                                                    type="number" step="0.1" max="5" min="0"
                                                    className="w-16 border p-1 rounded text-sm" 
                                                    value={editForm.rating} 
                                                    onChange={(e) => setEditForm({...editForm, rating: parseFloat(e.target.value)})}
                                                />
                                            ) : (
                                                <span className="text-slate-600">{dest.rating || 0}/5</span>
                                            )}
                                        </td>
                                        <td className="px-6 py-4 text-right">
                                            {isEditing ? (
                                                <div className="flex justify-end gap-2">
                                                    <button onClick={() => setEditingId(null)} disabled={actionLoading} className="p-1 text-slate-400 hover:text-slate-700"><X size={16} /></button>
                                                    <button onClick={() => handleSave(dest.id)} disabled={actionLoading} className="p-1 text-green-600 hover:text-green-800"><Save size={16} /></button>
                                                </div>
                                            ) : (
                                                <div className="flex justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                                    <button onClick={() => handleEditClick(dest)} className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded"><Edit2 size={14} /></button>
                                                    <button onClick={() => handleDelete(dest.id)} className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded"><Trash2 size={14} /></button>
                                                </div>
                                            )}
                                        </td>
                                    </tr>
                                );
                            })}
                            {destinations.length === 0 && !loading && (
                                <tr>
                                    <td colSpan="6" className="px-6 py-8 text-center text-slate-500 text-sm">No destinations found.</td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
};

export default DataLaboratory;

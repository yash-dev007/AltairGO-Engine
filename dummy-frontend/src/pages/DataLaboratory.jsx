import React, { useState, useEffect, useCallback } from 'react';
import {
    Edit2, Trash2, CheckCircle2,
    Loader2, Save, X, RefreshCw, ShieldAlert,
    Plus, ChevronLeft, ChevronRight, Hash, Globe,
    Inbox, Check, XCircle, Clock
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
    const [showAddModal, setShowAddModal] = useState(false);
    const [newDest, setNewDest] = useState({ name: '', tag: '', description: '', estimated_cost_per_day: 0, rating: 0 });

    // Destination Requests state
    const [requests, setRequests] = useState([]);
    const [requestsTotal, setRequestsTotal] = useState(0);
    const [requestsPage, setRequestsPage] = useState(1);
    const [requestsLoading, setRequestsLoading] = useState(false);
    const [requestAction, setRequestAction] = useState(null); // tracks which request id is being acted on

    const pageSize = 15;

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

    const fetchRequests = useCallback(async () => {
        setRequestsLoading(true);
        try {
            const data = await api.getDestinationRequests(requestsPage);
            setRequests(data.items || []);
            setRequestsTotal(data.total || 0);
        } catch {
            // silently fail — requests panel is supplementary
        } finally {
            setRequestsLoading(false);
        }
    }, [requestsPage]);

    useEffect(() => {
        fetchDestinations();
    }, [fetchDestinations]);

    useEffect(() => {
        fetchRequests();
    }, [fetchRequests]);

    const handleApprove = async (id) => {
        setRequestAction(id);
        try {
            await api.approveRequest(id);
            fetchRequests();
            fetchDestinations(); // approved request creates a destination
        } catch (err) {
            alert(`Approve failed: ${err.message}`);
        } finally {
            setRequestAction(null);
        }
    };

    const handleReject = async (id) => {
        setRequestAction(id);
        try {
            await api.rejectRequest(id);
            fetchRequests();
        } catch (err) {
            alert(`Reject failed: ${err.message}`);
        } finally {
            setRequestAction(null);
        }
    };

    const handleEditClick = (dest) => {
        setEditingId(dest.id);
        setEditForm({
            name: dest.name || '',
            tag: dest.tag || '',
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
            alert(`Update sync error: ${err.message}`);
        } finally {
            setActionLoading(false);
        }
    };

    const handleAddDestination = async () => {
        if (!newDest.name) return alert('Name is required');
        setActionLoading(true);
        try {
            await api.createDestination(newDest);
            setShowAddModal(false);
            setNewDest({ name: '', tag: '', description: '', estimated_cost_per_day: 0, rating: 0 });
            fetchDestinations();
        } catch (err) {
            alert(`Creation error: ${err.message}`);
        } finally {
            setActionLoading(false);
        }
    };

    const handleDelete = async (id) => {
        if (!window.confirm('Erase destination node from global registry? This action is irreversible.')) return;
        setActionLoading(true);
        try {
            await api.deleteDestination(id);
            fetchDestinations();
        } catch (err) {
            alert(`Registry deletion error: ${err.message}`);
        } finally {
            setActionLoading(false);
        }
    };

    if (loading && destinations.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
                <RefreshCw className="animate-spin text-green-500" size={40} />
                <p className="text-slate-500 font-black tracking-widest uppercase text-xs">Querying Global Destination Graph...</p>
            </div>
        );
    }

    return (
        <div className="space-y-10 animate-fade-in max-w-7xl mx-auto w-full relative">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-4xl font-black text-slate-900 tracking-tight">Data Laboratory</h2>
                    <p className="text-sm text-slate-500 font-medium tracking-tight">Curation of destination intelligence and pricing parameters.</p>
                </div>
                <div className="flex gap-4">
                    <button onClick={fetchDestinations} className="p-4 bg-white border border-slate-100 rounded-2xl shadow-xl shadow-slate-200/50 hover:bg-slate-50 transition-all active:scale-95">
                        <RefreshCw size={20} className="text-slate-600" />
                    </button>
                    <button onClick={() => setShowAddModal(true)} className="flex items-center gap-2 px-6 py-4 bg-slate-900 text-white rounded-2xl font-black text-xs uppercase tracking-widest shadow-xl shadow-slate-900/20 hover:bg-slate-800 transition-all active:scale-95">
                        <Plus size={16} /> ADD DESTINATION
                    </button>
                </div>
            </div>

            {error && (
                <div className="bg-red-50 border border-red-200 p-6 rounded-[2rem] flex items-center gap-4 text-red-700 font-bold">
                    <ShieldAlert size={24} />
                    <p>Laboratory Protocol Error: {error}</p>
                </div>
            )}

            <div className="bg-white rounded-[2.5rem] border border-slate-100 shadow-2xl shadow-slate-200/60 overflow-hidden flex flex-col">
                <div className="p-6 border-b border-slate-100 flex justify-between items-center bg-slate-50/20">
                    <div className="flex items-center gap-4">
                        <div className="size-10 bg-green-50 text-green-600 rounded-xl flex items-center justify-center font-black text-xs shadow-inner">
                            {total}
                        </div>
                        <h3 className="font-extrabold text-slate-800 text-sm uppercase tracking-wider">Nodes in Registry</h3>
                    </div>
                    <div className="flex items-center gap-3">
                        <button
                            disabled={page === 1}
                            onClick={() => setPage(p => p - 1)}
                            className="p-2 bg-white border border-slate-200 rounded-xl text-slate-400 hover:text-slate-900 disabled:opacity-30 transition-all shadow-sm"
                        >
                            <ChevronLeft size={18} />
                        </button>
                        <span className="text-xs font-black text-slate-500 w-20 text-center uppercase">Page {page}</span>
                        <button
                            disabled={destinations.length < pageSize}
                            onClick={() => setPage(p => p + 1)}
                            className="p-2 bg-white border border-slate-200 rounded-xl text-slate-400 hover:text-slate-900 disabled:opacity-30 transition-all shadow-sm"
                        >
                            <ChevronRight size={18} />
                        </button>
                    </div>
                </div>

                <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm">
                        <thead>
                            <tr className="bg-slate-50/50 border-b border-slate-100 text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">
                                <th className="px-8 py-5">Node Context</th>
                                <th className="px-8 py-5">Slug</th>
                                <th className="px-8 py-5">Tagging</th>
                                <th className="px-8 py-5">Est. Cost/Day</th>
                                <th className="px-8 py-5">Quality</th>
                                <th className="px-8 py-5 text-right">Ops</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {destinations.map((dest) => {
                                const isEditing = editingId === dest.id;
                                return (
                                    <tr key={dest.id} className="hover:bg-slate-50/30 transition-colors group">
                                        <td className="px-8 py-6">
                                            {isEditing ? (
                                                <input
                                                    className="w-full bg-white border border-slate-200 p-3 rounded-xl text-sm font-bold focus:ring-4 focus:ring-green-500/10 outline-none"
                                                    value={editForm.name}
                                                    onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                                                />
                                            ) : (
                                                <div className="flex items-center gap-4">
                                                    <div className="size-10 bg-slate-100 text-slate-400 rounded-xl flex items-center justify-center font-black text-[10px] shadow-inner group-hover:bg-blue-50 group-hover:text-blue-500 transition-colors">
                                                        <Hash size={14} />
                                                    </div>
                                                    <div>
                                                        <p className="font-black text-slate-900 leading-none mb-1.5">{dest.name}</p>
                                                        <p className="text-[10px] font-bold text-slate-400 font-mono tracking-tighter">NODE_REF_{dest.id}</p>
                                                    </div>
                                                </div>
                                            )}
                                        </td>
                                        <td className="px-8 py-6">
                                            <span className="text-[10px] font-mono font-bold text-slate-400 bg-slate-50 px-2 py-1 rounded-md">
                                                {dest.slug || '—'}
                                            </span>
                                        </td>
                                        <td className="px-8 py-6">
                                            {isEditing ? (
                                                <input
                                                    className="w-full bg-white border border-slate-200 p-3 rounded-xl text-sm font-bold outline-none"
                                                    value={editForm.tag}
                                                    onChange={(e) => setEditForm({ ...editForm, tag: e.target.value })}
                                                />
                                            ) : (
                                                <span className="text-[10px] font-black text-slate-500 uppercase bg-slate-100 px-2 py-1 rounded-md">{dest.tag || 'N/A'}</span>
                                            )}
                                        </td>
                                        <td className="px-8 py-6">
                                            {isEditing ? (
                                                <div className="relative">
                                                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 font-bold">$</span>
                                                    <input
                                                        type="number"
                                                        className="w-24 pl-6 pr-3 py-3 bg-white border border-slate-200 rounded-xl text-sm font-bold outline-none"
                                                        value={editForm.estimated_cost_per_day}
                                                        onChange={(e) => setEditForm({ ...editForm, estimated_cost_per_day: parseFloat(e.target.value) })}
                                                    />
                                                </div>
                                            ) : (
                                                <div className="flex items-center gap-1">
                                                    <span className="text-slate-300 font-bold">$</span>
                                                    <span className="font-black text-slate-700">{dest.estimated_cost_per_day || 0}</span>
                                                </div>
                                            )}
                                        </td>
                                        <td className="px-8 py-6">
                                            {isEditing ? (
                                                <input
                                                    type="number" step="0.1" max="5" min="0"
                                                    className="w-16 bg-white border border-slate-200 p-3 rounded-xl text-sm font-bold outline-none"
                                                    value={editForm.rating}
                                                    onChange={(e) => setEditForm({ ...editForm, rating: parseFloat(e.target.value) })}
                                                />
                                            ) : (
                                                <div className="flex items-center gap-2">
                                                    <div className="flex text-amber-400">
                                                        <CheckCircle2 size={12} fill="currentColor" />
                                                    </div>
                                                    <span className="font-black text-slate-900">{dest.rating || 0}/5</span>
                                                </div>
                                            )}
                                        </td>
                                        <td className="px-8 py-6 text-right">
                                            {isEditing ? (
                                                <div className="flex justify-end gap-3">
                                                    <button onClick={() => setEditingId(null)} disabled={actionLoading} className="p-3 bg-slate-100 text-slate-500 hover:bg-slate-200 rounded-xl transition-all"><X size={18} /></button>
                                                    <button onClick={() => handleSave(dest.id)} disabled={actionLoading} className="p-3 bg-green-500 text-white hover:bg-green-600 rounded-xl shadow-lg shadow-green-500/20 transition-all"><Save size={18} /></button>
                                                </div>
                                            ) : (
                                                <div className="flex justify-end gap-2 transition-all opacity-20 group-hover:opacity-100">
                                                    <button onClick={() => handleEditClick(dest)} className="p-3 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-xl transition-all"><Edit2 size={18} /></button>
                                                    <button onClick={() => handleDelete(dest.id)} className="p-3 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-xl transition-all"><Trash2 size={18} /></button>
                                                </div>
                                            )}
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* PENDING DESTINATION REQUESTS */}
            <div className="bg-white rounded-[2.5rem] border border-slate-100 shadow-2xl shadow-slate-200/60 overflow-hidden">
                <div className="p-6 border-b border-slate-100 flex justify-between items-center bg-slate-50/20">
                    <div className="flex items-center gap-4">
                        <div className="size-10 bg-amber-50 text-amber-600 rounded-xl flex items-center justify-center shadow-inner">
                            <Inbox size={18} />
                        </div>
                        <div>
                            <h3 className="font-extrabold text-slate-800 text-sm uppercase tracking-wider">Destination Requests</h3>
                            <p className="text-[10px] text-slate-400 font-bold">User-submitted destinations awaiting review</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-3">
                        <button onClick={fetchRequests} className="p-2 bg-white border border-slate-200 rounded-xl text-slate-400 hover:text-slate-900 transition-all shadow-sm">
                            <RefreshCw size={16} />
                        </button>
                        {requestsTotal > 0 && (
                            <span className="text-[10px] font-black text-amber-600 bg-amber-50 px-3 py-1 rounded-full uppercase">
                                {requestsTotal} total
                            </span>
                        )}
                    </div>
                </div>

                {requestsLoading && requests.length === 0 ? (
                    <div className="p-12 flex items-center justify-center">
                        <Loader2 className="animate-spin text-slate-300" size={24} />
                    </div>
                ) : requests.length === 0 ? (
                    <div className="p-12 text-center space-y-3">
                        <CheckCircle2 className="mx-auto text-green-300" size={32} />
                        <p className="text-sm font-bold text-slate-400">No pending requests — all clear.</p>
                    </div>
                ) : (
                    <>
                        <div className="divide-y divide-slate-100">
                            {requests.map((req) => {
                                const isPending = req.status === 'pending';
                                const isActing = requestAction === req.id;
                                return (
                                    <div key={req.id} className="px-8 py-5 flex items-center gap-6 group hover:bg-slate-50/30 transition-colors">
                                        <div className={`size-10 rounded-xl flex items-center justify-center shrink-0 ${
                                            req.status === 'approved' ? 'bg-green-50 text-green-500' :
                                            req.status === 'rejected' ? 'bg-red-50 text-red-400' :
                                            'bg-amber-50 text-amber-500'
                                        }`}>
                                            {req.status === 'approved' ? <Check size={18} /> :
                                             req.status === 'rejected' ? <XCircle size={16} /> :
                                             <Clock size={16} />}
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-3">
                                                <p className="font-black text-slate-900 text-sm truncate">{req.name}</p>
                                                {req.tag && (
                                                    <span className="text-[9px] font-black text-slate-400 uppercase bg-slate-100 px-2 py-0.5 rounded-md shrink-0">{req.tag}</span>
                                                )}
                                            </div>
                                            <p className="text-[11px] text-slate-400 font-medium truncate mt-0.5">
                                                {req.description || 'No description provided'}
                                                {req.cost ? ` · $${req.cost}/day` : ''}
                                            </p>
                                        </div>
                                        <div className="flex items-center gap-2 shrink-0">
                                            {isPending ? (
                                                <>
                                                    <button
                                                        onClick={() => handleApprove(req.id)}
                                                        disabled={isActing}
                                                        className="flex items-center gap-1.5 px-4 py-2.5 bg-green-500 text-white text-[10px] font-black uppercase tracking-wider rounded-xl shadow-lg shadow-green-500/20 hover:bg-green-600 disabled:opacity-50 transition-all active:scale-95"
                                                    >
                                                        {isActing ? <Loader2 className="animate-spin" size={12} /> : <Check size={12} />}
                                                        Approve
                                                    </button>
                                                    <button
                                                        onClick={() => handleReject(req.id)}
                                                        disabled={isActing}
                                                        className="flex items-center gap-1.5 px-4 py-2.5 bg-white text-red-500 border border-red-200 text-[10px] font-black uppercase tracking-wider rounded-xl hover:bg-red-50 disabled:opacity-50 transition-all active:scale-95"
                                                    >
                                                        {isActing ? <Loader2 className="animate-spin" size={12} /> : <XCircle size={12} />}
                                                        Reject
                                                    </button>
                                                </>
                                            ) : (
                                                <span className={`text-[10px] font-black uppercase tracking-wider px-3 py-1.5 rounded-full ${
                                                    req.status === 'approved' ? 'text-green-600 bg-green-50' : 'text-red-500 bg-red-50'
                                                }`}>
                                                    {req.status}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>

                        {/* Requests pagination */}
                        {requestsTotal > 50 && (
                            <div className="p-4 border-t border-slate-100 flex justify-center items-center gap-3">
                                <button
                                    disabled={requestsPage === 1}
                                    onClick={() => setRequestsPage(p => p - 1)}
                                    className="p-2 bg-white border border-slate-200 rounded-xl text-slate-400 hover:text-slate-900 disabled:opacity-30 transition-all shadow-sm"
                                >
                                    <ChevronLeft size={16} />
                                </button>
                                <span className="text-xs font-black text-slate-500 uppercase">Page {requestsPage}</span>
                                <button
                                    disabled={requests.length < 50}
                                    onClick={() => setRequestsPage(p => p + 1)}
                                    className="p-2 bg-white border border-slate-200 rounded-xl text-slate-400 hover:text-slate-900 disabled:opacity-30 transition-all shadow-sm"
                                >
                                    <ChevronRight size={16} />
                                </button>
                            </div>
                        )}
                    </>
                )}
            </div>

            {/* ADD DESTINATION MODAL */}
            {showAddModal && (
                <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-md z-50 flex items-center justify-center p-6 animate-fade-in">
                    <div className="bg-white w-full max-w-lg rounded-[2.5rem] shadow-2xl overflow-hidden animate-slide-up">
                        <div className="p-8 border-b border-slate-100 flex justify-between items-center bg-slate-50/30">
                            <div>
                                <h3 className="text-xl font-black text-slate-900 tracking-tight">Register New Node</h3>
                                <p className="text-xs text-slate-400 font-bold uppercase tracking-widest mt-1">Destination Registry</p>
                            </div>
                            <button onClick={() => setShowAddModal(false)} className="p-2 hover:bg-slate-100 rounded-full transition-colors">
                                <X size={20} className="text-slate-400" />
                            </button>
                        </div>

                        <div className="p-8 space-y-6">
                            <div className="space-y-4">
                                <div>
                                    <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest block mb-2 px-1">Node Name</label>
                                    <div className="relative">
                                        <Globe className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-300" size={18} />
                                        <input
                                            placeholder="e.g. Tokyo, Japan"
                                            className="w-full pl-12 pr-4 py-4 bg-slate-50 border border-slate-100 rounded-2xl text-sm font-bold focus:bg-white focus:ring-4 focus:ring-slate-900/5 focus:border-slate-900 outline-none transition-all"
                                            value={newDest.name}
                                            onChange={(e) => setNewDest({ ...newDest, name: e.target.value })}
                                        />
                                    </div>
                                </div>
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest block mb-2 px-1">Tag/Region</label>
                                        <input
                                            placeholder="e.g. Asia"
                                            className="w-full px-4 py-4 bg-slate-50 border border-slate-100 rounded-2xl text-sm font-bold focus:bg-white focus:ring-4 focus:ring-slate-900/5 focus:border-slate-900 outline-none transition-all"
                                            value={newDest.tag}
                                            onChange={(e) => setNewDest({ ...newDest, tag: e.target.value })}
                                        />
                                    </div>
                                    <div>
                                        <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest block mb-2 px-1">Short Description</label>
                                        <input
                                            placeholder="e.g. Coastal paradise"
                                            className="w-full px-4 py-4 bg-slate-50 border border-slate-100 rounded-2xl text-sm font-bold focus:bg-white focus:ring-4 focus:ring-slate-900/5 focus:border-slate-900 outline-none transition-all"
                                            value={newDest.description}
                                            onChange={(e) => setNewDest({ ...newDest, description: e.target.value })}
                                        />
                                    </div>
                                </div>
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest block mb-2 px-1">Daily Cost ($)</label>
                                        <input
                                            type="number"
                                            placeholder="0"
                                            className="w-full px-4 py-4 bg-slate-50 border border-slate-100 rounded-2xl text-sm font-bold focus:bg-white focus:border-slate-900 outline-none transition-all"
                                            value={newDest.estimated_cost_per_day}
                                            onChange={(e) => setNewDest({ ...newDest, estimated_cost_per_day: parseFloat(e.target.value) })}
                                        />
                                    </div>
                                    <div>
                                        <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest block mb-2 px-1">Initial Rating (0-5)</label>
                                        <input
                                            type="number" step="0.1" max="5" min="0"
                                            placeholder="0.0"
                                            className="w-full px-4 py-4 bg-slate-50 border border-slate-100 rounded-2xl text-sm font-bold focus:bg-white focus:border-slate-900 outline-none transition-all"
                                            value={newDest.rating}
                                            onChange={(e) => setNewDest({ ...newDest, rating: parseFloat(e.target.value) })}
                                        />
                                    </div>
                                </div>
                            </div>

                            <button
                                onClick={handleAddDestination}
                                disabled={actionLoading || !newDest.name}
                                className="w-full py-5 bg-slate-900 text-white rounded-[1.5rem] font-black text-xs uppercase tracking-[0.2em] shadow-2xl shadow-slate-900/30 hover:bg-slate-800 disabled:opacity-50 transition-all active:scale-[0.98]"
                            >
                                {actionLoading ? <Loader2 className="animate-spin mx-auto" size={20} /> : 'Register Destination Node'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default DataLaboratory;

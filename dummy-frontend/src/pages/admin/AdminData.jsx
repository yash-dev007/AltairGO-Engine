import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Plus, Edit2, Trash2, Check, X, Database, FileText } from 'lucide-react';
import toast from 'react-hot-toast';
import {
  getAdminDestinations, createDestination, updateDestination, deleteDestination,
  getDestinationRequests, approveRequest, rejectRequest,
} from '../../services/api';
import { Button, Badge, Spinner, Modal, EmptyState, Card } from '../../components/ui/index';

const TABS = ['Destinations', 'Destination Requests'];

function DestinationRow({ dest, onEdit, onDelete }) {
  const [deleting, setDeleting] = useState(false);
  const handleDelete = async () => {
    if (!window.confirm(`Delete "${dest.name}"?`)) return;
    setDeleting(true);
    try { await deleteDestination(dest.id); onDelete(); toast.success('Destination deleted'); }
    catch (err) { toast.error(err.message); }
    finally { setDeleting(false); }
  };
  return (
    <tr className="hover:bg-slate-50 transition-colors">
      <td className="px-4 py-3 text-sm font-medium text-slate-800">{dest.name}</td>
      <td className="px-4 py-3 text-xs text-slate-500">{dest.state_name || dest.country_name || '—'}</td>
      <td className="px-4 py-3"><Badge status={dest.budget_category}>{dest.budget_category || '—'}</Badge></td>
      <td className="px-4 py-3 text-xs text-slate-500">{dest.rating?.toFixed(1) || '—'}</td>
      <td className="px-4 py-3 text-xs text-slate-500">{dest.popularity_score || '—'}</td>
      <td className="px-4 py-3 flex items-center gap-1">
        <button onClick={() => onEdit(dest)} className="p-1.5 rounded-lg hover:bg-indigo-50 text-indigo-500 transition-colors"><Edit2 className="w-4 h-4" /></button>
        <button onClick={handleDelete} disabled={deleting} className="p-1.5 rounded-lg hover:bg-red-50 text-red-500 transition-colors">{deleting ? <Spinner size="sm" /> : <Trash2 className="w-4 h-4" />}</button>
      </td>
    </tr>
  );
}

function DestinationModal({ dest, isOpen, onClose, onSave }) {
  const [form, setForm] = useState({ name: '', description: '', budget_category: 'mid', rating: 4.0, lat: '', lng: '', ...dest });
  const [saving, setSaving] = useState(false);
  useEffect(() => { if (dest) setForm({ name: '', description: '', budget_category: 'mid', rating: 4.0, lat: '', lng: '', ...dest }); }, [dest]);
  const handleSave = async () => {
    if (!form.name) { toast.error('Name required'); return; }
    setSaving(true);
    try {
      if (dest?.id) await updateDestination(dest.id, form);
      else await createDestination(form);
      toast.success(dest?.id ? 'Destination updated' : 'Destination created');
      onSave();
      onClose();
    } catch (err) { toast.error(err.message); }
    finally { setSaving(false); }
  };
  return (
    <Modal isOpen={isOpen} onClose={onClose} title={dest?.id ? 'Edit Destination' : 'New Destination'} size="lg">
      <div className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {[['name','Name',true],['description','Description',false],['budget_category','Budget','select'],['rating','Rating','number'],['lat','Latitude','number'],['lng','Longitude','number']].map(([k,label,type]) => (
            type === 'select' ? (
              <div key={k}>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">{label}</label>
                <select value={form[k] || ''} onChange={e => setForm({...form,[k]:e.target.value})}
                  className="w-full px-4 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-400 text-sm">
                  <option value="budget">Budget</option><option value="mid">Standard</option><option value="luxury">Luxury</option>
                </select>
              </div>
            ) : (
              <div key={k}>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">{label}</label>
                <input type={type === true ? 'text' : type} value={form[k] || ''} onChange={e => setForm({...form,[k]:type==='number'?+e.target.value:e.target.value})}
                  className="w-full px-4 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-400 text-sm" />
              </div>
            )
          ))}
        </div>
        <Button onClick={handleSave} loading={saving} className="w-full">Save Destination</Button>
      </div>
    </Modal>
  );
}

function RequestsTab() {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    getDestinationRequests().then((d) => setRequests(d.requests || d.items || d || [])).catch(() => toast.error('Failed to load')).finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);

  const handle = async (id, action) => {
    try {
      if (action === 'approve') await approveRequest(id);
      else await rejectRequest(id);
      toast.success(`Request ${action}d`);
      load();
    } catch (err) { toast.error(err.message); }
  };

  if (loading) return <div className="flex justify-center py-8"><Spinner className="text-indigo-600" /></div>;
  if (requests.length === 0) return <EmptyState icon={FileText} title="No requests" description="No pending destination requests." />;

  return (
    <div className="space-y-3">
      {requests.map((req) => (
        <div key={req.id} className="bg-white rounded-2xl border border-slate-100 shadow-sm p-4 flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h4 className="font-semibold text-slate-800 text-sm">{req.name}</h4>
              <Badge status={req.status}>{req.status}</Badge>
            </div>
            {req.description && <p className="text-xs text-slate-500 line-clamp-2">{req.description}</p>}
            {req.cost && <p className="text-xs text-slate-400 mt-1">Est. cost: ₹{req.cost.toLocaleString('en-IN')}</p>}
          </div>
          {req.status === 'pending' && (
            <div className="flex gap-1 flex-shrink-0">
              <button onClick={() => handle(req.id, 'approve')} className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-green-50 text-green-600 hover:bg-green-100 text-xs font-medium transition-colors">
                <Check className="w-3.5 h-3.5" /> Approve
              </button>
              <button onClick={() => handle(req.id, 'reject')} className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-red-50 text-red-500 hover:bg-red-100 text-xs font-medium transition-colors">
                <X className="w-3.5 h-3.5" /> Reject
              </button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export default function AdminData() {
  const [activeTab, setActiveTab] = useState(0);
  const [destinations, setDestinations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [editDest, setEditDest] = useState(null);
  const [createModal, setCreateModal] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    getAdminDestinations(page)
      .then((d) => setDestinations(d.destinations || d.items || d || []))
      .catch(() => toast.error('Failed to load'))
      .finally(() => setLoading(false));
  }, [page]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Data Management</h1>
          <p className="text-sm text-slate-500 mt-0.5">Manage destinations and requests</p>
        </div>
        {activeTab === 0 && (
          <Button size="sm" onClick={() => setCreateModal(true)}>
            <Plus className="w-4 h-4" /> New Destination
          </Button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-slate-100 p-1 rounded-xl w-fit">
        {TABS.map((t, i) => (
          <button key={i} onClick={() => setActiveTab(i)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${activeTab === i ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-600 hover:text-slate-800'}`}>
            {t}
          </button>
        ))}
      </div>

      {activeTab === 0 && (
        <Card>
          {loading ? (
            <div className="flex justify-center py-8"><Spinner className="text-indigo-600" /></div>
          ) : destinations.length === 0 ? (
            <EmptyState icon={Database} title="No destinations" description="Create your first destination." action={() => setCreateModal(true)} actionLabel="Create Destination" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-100">
                    {['Name', 'Location', 'Budget', 'Rating', 'Score', 'Actions'].map(h => (
                      <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {destinations.map((d) => (
                    <DestinationRow key={d.id} dest={d} onEdit={setEditDest} onDelete={load} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="flex justify-between items-center px-4 py-3 border-t border-slate-100">
            <Button variant="ghost" size="sm" disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous</Button>
            <span className="text-sm text-slate-500">Page {page}</span>
            <Button variant="ghost" size="sm" disabled={destinations.length < 20} onClick={() => setPage(p => p + 1)}>Next</Button>
          </div>
        </Card>
      )}

      {activeTab === 1 && <RequestsTab />}

      <DestinationModal isOpen={createModal} onClose={() => setCreateModal(false)} onSave={load} />
      {editDest && <DestinationModal dest={editDest} isOpen={!!editDest} onClose={() => setEditDest(null)} onSave={load} />}
    </div>
  );
}

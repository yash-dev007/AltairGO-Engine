import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { User, Save, AlertTriangle, MapPin, Wallet, Users } from 'lucide-react';
import toast from 'react-hot-toast';
import { getProfile, updateProfile, deleteAccount, getUserTrips } from '../services/api';
import { Button, Input, Select, Card, Modal, Spinner } from '../components/ui/index';
import { useAuth } from '../contexts/AuthContext';

const DIETARY = ['none', 'vegetarian', 'vegan', 'jain', 'halal', 'gluten-free'];
const TRAVELER_TYPES = ['solo', 'couple', 'family', 'group', 'senior'];
const BUDGET_CATS = ['budget', 'mid', 'luxury'];

export default function Profile() {
  const { user, logout } = useAuth();
  const [profile, setProfile] = useState(null);
  const [form, setForm] = useState({ name: '', default_budget_category: 'mid', default_traveler_type: 'solo', default_dietary: 'none', accessibility: false });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [tripCount, setTripCount] = useState(0);
  const [deleteModal, setDeleteModal] = useState(false);
  const [deletePw, setDeletePw] = useState('');
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    Promise.all([
      getProfile().catch(() => null),
      getUserTrips(1).catch(() => null),
    ]).then(([prof, trips]) => {
      if (prof) {
        setProfile(prof);
        setForm({
          name: prof.name || user?.name || '',
          default_budget_category: prof.preferences?.default_budget_category || 'mid',
          default_traveler_type: prof.preferences?.default_traveler_type || 'solo',
          default_dietary: prof.preferences?.dietary_restrictions || 'none',
          accessibility: prof.preferences?.accessibility || false,
        });
      } else if (user) {
        setForm(f => ({ ...f, name: user.name || '' }));
      }
      setTripCount(trips?.total || trips?.trips?.length || 0);
    }).finally(() => setLoading(false));
  }, [user]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateProfile({
        name: form.name,
        preferences: {
          default_budget_category: form.default_budget_category,
          default_traveler_type: form.default_traveler_type,
          dietary_restrictions: form.default_dietary,
          accessibility: form.accessibility,
        },
      });
      toast.success('Profile updated');
    } catch (err) { toast.error(err.message || 'Update failed'); }
    finally { setSaving(false); }
  };

  const handleDelete = async () => {
    if (!deletePw) { toast.error('Enter your password'); return; }
    setDeleting(true);
    try {
      await deleteAccount(deletePw);
      toast.success('Account deleted');
      logout();
    } catch (err) { toast.error(err.message || 'Deletion failed'); }
    finally { setDeleting(false); }
  };

  if (loading) return <div className="flex justify-center py-16"><Spinner size="lg" className="text-indigo-600" /></div>;

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-10">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900 mb-1">Profile</h1>
        <p className="text-slate-500 text-sm">Manage your account and travel preferences.</p>
      </div>

      {/* Avatar + Stats */}
      <Card className="p-6 mb-6">
        <div className="flex items-center gap-5">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-400 to-violet-500 flex items-center justify-center text-white text-2xl font-bold">
            {form.name?.[0]?.toUpperCase() || 'U'}
          </div>
          <div>
            <h2 className="text-xl font-bold text-slate-900">{form.name || user?.name}</h2>
            <p className="text-slate-500 text-sm">{user?.email || profile?.email}</p>
          </div>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mt-5 pt-5 border-t border-slate-100">
          <div className="text-center">
            <p className="text-2xl font-bold text-indigo-600">{tripCount}</p>
            <p className="text-xs text-slate-500">Trips Planned</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-indigo-600">—</p>
            <p className="text-xs text-slate-500">Destinations Visited</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-indigo-600">—</p>
            <p className="text-xs text-slate-500">Bookings Made</p>
          </div>
        </div>
      </Card>

      {/* Edit form */}
      <Card className="p-6 mb-6 space-y-5">
        <h3 className="font-semibold text-slate-800 flex items-center gap-2">
          <User className="w-4 h-4 text-indigo-500" /> Personal Details
        </h3>
        <Input label="Full Name" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />

        <div>
          <h3 className="font-semibold text-slate-800 mb-4 flex items-center gap-2">
            <MapPin className="w-4 h-4 text-indigo-500" /> Travel Preferences
          </h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Default Budget</label>
              <div className="flex gap-2">
                {BUDGET_CATS.map(b => (
                  <button key={b} onClick={() => setForm({ ...form, default_budget_category: b })}
                    className={`flex-1 py-2 rounded-xl text-sm font-medium border capitalize transition-colors ${form.default_budget_category === b ? 'bg-indigo-600 text-white border-indigo-600' : 'border-slate-200 text-slate-600 hover:border-indigo-200'}`}>
                    {b}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Default Traveler Type</label>
              <div className="flex flex-wrap gap-2">
                {TRAVELER_TYPES.map(t => (
                  <button key={t} onClick={() => setForm({ ...form, default_traveler_type: t })}
                    className={`px-3 py-1.5 rounded-xl text-sm font-medium border capitalize transition-colors ${form.default_traveler_type === t ? 'bg-indigo-600 text-white border-indigo-600' : 'border-slate-200 text-slate-600 hover:border-indigo-200'}`}>
                    {t}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Dietary Preference</label>
              <div className="flex flex-wrap gap-2">
                {DIETARY.map(d => (
                  <button key={d} onClick={() => setForm({ ...form, default_dietary: d })}
                    className={`px-3 py-1.5 rounded-xl text-sm font-medium border capitalize transition-colors ${form.default_dietary === d ? 'bg-indigo-600 text-white border-indigo-600' : 'border-slate-200 text-slate-600 hover:border-indigo-200'}`}>
                    {d}
                  </button>
                ))}
              </div>
            </div>
            <label className="flex items-center gap-3 cursor-pointer">
              <input type="checkbox" checked={form.accessibility} onChange={e => setForm({ ...form, accessibility: e.target.checked })} className="accent-indigo-600 w-4 h-4" />
              <span className="text-sm text-slate-700">I have accessibility needs</span>
            </label>
          </div>
        </div>
        <Button onClick={handleSave} loading={saving}>
          <Save className="w-4 h-4" /> Save Changes
        </Button>
      </Card>

      {/* Danger zone */}
      <Card className="p-6 border-red-100 bg-red-50">
        <h3 className="font-semibold text-red-700 mb-2 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" /> Danger Zone
        </h3>
        <p className="text-sm text-red-600 mb-4">Permanently delete your account and all associated data. This cannot be undone.</p>
        <Button variant="danger" size="sm" onClick={() => setDeleteModal(true)}>Delete Account</Button>
      </Card>

      <Modal isOpen={deleteModal} onClose={() => setDeleteModal(false)} title="Delete Account">
        <div className="space-y-4">
          <div className="bg-red-50 p-4 rounded-xl border border-red-100">
            <p className="text-sm text-red-700 font-medium">This will permanently delete your account, trips, and all data.</p>
          </div>
          <Input label="Confirm Password" type="password" value={deletePw} onChange={e => setDeletePw(e.target.value)} placeholder="Enter your password to confirm" />
          <Button variant="danger" onClick={handleDelete} loading={deleting} className="w-full">
            Yes, Delete My Account
          </Button>
        </div>
      </Modal>
    </div>
  );
}

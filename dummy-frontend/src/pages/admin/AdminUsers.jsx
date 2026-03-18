import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Users, Map, Search, Calendar } from 'lucide-react';
import toast from 'react-hot-toast';
import { getAdminUsers, getAdminTrips } from '../../services/api';
import { Button, Badge, Spinner, EmptyState, Card } from '../../components/ui/index';

const TABS = ['Users', 'Recent Trips'];
const formatINR = (n) => `₹${Number(n || 0).toLocaleString('en-IN')}`;

function formatDate(d) {
  if (!d) return '—';
  return new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(d));
}

function UsersTable({ users }) {
  if (!users.length) return <EmptyState icon={Users} title="No users found" />;
  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-slate-100">
            {['Name', 'Email', 'Joined', 'Trips'].map(h => (
              <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {users.map((u) => (
            <tr key={u.id} className="hover:bg-slate-50 transition-colors">
              <td className="px-4 py-3 text-sm font-medium text-slate-800">{u.name || '—'}</td>
              <td className="px-4 py-3 text-sm text-slate-500">{u.email}</td>
              <td className="px-4 py-3 text-xs text-slate-400">{formatDate(u.created_at)}</td>
              <td className="px-4 py-3 text-sm text-slate-600">{u.trip_count || 0}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TripsTable({ trips }) {
  if (!trips.length) return <EmptyState icon={Map} title="No trips found" />;
  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-slate-100">
            {['Title', 'User', 'Budget', 'Duration', 'Quality', 'Date'].map(h => (
              <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {trips.map((t) => (
            <tr key={t.id} className="hover:bg-slate-50 transition-colors">
              <td className="px-4 py-3 text-sm font-medium text-slate-800 max-w-[200px]">
                <p className="truncate">{t.trip_title || '—'}</p>
              </td>
              <td className="px-4 py-3 text-xs text-slate-500">{t.user_email || t.user_id || '—'}</td>
              <td className="px-4 py-3 text-xs text-slate-600">{formatINR(t.budget)}</td>
              <td className="px-4 py-3 text-xs text-slate-500">{t.duration ? `${t.duration}d` : '—'}</td>
              <td className="px-4 py-3">
                {t.quality_score ? (
                  <span className={`text-xs font-bold ${t.quality_score >= 8 ? 'text-green-600' : t.quality_score >= 6 ? 'text-amber-600' : 'text-red-500'}`}>
                    {t.quality_score.toFixed(1)}
                  </span>
                ) : '—'}
              </td>
              <td className="px-4 py-3 text-xs text-slate-400">{formatDate(t.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function AdminUsers() {
  const [activeTab, setActiveTab] = useState(0);
  const [users, setUsers] = useState([]);
  const [trips, setTrips] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);

  const load = useCallback(() => {
    setLoading(true);
    const fetcher = activeTab === 0 ? getAdminUsers(page) : getAdminTrips(page);
    fetcher
      .then((d) => {
        if (activeTab === 0) setUsers(d.users || d.items || d || []);
        else setTrips(d.trips || d.items || d || []);
      })
      .catch(() => toast.error('Failed to load'))
      .finally(() => setLoading(false));
  }, [activeTab, page]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setPage(1); }, [activeTab]);

  const items = activeTab === 0 ? users : trips;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Users & Trips</h1>
        <p className="text-sm text-slate-500 mt-0.5">Manage registered users and generated trips</p>
      </div>

      <div className="flex gap-1 bg-slate-100 p-1 rounded-xl w-fit">
        {TABS.map((t, i) => (
          <button key={i} onClick={() => setActiveTab(i)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${activeTab === i ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-600 hover:text-slate-800'}`}>
            {t}
          </button>
        ))}
      </div>

      <Card>
        {loading ? (
          <div className="flex justify-center py-8"><Spinner className="text-indigo-600" /></div>
        ) : activeTab === 0 ? (
          <UsersTable users={users} />
        ) : (
          <TripsTable trips={trips} />
        )}
        <div className="flex justify-between items-center px-4 py-3 border-t border-slate-100">
          <Button variant="ghost" size="sm" disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous</Button>
          <span className="text-sm text-slate-500">Page {page} — {items.length} items</span>
          <Button variant="ghost" size="sm" disabled={items.length < 20} onClick={() => setPage(p => p + 1)}>Next</Button>
        </div>
      </Card>
    </div>
  );
}

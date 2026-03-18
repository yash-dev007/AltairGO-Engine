import { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Plus, Trash2, TrendingUp, TrendingDown } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import toast from 'react-hot-toast';
import { getExpenses, addExpense, deleteExpense, getTrip } from '../services/api';
import { Button, Spinner, EmptyState, Modal, Card } from '../components/ui/index';

const formatINR = (n) => `₹${Number(n || 0).toLocaleString('en-IN')}`;
const CATEGORIES = ['accommodation', 'food', 'transport', 'activities', 'misc'];

export default function Expenses() {
  const { id: tripId } = useParams();
  const [expenses, setExpenses] = useState(null);
  const [trip, setTrip] = useState(null);
  const [loading, setLoading] = useState(true);
  const [addModal, setAddModal] = useState(false);
  const [form, setForm] = useState({ category: 'food', amount: '', description: '' });

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      getExpenses(tripId).catch(() => null),
      getTrip(tripId).catch(() => null),
    ]).then(([exp, tr]) => {
      setExpenses(exp);
      setTrip(tr?.trip || tr);
    }).finally(() => setLoading(false));
  }, [tripId]);

  useEffect(() => { load(); }, [load]);

  const handleAdd = async () => {
    if (!form.amount || form.amount <= 0) { toast.error('Enter a valid amount'); return; }
    try {
      await addExpense(tripId, { ...form, amount: Number(form.amount) });
      toast.success('Expense logged');
      setAddModal(false);
      setForm({ category: 'food', amount: '', description: '' });
      load();
    } catch (err) { toast.error(err.message); }
  };

  const handleDelete = async (id) => {
    try {
      await deleteExpense(id);
      toast.success('Expense deleted');
      load();
    } catch (err) { toast.error(err.message); }
  };

  const expList = expenses?.expenses || expenses?.items || [];
  const planned = expenses?.planned_breakdown || (trip?.itinerary_json?.cost_breakdown) || {};
  const totalActual = expList.reduce((s, e) => s + (e.amount || 0), 0);
  const totalBudget = trip?.itinerary_json?.total_cost || trip?.budget || 0;

  const chartData = CATEGORIES.map((cat) => ({
    category: cat.charAt(0).toUpperCase() + cat.slice(1),
    planned: planned[cat] || 0,
    actual: expList.filter(e => e.category === cat).reduce((s, e) => s + e.amount, 0),
  })).filter(d => d.planned > 0 || d.actual > 0);

  if (loading) return <div className="flex justify-center py-16"><Spinner size="lg" className="text-indigo-600" /></div>;

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <div className="flex items-center gap-3 mb-6">
        <Link to={`/trip/${tripId}`} className="p-2 rounded-xl hover:bg-slate-100 transition-colors">
          <ArrowLeft className="w-5 h-5 text-slate-600" />
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-slate-900">Expense Tracker</h1>
          <p className="text-sm text-slate-500">Budget vs actual spending</p>
        </div>
        <Button size="sm" onClick={() => setAddModal(true)}>
          <Plus className="w-4 h-4" /> Log Expense
        </Button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <Card className="p-5">
          <p className="text-xs text-slate-500 mb-1">Total Budget</p>
          <p className="text-2xl font-bold text-slate-800">{formatINR(totalBudget)}</p>
        </Card>
        <Card className="p-5">
          <p className="text-xs text-slate-500 mb-1">Total Spent</p>
          <p className="text-2xl font-bold text-slate-800">{formatINR(totalActual)}</p>
        </Card>
        <Card className={`p-5 ${totalActual > totalBudget ? 'bg-red-50 border-red-100' : 'bg-green-50 border-green-100'}`}>
          <p className="text-xs text-slate-500 mb-1">{totalActual > totalBudget ? 'Over Budget' : 'Remaining'}</p>
          <div className="flex items-center gap-2">
            <p className={`text-2xl font-bold ${totalActual > totalBudget ? 'text-red-600' : 'text-green-600'}`}>
              {formatINR(Math.abs(totalBudget - totalActual))}
            </p>
            {totalActual > totalBudget
              ? <TrendingUp className="w-5 h-5 text-red-500" />
              : <TrendingDown className="w-5 h-5 text-green-500" />}
          </div>
        </Card>
      </div>

      {/* Chart */}
      {chartData.length > 0 && (
        <Card className="p-5 mb-6">
          <h3 className="font-semibold text-slate-700 mb-4 text-sm">Budget vs Actual by Category</h3>
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 0, right: 0, bottom: 0, left: -15 }}>
                <XAxis dataKey="category" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => formatINR(v)} />
                <Legend />
                <Bar dataKey="planned" fill="#e0e7ff" name="Planned" radius={[4,4,0,0]} />
                <Bar dataKey="actual" fill="#6366f1" name="Actual" radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      )}

      {/* Expense list */}
      {expList.length === 0 ? (
        <EmptyState
          icon={Plus}
          title="No expenses logged yet"
          description="Track your actual spending against the planned budget."
          action={() => setAddModal(true)}
          actionLabel="Log First Expense"
        />
      ) : (
        <Card className="overflow-hidden">
          <div className="divide-y divide-slate-100">
            {expList.map((e) => (
              <div key={e.id} className="flex items-center justify-between px-5 py-4 hover:bg-slate-50 transition-colors">
                <div>
                  <p className="font-medium text-sm text-slate-800">{e.description || e.category}</p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-xs text-slate-400 capitalize">{e.category}</span>
                    {e.created_at && <span className="text-xs text-slate-300">{new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short' }).format(new Date(e.created_at))}</span>}
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="font-bold text-slate-800">{formatINR(e.amount)}</span>
                  <button onClick={() => handleDelete(e.id)} className="p-1.5 text-slate-400 hover:text-red-500 transition-colors">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      <Modal isOpen={addModal} onClose={() => setAddModal(false)} title="Log Expense">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Category</label>
            <select value={form.category} onChange={e => setForm({...form, category: e.target.value})}
              className="w-full px-4 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-400 text-sm">
              {CATEGORIES.map(c => <option key={c} value={c} className="capitalize">{c.charAt(0).toUpperCase() + c.slice(1)}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Amount (₹)</label>
            <div className="relative">
              <span className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 font-medium">₹</span>
              <input type="number" min="1" value={form.amount} onChange={e => setForm({...form, amount: e.target.value})}
                placeholder="0"
                className="w-full pl-8 pr-4 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-400 text-sm" />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Description</label>
            <input type="text" value={form.description} onChange={e => setForm({...form, description: e.target.value})}
              placeholder="What was it for?"
              className="w-full px-4 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-400 text-sm" />
          </div>
          <Button onClick={handleAdd} className="w-full">Save Expense</Button>
        </div>
      </Modal>
    </div>
  );
}

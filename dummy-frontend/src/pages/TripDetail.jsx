import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ChevronDown, ChevronUp, Clock, DollarSign, MapPin, Share2, CheckSquare,
  Hotel, Camera, Star, ArrowLeft, BookOpen, Wallet, ClipboardList,
  AlertTriangle, StickyNote, Plus, Trash2, RefreshCw, Check, X,
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import toast from 'react-hot-toast';
import {
  getTrip, shareTrip,
  getBookings, approveBooking, rejectBooking, cancelBooking, executeAllBookings, addCustomBooking,
  getExpenses, addExpense, deleteExpense,
  getTripReadiness, saveTripNotes,
  changeHotel, getHotelOptions, removeActivity,
} from '../services/api';
import { Badge, Button, Card, Spinner, Modal, EmptyState, ProgressBar, Textarea } from '../components/ui/index';

const formatINR = (n) => `₹${Number(n || 0).toLocaleString('en-IN')}`;
const TABS = ['Itinerary', 'Bookings', 'Expenses', 'Readiness', 'Notes'];

// ── Activity Card ──────────────────────────────────────────────────────────
function ActivityCard({ activity, dayNum, tripId, onRefresh }) {
  const isMeal = activity.type === 'meal' || activity.name?.toLowerCase().includes('lunch') || activity.name?.toLowerCase().includes('breakfast') || activity.name?.toLowerCase().includes('dinner');
  const [removing, setRemoving] = useState(false);

  const handleRemove = async () => {
    if (!window.confirm(`Remove "${activity.name}"?`)) return;
    setRemoving(true);
    try {
      await removeActivity(tripId, dayNum, activity.name);
      toast.success('Activity removed');
      onRefresh?.();
    } catch (err) { toast.error(err.message); }
    finally { setRemoving(false); }
  };

  return (
    <div className={`flex gap-4 p-4 rounded-xl border transition-colors ${isMeal ? 'bg-amber-50 border-amber-100' : 'bg-slate-50 border-slate-100 hover:border-indigo-100'}`}>
      <div className="flex flex-col items-center gap-1 flex-shrink-0 min-w-[4rem]">
        <span className="text-xs font-bold text-slate-600 bg-white border border-slate-200 px-2 py-1 rounded-lg whitespace-nowrap">{activity.time || '—'}</span>
        {activity.end_time && <span className="text-xs text-slate-400">{activity.end_time}</span>}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2 mb-1">
          <h4 className={`font-semibold text-sm ${isMeal ? 'text-amber-800' : 'text-slate-800'}`}>{activity.name}</h4>
          <div className="flex items-center gap-1 flex-shrink-0">
            {activity.is_photo_spot && <Camera className="w-3.5 h-3.5 text-indigo-400" title="Photo spot" />}
            {activity.cost > 0 && <span className="text-xs font-medium text-slate-600 bg-white border border-slate-200 px-1.5 py-0.5 rounded-lg">{formatINR(activity.cost)}</span>}
          </div>
        </div>
        {activity.description && <p className="text-xs text-slate-500 leading-relaxed mb-2 line-clamp-2">{activity.description}</p>}
        <div className="flex flex-wrap gap-2">
          {activity.avg_visit_duration_hours && <span className="text-xs text-slate-400 flex items-center gap-1"><Clock className="w-3 h-3" />{activity.avg_visit_duration_hours}h</span>}
          {activity.difficulty_level && activity.difficulty_level !== 'easy' && <Badge status={activity.difficulty_level === 'strenuous' ? 'failed' : 'pending'} className="text-xs">{activity.difficulty_level}</Badge>}
          {activity.dress_code && <span className="text-xs text-slate-400">{activity.dress_code}</span>}
        </div>
      </div>
      {tripId && (
        <button onClick={handleRemove} disabled={removing} className="flex-shrink-0 p-1.5 text-slate-400 hover:text-red-500 transition-colors">
          {removing ? <Spinner size="sm" /> : <Trash2 className="w-3.5 h-3.5" />}
        </button>
      )}
    </div>
  );
}

// ── Day Card ───────────────────────────────────────────────────────────────
function DayCard({ day, index, tripId, onRefresh }) {
  const [expanded, setExpanded] = useState(index === 0);
  const pacingColors = { intense: 'bg-red-100 text-red-700', moderate: 'bg-amber-100 text-amber-700', relaxed: 'bg-green-100 text-green-700' };
  const activities = day.activities || [];

  return (
    <Card className="overflow-hidden">
      <button onClick={() => setExpanded(!expanded)} className="w-full flex items-center justify-between p-5 text-left hover:bg-slate-50 transition-colors">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-white font-bold text-sm flex-shrink-0">
            {index + 1}
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-bold text-slate-800">Day {index + 1}</span>
              {day.location && <span className="text-sm text-slate-500 flex items-center gap-1"><MapPin className="w-3 h-3" />{day.location}</span>}
              {day.theme && <span className="text-xs px-2 py-0.5 rounded-full bg-violet-100 text-violet-700 font-medium">{day.theme}</span>}
            </div>
            <div className="flex items-center gap-2 mt-0.5">
              {day.pacing_level && (
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${pacingColors[day.pacing_level] || pacingColors.moderate}`}>
                  {day.pacing_level}
                </span>
              )}
              <span className="text-xs text-slate-400">{activities.length} activities</span>
              {day.day_total && <span className="text-xs text-slate-500">{formatINR(day.day_total)}</span>}
            </div>
          </div>
        </div>
        {expanded ? <ChevronUp className="w-5 h-5 text-slate-400 flex-shrink-0" /> : <ChevronDown className="w-5 h-5 text-slate-400 flex-shrink-0" />}
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }} className="overflow-hidden">
            <div className="border-t border-slate-100 p-4 space-y-3">
              {activities.map((act, i) => (
                <ActivityCard key={i} activity={act} dayNum={index + 1} tripId={tripId} onRefresh={onRefresh} />
              ))}
              {day.accommodation && (
                <div className="flex items-center gap-3 p-3 bg-sky-50 rounded-xl border border-sky-100">
                  <Hotel className="w-4 h-4 text-sky-500 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-sky-800">{day.accommodation}</p>
                    <p className="text-xs text-sky-600">Accommodation</p>
                  </div>
                </div>
              )}
              {day.daily_transport_guide && (
                <div className="p-3 bg-indigo-50 rounded-xl border border-indigo-100 text-xs text-indigo-700">
                  <span className="font-semibold">Transport: </span>{day.daily_transport_guide.recommendation || day.daily_transport_guide}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  );
}

// ── Bookings Tab ───────────────────────────────────────────────────────────
function BookingsTab({ tripId }) {
  const [bookings, setBookings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [executing, setExecuting] = useState(false);
  const [customModal, setCustomModal] = useState(false);
  const [customForm, setCustomForm] = useState({ booking_type: 'hotel', description: '', cost: 0 });

  const load = useCallback(() => {
    setLoading(true);
    getBookings(tripId).then(setBookings).catch(() => toast.error('Failed to load bookings')).finally(() => setLoading(false));
  }, [tripId]);
  useEffect(() => { load(); }, [load]);

  const handleAction = async (action, id) => {
    try {
      if (action === 'approve') await approveBooking(id);
      else if (action === 'reject') await rejectBooking(id);
      else if (action === 'cancel') await cancelBooking(id);
      toast.success(`Booking ${action}d`);
      load();
    } catch (err) { toast.error(err.message); }
  };

  const handleExecuteAll = async () => {
    setExecuting(true);
    try {
      const result = await executeAllBookings(tripId);
      toast.success(`Executed ${result.executed_count || 'all'} bookings!`);
      load();
    } catch (err) { toast.error(err.message || 'Execute failed'); }
    finally { setExecuting(false); }
  };

  const handleAddCustom = async () => {
    try {
      await addCustomBooking(tripId, customForm);
      toast.success('Custom booking added');
      setCustomModal(false);
      load();
    } catch (err) { toast.error(err.message); }
  };

  if (loading) return <div className="flex justify-center py-8"><Spinner className="text-indigo-600" /></div>;

  const allBookings = bookings?.bookings || bookings?.all_bookings || [];
  const grouped = allBookings.reduce((acc, b) => {
    const type = b.booking_type || 'other';
    if (!acc[type]) acc[type] = [];
    acc[type].push(b);
    return acc;
  }, {});

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3 justify-between">
        <Button onClick={handleExecuteAll} loading={executing} size="sm">
          <Check className="w-4 h-4" /> Execute All Approved
        </Button>
        <Button variant="secondary" size="sm" onClick={() => setCustomModal(true)}>
          <Plus className="w-4 h-4" /> Add Custom Booking
        </Button>
      </div>

      {allBookings.length === 0 ? (
        <EmptyState icon={BookOpen} title="No bookings yet" description="Bookings will appear here once your trip plan is ready." />
      ) : (
        Object.entries(grouped).map(([type, items]) => (
          <div key={type}>
            <h3 className="text-sm font-semibold text-slate-700 capitalize mb-2">{type.replace(/_/g, ' ')}</h3>
            <div className="space-y-2">
              {items.map((b) => (
                <div key={b.id} className="flex items-start justify-between gap-3 p-4 bg-slate-50 rounded-xl border border-slate-100">
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm text-slate-800 truncate">{b.description || b.booking_reference || 'Booking'}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <Badge status={b.status}>{b.status}</Badge>
                      {b.cost && <span className="text-xs text-slate-500">{formatINR(b.cost)}</span>}
                    </div>
                  </div>
                  <div className="flex gap-1 flex-shrink-0">
                    {b.status === 'pending' && (
                      <>
                        <button onClick={() => handleAction('approve', b.id)} className="p-1.5 rounded-lg hover:bg-green-100 text-green-600 transition-colors"><Check className="w-4 h-4" /></button>
                        <button onClick={() => handleAction('reject', b.id)} className="p-1.5 rounded-lg hover:bg-red-100 text-red-500 transition-colors"><X className="w-4 h-4" /></button>
                      </>
                    )}
                    {['approved', 'booked'].includes(b.status) && (
                      <button onClick={() => handleAction('cancel', b.id)} className="p-1.5 rounded-lg hover:bg-red-100 text-red-500 transition-colors text-xs font-medium">Cancel</button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))
      )}

      <Modal isOpen={customModal} onClose={() => setCustomModal(false)} title="Add Custom Booking">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Type</label>
            <select value={customForm.booking_type} onChange={e => setCustomForm({...customForm, booking_type: e.target.value})}
              className="w-full px-4 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-400 text-sm">
              {['hotel','flight','activity','restaurant','transport','other'].map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Description</label>
            <input type="text" value={customForm.description} onChange={e => setCustomForm({...customForm, description: e.target.value})}
              className="w-full px-4 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-400 text-sm" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Cost (₹)</label>
            <input type="number" value={customForm.cost} onChange={e => setCustomForm({...customForm, cost: +e.target.value})}
              className="w-full px-4 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-400 text-sm" />
          </div>
          <Button onClick={handleAddCustom} className="w-full">Add Booking</Button>
        </div>
      </Modal>
    </div>
  );
}

// ── Expenses Tab ───────────────────────────────────────────────────────────
function ExpensesTab({ tripId, budget }) {
  const [expenses, setExpenses] = useState(null);
  const [loading, setLoading] = useState(true);
  const [addModal, setAddModal] = useState(false);
  const [addForm, setAddForm] = useState({ category: 'accommodation', amount: 0, description: '' });

  const load = useCallback(() => {
    setLoading(true);
    getExpenses(tripId).then(setExpenses).catch(() => {}).finally(() => setLoading(false));
  }, [tripId]);
  useEffect(() => { load(); }, [load]);

  const handleAdd = async () => {
    try {
      await addExpense(tripId, addForm);
      toast.success('Expense logged');
      setAddModal(false);
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

  if (loading) return <div className="flex justify-center py-8"><Spinner className="text-indigo-600" /></div>;

  const expList = expenses?.expenses || expenses?.items || [];
  const totalActual = expList.reduce((s, e) => s + (e.amount || 0), 0);
  const planned = expenses?.planned_breakdown || {};
  const chartData = Object.entries(planned).map(([k, v]) => ({
    category: k.replace(/_/g, ' '),
    planned: v,
    actual: expList.filter(e => e.category === k).reduce((s, e) => s + e.amount, 0),
  }));

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-slate-500">Total Spent</p>
          <p className="text-2xl font-bold text-slate-900">{formatINR(totalActual)}</p>
          {budget && (
            <p className={`text-xs mt-0.5 ${totalActual > budget ? 'text-red-500' : 'text-green-600'}`}>
              {totalActual > budget ? `${formatINR(totalActual - budget)} over budget` : `${formatINR(budget - totalActual)} remaining`}
            </p>
          )}
        </div>
        <Button size="sm" onClick={() => setAddModal(true)}>
          <Plus className="w-4 h-4" /> Log Expense
        </Button>
      </div>

      {chartData.length > 0 && (
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 0, right: 0, bottom: 0, left: -10 }}>
              <XAxis dataKey="category" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip formatter={(v) => formatINR(v)} />
              <Legend />
              <Bar dataKey="planned" fill="#e0e7ff" name="Planned" radius={[4,4,0,0]} />
              <Bar dataKey="actual" fill="#6366f1" name="Actual" radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {expList.length === 0 ? (
        <EmptyState icon={Wallet} title="No expenses logged" description="Track your actual spending against the planned budget." />
      ) : (
        <div className="space-y-2">
          {expList.map((e) => (
            <div key={e.id} className="flex items-center justify-between p-3 bg-slate-50 rounded-xl border border-slate-100">
              <div>
                <p className="text-sm font-medium text-slate-800">{e.description || e.category}</p>
                <p className="text-xs text-slate-500 capitalize">{e.category}</p>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-slate-800">{formatINR(e.amount)}</span>
                <button onClick={() => handleDelete(e.id)} className="p-1 text-slate-400 hover:text-red-500 transition-colors">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal isOpen={addModal} onClose={() => setAddModal(false)} title="Log Expense">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Category</label>
            <select value={addForm.category} onChange={e => setAddForm({...addForm, category: e.target.value})}
              className="w-full px-4 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-400 text-sm">
              {['accommodation','food','transport','activities','misc'].map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Amount (₹)</label>
            <input type="number" value={addForm.amount} onChange={e => setAddForm({...addForm, amount: +e.target.value})}
              className="w-full px-4 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-400 text-sm" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Description</label>
            <input type="text" value={addForm.description} onChange={e => setAddForm({...addForm, description: e.target.value})}
              placeholder="What was it for?"
              className="w-full px-4 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-400 text-sm" />
          </div>
          <Button onClick={handleAdd} className="w-full">Save Expense</Button>
        </div>
      </Modal>
    </div>
  );
}

// ── Readiness Tab ──────────────────────────────────────────────────────────
function ReadinessTab({ tripId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getTripReadiness(tripId).then(setData).catch(() => {}).finally(() => setLoading(false));
  }, [tripId]);

  if (loading) return <div className="flex justify-center py-8"><Spinner className="text-indigo-600" /></div>;
  if (!data) return <p className="text-slate-500 text-sm">Readiness data not available.</p>;

  const score = data.readiness_score || data.score || 0;
  const items = data.checklist || data.items || [];
  const color = score >= 80 ? 'green' : score >= 50 ? 'amber' : 'red';

  return (
    <div className="space-y-6">
      <div className="text-center py-4">
        <div className={`text-5xl font-bold mb-2 ${color === 'green' ? 'text-green-600' : color === 'amber' ? 'text-amber-600' : 'text-red-600'}`}>
          {score}%
        </div>
        <p className="text-slate-500 text-sm">Trip Readiness Score</p>
        <div className="mt-4 max-w-xs mx-auto">
          <ProgressBar value={score} color={color} showLabel={false} />
        </div>
      </div>
      {items.length > 0 && (
        <div className="space-y-2">
          {items.map((item, i) => (
            <div key={i} className={`flex items-start gap-3 p-3 rounded-xl border ${item.status === 'ok' || item.completed ? 'bg-green-50 border-green-100' : 'bg-amber-50 border-amber-100'}`}>
              {item.status === 'ok' || item.completed
                ? <Check className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />
                : <AlertTriangle className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" />}
              <div>
                <p className="text-sm font-medium text-slate-800">{item.label || item.title}</p>
                {item.description && <p className="text-xs text-slate-500 mt-0.5">{item.description}</p>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Notes Tab ──────────────────────────────────────────────────────────────
function NotesTab({ tripId, initialNotes }) {
  const [notes, setNotes] = useState(initialNotes || '');
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      await saveTripNotes(tripId, { user_notes: notes });
      toast.success('Notes saved');
    } catch (err) { toast.error(err.message); }
    finally { setSaving(false); }
  };

  return (
    <div className="space-y-4">
      <Textarea
        label="Trip Notes"
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        rows={10}
        placeholder="Add your notes, reminders, and tips here..."
        className="min-h-[200px]"
      />
      <div className="flex justify-end">
        <Button onClick={handleSave} loading={saving}>Save Notes</Button>
      </div>
    </div>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────
export default function TripDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [trip, setTrip] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState(0);

  const loadTrip = useCallback(() => {
    setLoading(true);
    getTrip(id).then((d) => setTrip(d.trip || d)).catch(() => toast.error('Trip not found')).finally(() => setLoading(false));
  }, [id]);

  useEffect(() => { loadTrip(); }, [loadTrip]);

  const handleShare = async () => {
    try {
      const data = await shareTrip(id);
      const url = `${window.location.origin}/trip/shared/${data.share_token || data.token}`;
      await navigator.clipboard.writeText(url);
      toast.success('Share link copied!');
    } catch { toast.error('Could not generate share link'); }
  };

  if (loading) return <div className="flex justify-center items-center min-h-[60vh]"><Spinner size="lg" className="text-indigo-600" /></div>;
  if (!trip) return <div className="max-w-4xl mx-auto px-4 py-16 text-center"><p className="text-slate-500">Trip not found.</p><Button onClick={() => navigate('/trips')} className="mt-4">Back to My Trips</Button></div>;

  const itinerary = trip.itinerary_json || {};
  const days = itinerary.itinerary || [];

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-6">
        <div className="flex items-start gap-3">
          <button onClick={() => navigate('/trips')} className="p-2 rounded-xl hover:bg-slate-100 transition-colors mt-0.5">
            <ArrowLeft className="w-5 h-5 text-slate-600" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">{itinerary.trip_title || trip.trip_title || 'My Trip'}</h1>
            <div className="flex flex-wrap items-center gap-2 mt-1">
              {days.length > 0 && <span className="text-sm text-slate-500">{days.length} day{days.length !== 1 ? 's' : ''}</span>}
              {(itinerary.total_cost || trip.budget) && (
                <span className="text-sm text-slate-500">{formatINR(itinerary.total_cost || trip.budget)}</span>
              )}
              {trip.quality_score && (
                <span className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-full bg-amber-50 text-amber-700 border border-amber-100">
                  <Star className="w-3 h-3 fill-amber-400 text-amber-400" /> {trip.quality_score.toFixed(1)}
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <Button variant="secondary" size="sm" onClick={handleShare}>
            <Share2 className="w-4 h-4" /> Share
          </Button>
          <Link to={`/trip/${id}/briefing/1`}>
            <Button variant="secondary" size="sm">
              <ClipboardList className="w-4 h-4" /> Day 1 Briefing
            </Button>
          </Link>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-slate-100 p-1 rounded-xl mb-6 overflow-x-auto">
        {TABS.map((tab, i) => (
          <button key={i} onClick={() => setActiveTab(i)}
            className={`flex-shrink-0 px-4 py-2 rounded-lg text-sm font-medium transition-all ${activeTab === i ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-600 hover:text-slate-800'}`}>
            {tab}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <AnimatePresence mode="wait">
        <motion.div key={activeTab} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
          {activeTab === 0 && (
            <div className="space-y-4">
              {itinerary.smart_insights?.length > 0 && (
                <Card className="p-5">
                  <h3 className="font-semibold text-slate-700 mb-3 text-sm">Smart Insights</h3>
                  <ul className="space-y-1.5">
                    {itinerary.smart_insights.map((s, i) => (
                      <li key={i} className="text-sm text-slate-600 flex items-start gap-2">
                        <span className="text-indigo-400 mt-0.5">•</span>{s}
                      </li>
                    ))}
                  </ul>
                </Card>
              )}
              {days.map((day, i) => (
                <DayCard key={i} day={day} index={i} tripId={id} onRefresh={loadTrip} />
              ))}
              {itinerary.document_checklist && (
                <Card className="p-5">
                  <h3 className="font-semibold text-slate-700 mb-3 text-sm flex items-center gap-2">
                    <CheckSquare className="w-4 h-4 text-indigo-500" /> Document Checklist
                  </h3>
                  <ul className="space-y-1.5">
                    {(Array.isArray(itinerary.document_checklist) ? itinerary.document_checklist : [itinerary.document_checklist]).map((item, i) => (
                      <li key={i} className="flex items-center gap-2 text-sm text-slate-600">
                        <Check className="w-4 h-4 text-green-500 flex-shrink-0" /> {typeof item === 'string' ? item : item.item || JSON.stringify(item)}
                      </li>
                    ))}
                  </ul>
                </Card>
              )}
            </div>
          )}
          {activeTab === 1 && <BookingsTab tripId={id} />}
          {activeTab === 2 && <ExpensesTab tripId={id} budget={itinerary.total_cost || trip.budget} />}
          {activeTab === 3 && <ReadinessTab tripId={id} />}
          {activeTab === 4 && <NotesTab tripId={id} initialNotes={trip.user_notes} />}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

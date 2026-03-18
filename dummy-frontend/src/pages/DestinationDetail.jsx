import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { MapPin, Star, Clock, DollarSign, ChevronLeft, Calendar } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import toast from 'react-hot-toast';
import { getDestination, getBestTime, isGoodTime, estimateBudget } from '../services/api';
import { Button, Badge, Spinner, Card } from '../components/ui/index';

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const TABS = ['Overview', 'Best Time', 'Attractions', 'Budget Estimate'];

function OverviewTab({ dest }) {
  const tags = dest.vibe_tags
    ? (typeof dest.vibe_tags === 'string' ? JSON.parse(dest.vibe_tags) : dest.vibe_tags)
    : [];
  return (
    <div className="space-y-6">
      {dest.description && (
        <div>
          <h3 className="font-semibold text-slate-700 mb-2">About</h3>
          <p className="text-slate-600 leading-relaxed">{dest.description}</p>
        </div>
      )}
      {tags.length > 0 && (
        <div>
          <h3 className="font-semibold text-slate-700 mb-3">Vibe</h3>
          <div className="flex flex-wrap gap-2">
            {tags.map((t, i) => (
              <span key={i} className="px-3 py-1.5 rounded-full bg-indigo-50 text-indigo-600 text-sm font-medium border border-indigo-100">{t}</span>
            ))}
          </div>
        </div>
      )}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
        {dest.avg_temperature_c && (
          <div className="bg-slate-50 rounded-xl p-4 text-center">
            <p className="text-2xl font-bold text-slate-800">{dest.avg_temperature_c}°C</p>
            <p className="text-xs text-slate-500 mt-1">Avg Temperature</p>
          </div>
        )}
        {dest.popularity_score && (
          <div className="bg-slate-50 rounded-xl p-4 text-center">
            <p className="text-2xl font-bold text-slate-800">{dest.popularity_score}</p>
            <p className="text-xs text-slate-500 mt-1">Popularity Score</p>
          </div>
        )}
        {dest.attractions_count !== undefined && (
          <div className="bg-slate-50 rounded-xl p-4 text-center">
            <p className="text-2xl font-bold text-slate-800">{dest.attractions_count || '—'}</p>
            <p className="text-xs text-slate-500 mt-1">Attractions</p>
          </div>
        )}
      </div>
    </div>
  );
}

function BestTimeTab({ destId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [goodTime, setGoodTime] = useState(null);

  useEffect(() => {
    const curMonth = new Date().getMonth() + 1;
    Promise.all([
      getBestTime(destId).catch(() => null),
      isGoodTime(destId, curMonth).catch(() => null),
    ]).then(([bt, gt]) => {
      setData(bt);
      setGoodTime(gt);
      setLoading(false);
    });
  }, [destId]);

  if (loading) return <div className="flex justify-center py-8"><Spinner className="text-indigo-600" /></div>;

  const chartData = MONTHS.map((m, i) => ({
    month: m,
    score: data?.monthly_scores?.[i + 1] || data?.seasonal_scores?.[i] || 50,
  }));

  const bestMonths = data?.best_months || [];

  return (
    <div className="space-y-6">
      {goodTime && (
        <div className={`p-4 rounded-xl border ${goodTime.verdict === 'good' ? 'bg-green-50 border-green-200' : goodTime.verdict === 'acceptable' ? 'bg-amber-50 border-amber-200' : 'bg-red-50 border-red-200'}`}>
          <p className="font-semibold text-slate-800">
            {MONTHS[new Date().getMonth()]} — {goodTime.verdict === 'good' ? 'Great time to visit!' : goodTime.verdict === 'acceptable' ? 'Decent time to visit' : 'Not ideal right now'}
          </p>
          {goodTime.best_alternative_month && (
            <p className="text-sm text-slate-600 mt-1">Better month: {MONTHS[goodTime.best_alternative_month - 1]}</p>
          )}
        </div>
      )}

      <div>
        <h3 className="font-semibold text-slate-700 mb-4">Monthly Seasonal Score</h3>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 0, right: 0, bottom: 0, left: -20 }}>
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => [`${v}`, 'Score']} />
              <Bar dataKey="score" radius={[4, 4, 0, 0]}>
                {chartData.map((entry, i) => (
                  <Cell key={i} fill={entry.score >= 70 ? '#6366f1' : entry.score >= 40 ? '#a5b4fc' : '#e2e8f0'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {bestMonths.length > 0 && (
        <div>
          <h3 className="font-semibold text-slate-700 mb-2">Best Months to Visit</h3>
          <div className="flex flex-wrap gap-2">
            {bestMonths.slice(0, 3).map((m, i) => (
              <span key={i} className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-sm font-medium">
                {typeof m === 'number' ? MONTHS[m - 1] : m}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function AttractionsTab({ attractions = [] }) {
  if (!attractions.length) return <p className="text-slate-500 text-sm">No attraction data available.</p>;
  return (
    <div className="space-y-3">
      {attractions.slice(0, 10).map((a, i) => (
        <div key={i} className="flex items-start gap-4 p-4 bg-slate-50 rounded-xl">
          <div className="w-10 h-10 rounded-xl bg-indigo-100 flex items-center justify-center flex-shrink-0 text-indigo-600 text-sm font-bold">
            {i + 1}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2">
              <h4 className="font-semibold text-slate-800 text-sm">{a.name}</h4>
              {a.rating && (
                <div className="flex items-center gap-1 flex-shrink-0">
                  <Star className="w-3 h-3 text-amber-400 fill-amber-400" />
                  <span className="text-xs text-slate-500">{a.rating.toFixed(1)}</span>
                </div>
              )}
            </div>
            <p className="text-xs text-slate-500 mt-0.5 capitalize">{(a.type || '').replace(/_/g, ' ')}</p>
            <div className="flex flex-wrap gap-3 mt-2 text-xs text-slate-500">
              {a.avg_visit_duration_hours && <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{a.avg_visit_duration_hours}h</span>}
              {a.entry_cost_min != null && <span className="flex items-center gap-1"><DollarSign className="w-3 h-3" />₹{a.entry_cost_min}–{a.entry_cost_max}</span>}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function BudgetEstimateTab({ destId }) {
  const [form, setForm] = useState({ duration: 3, travelers: 2, style: 'mid' });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleEstimate = async () => {
    setLoading(true);
    try {
      const data = await estimateBudget({
        destination_ids: [destId],
        duration: form.duration,
        travelers: form.travelers,
        style: form.style,
      });
      setResult(data);
    } catch (err) {
      toast.error(err.message || 'Estimate failed');
    } finally {
      setLoading(false);
    }
  };

  const formatINR = (n) => `₹${Number(n || 0).toLocaleString('en-IN')}`;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1.5">Duration (days)</label>
          <input type="number" min="1" max="21" value={form.duration}
            onChange={(e) => setForm(f => ({ ...f, duration: +e.target.value }))}
            className="w-full px-4 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-400 text-sm" />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1.5">Travelers</label>
          <input type="number" min="1" max="20" value={form.travelers}
            onChange={(e) => setForm(f => ({ ...f, travelers: +e.target.value }))}
            className="w-full px-4 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-400 text-sm" />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1.5">Style</label>
          <select value={form.style} onChange={(e) => setForm(f => ({ ...f, style: e.target.value }))}
            className="w-full px-4 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-400 text-sm">
            <option value="budget">Budget</option>
            <option value="mid">Standard</option>
            <option value="luxury">Luxury</option>
          </select>
        </div>
      </div>
      <Button onClick={handleEstimate} loading={loading}>Get Estimate</Button>

      {result && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="bg-slate-50 rounded-2xl p-5">
          <h3 className="font-bold text-slate-800 mb-4 text-lg">
            Estimated Total: {formatINR(result.total_estimated || result.total)}
          </h3>
          <div className="space-y-3">
            {(result.breakdown || result.budget_breakdown ? Object.entries(result.breakdown || result.budget_breakdown) : []).map(([k, v]) => (
              <div key={k} className="flex justify-between items-center">
                <span className="text-sm text-slate-600 capitalize">{k.replace(/_/g, ' ')}</span>
                <span className="text-sm font-semibold text-slate-800">{formatINR(v)}</span>
              </div>
            ))}
          </div>
        </motion.div>
      )}
    </div>
  );
}

export default function DestinationDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [dest, setDest] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState(0);

  useEffect(() => {
    getDestination(id)
      .then((d) => setDest(d.destination || d))
      .catch(() => toast.error('Destination not found'))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return (
    <div className="flex justify-center items-center min-h-[60vh]">
      <Spinner size="lg" className="text-indigo-600" />
    </div>
  );

  if (!dest) return (
    <div className="max-w-4xl mx-auto px-4 py-16 text-center">
      <p className="text-slate-500">Destination not found.</p>
      <Button onClick={() => navigate('/discover')} className="mt-4">Back to Discover</Button>
    </div>
  );

  const gradients = ['from-indigo-400 to-violet-600','from-amber-400 to-orange-500','from-teal-400 to-cyan-600'];
  const grad = gradients[dest.id % gradients.length] || gradients[0];

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <button onClick={() => navigate('/discover')} className="flex items-center gap-2 text-sm text-slate-500 hover:text-slate-700 mb-6 transition-colors">
        <ChevronLeft className="w-4 h-4" /> Back to Discover
      </button>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main content */}
        <div className="lg:col-span-2">
          {/* Hero */}
          <div className={`w-full h-56 sm:h-72 bg-gradient-to-br ${grad} rounded-2xl flex items-end p-6 mb-6 relative overflow-hidden`}>
            <div className="absolute inset-0 opacity-20">
              <svg className="w-full h-full"><defs><pattern id="d2" width="20" height="20" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1" fill="white"/></pattern></defs><rect width="100%" height="100%" fill="url(#d2)"/></svg>
            </div>
            <div className="relative z-10">
              <p className="text-white/70 text-xs flex items-center gap-1 mb-1">
                <MapPin className="w-3 h-3" />
                {dest.country_name || 'India'} &rsaquo; {dest.state_name || ''}
              </p>
              <h1 className="text-3xl font-bold text-white drop-shadow">{dest.name}</h1>
              <div className="flex items-center gap-2 mt-2">
                <div className="flex items-center gap-0.5">
                  {[1,2,3,4,5].map(s => <Star key={s} className={`w-4 h-4 ${s <= Math.round(dest.rating || 4) ? 'fill-amber-300 text-amber-300' : 'fill-white/30 text-white/30'}`} />)}
                </div>
                <span className="text-white/90 text-sm">{(dest.rating || 4).toFixed(1)}</span>
                {dest.budget_category && (
                  <Badge status={dest.budget_category} className="ml-2">{dest.budget_category}</Badge>
                )}
              </div>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex gap-1 bg-slate-100 p-1 rounded-xl mb-6">
            {TABS.map((tab, i) => (
              <button
                key={i}
                onClick={() => setActiveTab(i)}
                className={`flex-1 py-2 px-3 rounded-lg text-xs sm:text-sm font-medium transition-all ${activeTab === i ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-600 hover:text-slate-800'}`}
              >
                {tab}
              </button>
            ))}
          </div>

          <Card className="p-6">
            {activeTab === 0 && <OverviewTab dest={dest} />}
            {activeTab === 1 && <BestTimeTab destId={id} />}
            {activeTab === 2 && <AttractionsTab attractions={dest.attractions || []} />}
            {activeTab === 3 && <BudgetEstimateTab destId={id} />}
          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          <Card className="p-6">
            <h3 className="font-bold text-slate-800 mb-4">Plan a Trip Here</h3>
            <p className="text-sm text-slate-500 mb-4">Our AI engine will build a complete day-by-day itinerary for {dest.name}.</p>
            <Button
              className="w-full"
              onClick={() => navigate(`/planner?destination=${encodeURIComponent(dest.name)}`)}
            >
              Start Planning
            </Button>
          </Card>

          {dest.budget_category && (
            <Card className="p-6">
              <h3 className="font-semibold text-slate-700 mb-3 text-sm">Quick Facts</h3>
              <div className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-slate-500">Budget Type</span>
                  <span className="font-medium text-slate-800 capitalize">{dest.budget_category}</span>
                </div>
                {dest.best_season && (
                  <div className="flex justify-between">
                    <span className="text-slate-500">Best Season</span>
                    <span className="font-medium text-slate-800">{dest.best_season}</span>
                  </div>
                )}
                {dest.lat && dest.lng && (
                  <div className="flex justify-between">
                    <span className="text-slate-500">Location</span>
                    <span className="font-medium text-slate-800 text-xs">{dest.lat.toFixed(3)}, {dest.lng.toFixed(3)}</span>
                  </div>
                )}
              </div>
            </Card>
          )}

          <Card className="p-6">
            <h3 className="font-semibold text-slate-700 mb-3 text-sm flex items-center gap-2">
              <Calendar className="w-4 h-4 text-indigo-500" /> Current Month
            </h3>
            <IsGoodTimeWidget destId={id} />
          </Card>
        </div>
      </div>
    </div>
  );
}

function IsGoodTimeWidget({ destId }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    const m = new Date().getMonth() + 1;
    isGoodTime(destId, m).then(setData).catch(() => {});
  }, [destId]);

  if (!data) return <p className="text-sm text-slate-400">Checking...</p>;
  const color = data.verdict === 'good' ? 'text-green-600 bg-green-50' : data.verdict === 'acceptable' ? 'text-amber-600 bg-amber-50' : 'text-red-600 bg-red-50';
  return (
    <div className={`rounded-xl px-3 py-2 text-sm font-medium ${color}`}>
      {MONTHS[new Date().getMonth()]}: {data.verdict === 'good' ? 'Great time!' : data.verdict === 'acceptable' ? 'Decent time' : 'Not ideal'}
      {data.seasonal_score && <span className="text-xs ml-2 opacity-70">({data.seasonal_score}/100)</span>}
    </div>
  );
}

import { useState, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams, Routes, Route, useParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronRight, ChevronLeft, Check, Search, MapPin, Sparkles } from 'lucide-react';
import toast from 'react-hot-toast';
import {
  generateItinerary, getItineraryStatus, saveTrip,
  getCountries, getRecommendations, search as apiSearch, estimateBudget,
} from '../services/api';
import { Button, Spinner } from '../components/ui/index';
import { useAuth } from '../contexts/AuthContext';

const STYLES = ['adventure', 'cultural', 'relaxation', 'photography', 'food', 'spiritual', 'family'];
const TRAVELER_TYPES = ['solo', 'couple', 'family', 'group', 'senior'];
const DIETARY = ['none', 'vegetarian', 'vegan', 'jain', 'halal', 'gluten-free'];
const FITNESS = ['low', 'moderate', 'high'];

const STAGE_MSGS = [
  'Analyzing your preferences...',
  'Filtering 200+ attractions...',
  'Grouping by location with H3 hexes...',
  'Optimizing your daily routes...',
  'Calculating budget breakdowns...',
  'Adding Gemini AI polish...',
  'Almost ready!',
];

function StepBar({ current, total }) {
  return (
    <div className="flex items-center gap-2 mb-8">
      {Array.from({ length: total }).map((_, i) => (
        <div key={i} className="flex items-center gap-2 flex-1">
          <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition-all flex-shrink-0 ${i < current ? 'bg-indigo-600 text-white' : i === current ? 'bg-indigo-100 text-indigo-600 border-2 border-indigo-400' : 'bg-slate-100 text-slate-400'}`}>
            {i < current ? <Check className="w-4 h-4" /> : i + 1}
          </div>
          {i < total - 1 && <div className={`flex-1 h-1 rounded-full transition-all ${i < current ? 'bg-indigo-600' : 'bg-slate-200'}`} />}
        </div>
      ))}
    </div>
  );
}

function DestSearchInput({ value, onChange }) {
  const [query, setQuery] = useState(value || '');
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const timer = useRef(null);

  const handleInput = (q) => {
    setQuery(q);
    clearTimeout(timer.current);
    if (!q.trim()) { setResults([]); setOpen(false); return; }
    timer.current = setTimeout(async () => {
      try {
        const res = await apiSearch(q, 'destination');
        setResults(res.results || res.destinations || []);
        setOpen(true);
      } catch { setResults([]); }
    }, 300);
  };

  const select = (item) => {
    setQuery(item.name);
    onChange(item.name);
    setOpen(false);
    setResults([]);
  };

  return (
    <div className="relative">
      <div className="relative">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
        <input
          value={query}
          onChange={(e) => handleInput(e.target.value)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          placeholder="Search destination..."
          className="w-full pl-12 pr-4 py-3.5 rounded-2xl border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-400 text-sm"
        />
      </div>
      {open && results.length > 0 && (
        <div className="absolute z-20 left-0 right-0 mt-2 bg-white rounded-2xl shadow-xl border border-slate-100 overflow-hidden">
          {results.slice(0, 6).map((r, i) => (
            <button key={i} onMouseDown={() => select(r)}
              className="w-full text-left px-4 py-3 hover:bg-indigo-50 transition-colors flex items-center gap-3 border-b border-slate-50 last:border-0">
              <MapPin className="w-4 h-4 text-slate-400 flex-shrink-0" />
              <div>
                <p className="text-sm font-medium text-slate-800">{r.name}</p>
                {r.state_name && <p className="text-xs text-slate-500">{r.state_name}</p>}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function Step1({ form, setForm }) {
  const [recLoading, setRecLoading] = useState(false);
  const [recs, setRecs] = useState([]);
  const [countries, setCountries] = useState([]);

  useEffect(() => {
    getCountries().then((d) => setCountries(d.countries || d || [])).catch(() => {});
  }, []);

  const loadRecs = async () => {
    setRecLoading(true);
    try {
      const data = await getRecommendations({ month: new Date().getMonth() + 1 });
      setRecs(data.recommendations || data || []);
    } catch { toast.error('Could not load recommendations'); }
    finally { setRecLoading(false); }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900 mb-1">Where do you want to go?</h2>
        <p className="text-sm text-slate-500">Search for a destination or pick a country.</p>
      </div>
      <DestSearchInput value={form.destination} onChange={(v) => setForm({ ...form, destination: v, start_city: v })} />
      {form.destination && (
        <div className="flex items-center gap-2 px-4 py-3 bg-indigo-50 rounded-xl border border-indigo-100">
          <MapPin className="w-4 h-4 text-indigo-500" />
          <span className="text-sm font-medium text-indigo-700">{form.destination}</span>
          <button onClick={() => setForm({ ...form, destination: '', start_city: '' })} className="ml-auto text-indigo-400 hover:text-indigo-600 text-xs">Remove</button>
        </div>
      )}
      <div>
        <label className="block text-sm font-medium text-slate-700 mb-1.5">Country</label>
        <select value={form.destination_country} onChange={(e) => setForm({ ...form, destination_country: e.target.value })}
          className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-400 text-sm bg-white">
          <option value="India">India</option>
          {countries.filter(c => c.name !== 'India').map((c) => <option key={c.id} value={c.name}>{c.name}</option>)}
        </select>
      </div>
      <div className="border-t border-slate-100 pt-4">
        <div className="flex items-center justify-between mb-3">
          <p className="text-sm font-medium text-slate-600">Not sure where to go?</p>
          <Button variant="secondary" size="sm" loading={recLoading} onClick={loadRecs}>
            <Sparkles className="w-4 h-4" /> Suggest
          </Button>
        </div>
        {recs.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {recs.slice(0, 3).map((r, i) => (
              <button key={i} onClick={() => setForm({ ...form, destination: r.name, start_city: r.name })}
                className={`text-left p-3 rounded-xl border transition-all ${form.destination === r.name ? 'border-indigo-400 bg-indigo-50' : 'border-slate-200 hover:border-indigo-200 bg-white'}`}>
                <p className="font-semibold text-sm text-slate-800">{r.name}</p>
                <p className="text-xs text-slate-500 mt-0.5">{r.reason || r.state_name || ''}</p>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Step2({ form, setForm }) {
  const presets = [
    { label: 'Day Trip', days: 1 }, { label: 'Weekend', days: 2 },
    { label: '1 Week', days: 7 }, { label: '2 Weeks', days: 14 },
  ];
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900 mb-1">When and How Long?</h2>
        <p className="text-sm text-slate-500">Set your travel dates and duration.</p>
      </div>
      <div>
        <label className="block text-sm font-medium text-slate-700 mb-1.5">Start Date</label>
        <input type="date" value={form.start_date || ''} min={new Date().toISOString().split('T')[0]}
          onChange={(e) => {
            const d = new Date(e.target.value);
            setForm({ ...form, start_date: e.target.value, travel_month: d.getMonth() + 1 });
          }}
          className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-400 text-sm" />
      </div>
      <div>
        <label className="block text-sm font-medium text-slate-700 mb-2">Duration: {form.duration} day{form.duration !== 1 ? 's' : ''}</label>
        <div className="flex flex-wrap gap-2 mb-3">
          {presets.map((p) => (
            <button key={p.label} onClick={() => setForm({ ...form, duration: p.days })}
              className={`px-3 py-1.5 rounded-xl text-sm font-medium border transition-colors ${form.duration === p.days ? 'bg-indigo-600 text-white border-indigo-600' : 'border-slate-200 text-slate-600 hover:border-indigo-300'}`}>
              {p.label}
            </button>
          ))}
        </div>
        <input type="range" min="1" max="21" value={form.duration}
          onChange={(e) => setForm({ ...form, duration: +e.target.value })}
          className="w-full accent-indigo-600" />
        <div className="flex justify-between text-xs text-slate-400 mt-1"><span>1 day</span><span>21 days</span></div>
      </div>
    </div>
  );
}

function Step3({ form, setForm }) {
  const tierLabel = () => {
    const daily = form.budget / (form.duration || 1) / (form.travelers || 1);
    if (daily < 1000) return { label: 'Budget', color: 'text-sky-600 bg-sky-50' };
    if (daily < 5000) return { label: 'Standard', color: 'text-violet-600 bg-violet-50' };
    return { label: 'Luxury', color: 'text-amber-600 bg-amber-50' };
  };
  const tier = tierLabel();
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900 mb-1">Budget and Style</h2>
        <p className="text-sm text-slate-500">Set your total budget and preferred trip style.</p>
      </div>
      <div>
        <label className="block text-sm font-medium text-slate-700 mb-1.5">Total Budget</label>
        <div className="relative">
          <span className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500 font-medium">₹</span>
          <input type="number" min="500" step="500" value={form.budget}
            onChange={(e) => setForm({ ...form, budget: +e.target.value })}
            className="w-full pl-8 pr-4 py-3 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-400 text-sm" />
        </div>
        <div className="flex items-center justify-between mt-2">
          <p className="text-xs text-slate-500">₹{(form.budget / (form.duration || 1) / (form.travelers || 1)).toLocaleString('en-IN')}/day per person</p>
          <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${tier.color}`}>{tier.label}</span>
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-slate-700 mb-2">Trip Style</label>
        <div className="flex flex-wrap gap-2">
          {STYLES.map((s) => (
            <button key={s} onClick={() => setForm({ ...form, style: s })}
              className={`px-4 py-2 rounded-xl text-sm font-medium border capitalize transition-colors ${form.style === s ? 'bg-indigo-600 text-white border-indigo-600' : 'border-slate-200 text-slate-600 hover:border-indigo-300 bg-white'}`}>
              {s}
            </button>
          ))}
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-slate-700 mb-2">Number of Travelers</label>
        <div className="flex items-center gap-4">
          <button onClick={() => setForm({ ...form, travelers: Math.max(1, form.travelers - 1) })}
            className="w-10 h-10 rounded-xl border border-slate-200 font-bold text-lg hover:bg-slate-50 flex items-center justify-center">-</button>
          <span className="text-xl font-bold text-slate-800 min-w-[2rem] text-center">{form.travelers}</span>
          <button onClick={() => setForm({ ...form, travelers: Math.min(20, form.travelers + 1) })}
            className="w-10 h-10 rounded-xl border border-slate-200 font-bold text-lg hover:bg-slate-50 flex items-center justify-center">+</button>
        </div>
      </div>
    </div>
  );
}

function Step4({ form, setForm }) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900 mb-1">Traveler Profile</h2>
        <p className="text-sm text-slate-500">Help us personalize your experience.</p>
      </div>
      <div>
        <label className="block text-sm font-medium text-slate-700 mb-2">Traveler Type</label>
        <div className="flex flex-wrap gap-2">
          {TRAVELER_TYPES.map((t) => (
            <button key={t} onClick={() => setForm({ ...form, traveler_type: t })}
              className={`px-4 py-2 rounded-xl text-sm font-medium border capitalize transition-colors ${form.traveler_type === t ? 'bg-indigo-600 text-white border-indigo-600' : 'border-slate-200 text-slate-600 hover:border-indigo-300 bg-white'}`}>
              {t}
            </button>
          ))}
        </div>
      </div>
      {form.traveler_type === 'senior' && (
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1.5">Senior Count</label>
          <input type="number" min="1" max={form.travelers} value={form.senior_count || 1}
            onChange={(e) => setForm({ ...form, senior_count: +e.target.value })}
            className="w-24 px-4 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-400 text-sm" />
        </div>
      )}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1.5">Children Count</label>
          <input type="number" min="0" max="10" value={form.children_count || 0}
            onChange={(e) => setForm({ ...form, children_count: +e.target.value })}
            className="w-full px-4 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-400 text-sm" />
        </div>
        {(form.children_count || 0) > 0 && (
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Youngest Child Age</label>
            <input type="number" min="0" max="17" value={form.children_min_age || 5}
              onChange={(e) => setForm({ ...form, children_min_age: +e.target.value })}
              className="w-full px-4 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-400 text-sm" />
          </div>
        )}
      </div>
      <div>
        <label className="block text-sm font-medium text-slate-700 mb-2">Dietary Restrictions</label>
        <div className="flex flex-wrap gap-2">
          {DIETARY.map((d) => (
            <button key={d} onClick={() => setForm({ ...form, dietary_restrictions: d })}
              className={`px-3 py-1.5 rounded-xl text-sm font-medium border capitalize transition-colors ${form.dietary_restrictions === d ? 'bg-indigo-600 text-white border-indigo-600' : 'border-slate-200 text-slate-600 hover:border-indigo-300 bg-white'}`}>
              {d}
            </button>
          ))}
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-slate-700 mb-2">Fitness Level</label>
        <div className="flex gap-2">
          {FITNESS.map((f) => (
            <button key={f} onClick={() => setForm({ ...form, fitness_level: f })}
              className={`flex-1 py-2 rounded-xl text-sm font-medium border capitalize transition-colors ${form.fitness_level === f ? 'bg-indigo-600 text-white border-indigo-600' : 'border-slate-200 text-slate-600 hover:border-indigo-300 bg-white'}`}>
              {f}
            </button>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1.5">Special Occasion (optional)</label>
          <input type="text" value={form.special_occasion || ''} placeholder="Anniversary, Birthday..."
            onChange={(e) => setForm({ ...form, special_occasion: e.target.value })}
            className="w-full px-4 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-400 text-sm" />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1.5">From City IATA (optional)</label>
          <input type="text" value={form.from_city_iata || ''} placeholder="e.g. BOM, DEL, BLR"
            onChange={(e) => setForm({ ...form, from_city_iata: e.target.value.toUpperCase() })}
            className="w-full px-4 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-400 text-sm" />
        </div>
      </div>
      <label className="flex items-center gap-3 cursor-pointer">
        <input type="checkbox" checked={form.accessibility || false}
          onChange={(e) => setForm({ ...form, accessibility: e.target.checked })}
          className="accent-indigo-600 w-4 h-4" />
        <span className="text-sm text-slate-700">I have accessibility needs (wheelchair, ramp access)</span>
      </label>
    </div>
  );
}

function Step5({ form, onGenerate, loading }) {
  const [estimate, setEstimate] = useState(null);
  const [estLoading, setEstLoading] = useState(false);
  const fmt = (n) => `₹${Number(n || 0).toLocaleString('en-IN')}`;

  const getEst = async () => {
    if (!form.destination) { toast.error('Please select a destination first'); return; }
    setEstLoading(true);
    try {
      const data = await estimateBudget({ destination_names: [form.destination], duration: form.duration, travelers: form.travelers, style: form.style });
      setEstimate(data);
    } catch { toast.error('Could not get estimate'); }
    finally { setEstLoading(false); }
  };

  const rows = [
    ['Destination', form.destination || '—'],
    ['Duration', `${form.duration} day${form.duration !== 1 ? 's' : ''}`],
    ['Travelers', form.travelers],
    ['Budget', fmt(form.budget)],
    ['Style', form.style],
    ['Traveler Type', form.traveler_type],
    form.start_date ? ['Start Date', new Intl.DateTimeFormat('en-IN').format(new Date(form.start_date))] : null,
    form.dietary_restrictions && form.dietary_restrictions !== 'none' ? ['Dietary', form.dietary_restrictions] : null,
    form.special_occasion ? ['Occasion', form.special_occasion] : null,
  ].filter(Boolean);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900 mb-1">Review Your Trip</h2>
        <p className="text-sm text-slate-500">Confirm and generate your personalized itinerary.</p>
      </div>
      <div className="bg-slate-50 rounded-2xl p-5 space-y-3">
        {rows.map(([k, v]) => (
          <div key={k} className="flex justify-between text-sm">
            <span className="text-slate-500">{k}</span>
            <span className="font-semibold text-slate-800 capitalize">{String(v)}</span>
          </div>
        ))}
      </div>
      {estimate && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="bg-indigo-50 rounded-2xl p-4 border border-indigo-100">
          <p className="font-semibold text-indigo-800 mb-2">Estimated: {fmt(estimate.total_estimated || estimate.total)}</p>
          {estimate.breakdown && Object.entries(estimate.breakdown).map(([k, v]) => (
            <div key={k} className="flex justify-between text-xs text-indigo-700 py-0.5">
              <span className="capitalize">{k.replace(/_/g, ' ')}</span><span>{fmt(v)}</span>
            </div>
          ))}
        </motion.div>
      )}
      <div className="flex flex-col sm:flex-row gap-3">
        <Button variant="secondary" onClick={getEst} loading={estLoading} className="flex-1">Get Budget Estimate</Button>
        <Button onClick={onGenerate} loading={loading} className="flex-1" size="lg">
          <Sparkles className="w-4 h-4" /> Generate My Trip Plan
        </Button>
      </div>
    </div>
  );
}

function GeneratingScreen() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const [stageIdx, setStageIdx] = useState(0);
  const [progress, setProgress] = useState(5);

  useEffect(() => {
    const iv = setInterval(() => {
      setStageIdx((i) => (i + 1) % STAGE_MSGS.length);
      setProgress((p) => Math.min(90, p + 12));
    }, 2500);
    return () => clearInterval(iv);
  }, []);

  useEffect(() => {
    if (!jobId) return;
    const poll = setInterval(async () => {
      try {
        const data = await getItineraryStatus(jobId);
        if (data.status === 'completed') {
          clearInterval(poll);
          setProgress(100);
          if (isAuthenticated && data.result) {
            try {
              const saved = await saveTrip({
                itinerary_json: data.result,
                trip_title: data.result.trip_title,
                budget: data.result.total_cost,
                duration: data.result.itinerary?.length,
              });
              toast.success('Your trip is ready!');
              navigate(`/trip/${saved.trip_id || saved.id}`);
              return;
            } catch { /* fall through */ }
          }
          sessionStorage.setItem('pending_itinerary', JSON.stringify(data.result));
          toast.success('Your trip is ready!');
          navigate('/trips');
        } else if (data.status === 'failed') {
          clearInterval(poll);
          toast.error(data.error || 'Trip generation failed. Please try again.');
          navigate('/planner');
        }
      } catch { /* keep polling */ }
    }, 2000);
    return () => clearInterval(poll);
  }, [jobId, navigate, isAuthenticated]);

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4">
      <div className="w-full max-w-md text-center">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
          className="w-20 h-20 rounded-3xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center mx-auto mb-8 shadow-xl shadow-indigo-200"
        >
          <Sparkles className="w-10 h-10 text-white" />
        </motion.div>
        <h2 className="text-2xl font-bold text-slate-900 mb-3">Building Your Trip</h2>
        <AnimatePresence mode="wait">
          <motion.p key={stageIdx} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} className="text-slate-500 mb-8 h-6">
            {STAGE_MSGS[stageIdx]}
          </motion.p>
        </AnimatePresence>
        <div className="w-full bg-slate-100 rounded-full h-2.5 mb-4 overflow-hidden">
          <motion.div animate={{ width: `${progress}%` }} transition={{ duration: 0.5 }}
            className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-600" />
        </div>
        <p className="text-xs text-slate-400">This takes 20-40 seconds. Please don't close this tab.</p>
      </div>
    </div>
  );
}

const DEFAULT_FORM = {
  destination: '', start_city: '', destination_country: 'India',
  budget: 15000, duration: 3, travelers: 2, style: 'cultural',
  traveler_type: 'couple', start_date: '', travel_month: new Date().getMonth() + 1,
  dietary_restrictions: 'none', fitness_level: 'moderate',
  accessibility: false, children_count: 0, senior_count: 0,
};

function PlannerForm() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState(() => {
    try {
      const saved = sessionStorage.getItem('planner_form');
      const base = saved ? JSON.parse(saved) : { ...DEFAULT_FORM };
      const dest = searchParams.get('destination');
      if (dest) { base.destination = dest; base.start_city = dest; }
      return base;
    } catch { return { ...DEFAULT_FORM }; }
  });

  useEffect(() => {
    sessionStorage.setItem('planner_form', JSON.stringify(form));
  }, [form]);

  const canNext = () => {
    if (step === 0 && !form.destination) { toast.error('Please enter a destination'); return false; }
    return true;
  };

  const handleGenerate = async () => {
    if (!form.destination) { toast.error('Please select a destination'); return; }
    setLoading(true);
    try {
      const payload = {
        destination_country: form.destination_country || 'India',
        start_city: form.start_city || form.destination,
        selected_destinations: [{ name: form.destination }],
        budget: form.budget,
        duration: form.duration,
        travelers: form.travelers,
        style: form.style,
        traveler_type: form.traveler_type,
        travel_month: form.travel_month,
        ...(form.dietary_restrictions !== 'none' ? { dietary_restrictions: form.dietary_restrictions } : {}),
        accessibility: form.accessibility ? 1 : 0,
        children_count: form.children_count || 0,
        senior_count: form.senior_count || 0,
        fitness_level: form.fitness_level,
        ...(form.special_occasion ? { special_occasion: form.special_occasion } : {}),
        ...(form.from_city_iata ? { from_city_iata: form.from_city_iata } : {}),
        ...(form.start_date ? { start_date: form.start_date } : {}),
      };
      const data = await generateItinerary(payload);
      sessionStorage.removeItem('planner_form');
      navigate(`/planner/generating/${data.job_id}`);
    } catch (err) {
      toast.error(err.message || 'Failed to start trip generation');
    } finally {
      setLoading(false);
    }
  };

  const TOTAL_STEPS = 5;
  const stepComponents = [
    <Step1 form={form} setForm={setForm} />,
    <Step2 form={form} setForm={setForm} />,
    <Step3 form={form} setForm={setForm} />,
    <Step4 form={form} setForm={setForm} />,
    <Step5 form={form} onGenerate={handleGenerate} loading={loading} />,
  ];

  return (
    <div className="max-w-2xl mx-auto px-4 py-10">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900 mb-1">Plan Your Trip</h1>
        <p className="text-sm text-slate-500">Step {step + 1} of {TOTAL_STEPS}</p>
      </div>
      <StepBar current={step} total={TOTAL_STEPS} />
      <AnimatePresence mode="wait">
        <motion.div key={step} initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} transition={{ duration: 0.2 }}
          className="bg-white rounded-3xl shadow-sm border border-slate-100 p-6 sm:p-8">
          {stepComponents[step]}
        </motion.div>
      </AnimatePresence>
      <div className="flex justify-between mt-6">
        <Button variant="ghost" onClick={() => setStep(Math.max(0, step - 1))} disabled={step === 0}>
          <ChevronLeft className="w-4 h-4" /> Back
        </Button>
        {step < TOTAL_STEPS - 1 && (
          <Button onClick={() => { if (canNext()) setStep(step + 1); }}>
            Next <ChevronRight className="w-4 h-4" />
          </Button>
        )}
      </div>
    </div>
  );
}

export default function Planner() {
  return (
    <Routes>
      <Route path="generating/:jobId" element={<GeneratingScreen />} />
      <Route path="*" element={<PlannerForm />} />
    </Routes>
  );
}

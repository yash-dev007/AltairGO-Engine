import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { MapPin, ChevronDown, ChevronUp, Clock, Sparkles, Share2 } from 'lucide-react';
import toast from 'react-hot-toast';
import { getSharedTrip } from '../services/api';
import { Badge, Spinner, Card } from '../components/ui/index';

const formatINR = (n) => `₹${Number(n || 0).toLocaleString('en-IN')}`;

function ReadOnlyDayCard({ day, index }) {
  const [expanded, setExpanded] = useState(index === 0);
  const activities = day.activities || [];
  return (
    <Card className="overflow-hidden">
      <button onClick={() => setExpanded(!expanded)} className="w-full flex items-center justify-between p-5 text-left hover:bg-slate-50 transition-colors">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-white font-bold text-sm">
            {index + 1}
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-bold text-slate-800">Day {index + 1}</span>
              {day.location && <span className="text-sm text-slate-500">{day.location}</span>}
              {day.theme && <span className="text-xs px-2 py-0.5 rounded-full bg-violet-100 text-violet-700 font-medium">{day.theme}</span>}
            </div>
            <div className="flex items-center gap-2 mt-0.5">
              {day.pacing_level && <Badge status={day.pacing_level}>{day.pacing_level}</Badge>}
              <span className="text-xs text-slate-400">{activities.length} activities</span>
            </div>
          </div>
        </div>
        {expanded ? <ChevronUp className="w-5 h-5 text-slate-400" /> : <ChevronDown className="w-5 h-5 text-slate-400" />}
      </button>
      <AnimatePresence>
        {expanded && (
          <motion.div initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }} className="overflow-hidden">
            <div className="border-t border-slate-100 p-4 space-y-3">
              {activities.map((act, i) => (
                <div key={i} className="flex gap-4 p-3 bg-slate-50 rounded-xl">
                  <div className="flex-shrink-0 min-w-[3.5rem]">
                    <span className="text-xs font-bold text-slate-500 bg-white border border-slate-200 px-2 py-1 rounded-lg whitespace-nowrap">{act.time || '—'}</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-sm text-slate-800">{act.name}</p>
                    {act.description && <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">{act.description}</p>}
                    <div className="flex flex-wrap gap-2 mt-1">
                      {act.avg_visit_duration_hours && <span className="text-xs text-slate-400 flex items-center gap-1"><Clock className="w-3 h-3" />{act.avg_visit_duration_hours}h</span>}
                      {act.cost > 0 && <span className="text-xs text-slate-400">{formatINR(act.cost)}</span>}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  );
}

export default function SharedTrip() {
  const { token } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    getSharedTrip(token)
      .then(setData)
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false));
  }, [token]);

  const handleShare = async () => {
    await navigator.clipboard.writeText(window.location.href);
    toast.success('Link copied!');
  };

  if (loading) return <div className="flex justify-center items-center min-h-[60vh]"><Spinner size="lg" className="text-indigo-600" /></div>;

  if (notFound) return (
    <div className="max-w-lg mx-auto px-4 py-16 text-center">
      <div className="w-16 h-16 rounded-2xl bg-slate-100 flex items-center justify-center mx-auto mb-4">
        <MapPin className="w-8 h-8 text-slate-400" />
      </div>
      <h2 className="text-xl font-bold text-slate-700 mb-2">Trip not found</h2>
      <p className="text-slate-500 mb-6">This shared trip link may have expired or been revoked.</p>
      <Link to="/planner" className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 text-white font-semibold">
        Plan Your Own Trip
      </Link>
    </div>
  );

  const itinerary = data?.itinerary_json || data?.itinerary || data || {};
  const days = itinerary.itinerary || [];

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      {/* Shared banner */}
      <div className="bg-gradient-to-r from-indigo-600 to-violet-700 rounded-2xl p-5 mb-8 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Sparkles className="w-6 h-6 text-white" />
          <div>
            <p className="text-white font-semibold">Shared with AltairGO</p>
            <p className="text-indigo-200 text-sm">Read-only view</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleShare} className="flex items-center gap-2 px-3 py-2 rounded-xl bg-white/15 text-white text-sm font-medium hover:bg-white/25 transition-colors border border-white/20">
            <Share2 className="w-4 h-4" /> Copy Link
          </button>
          <Link to="/planner" className="flex items-center gap-2 px-3 py-2 rounded-xl bg-white text-indigo-700 text-sm font-semibold hover:bg-indigo-50 transition-colors">
            Plan Similar
          </Link>
        </div>
      </div>

      {/* Trip header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-slate-900">{itinerary.trip_title || 'Shared Trip'}</h1>
        <div className="flex flex-wrap items-center gap-3 mt-2 text-sm text-slate-500">
          {days.length > 0 && <span>{days.length} days</span>}
          {itinerary.total_cost && <span>{formatINR(itinerary.total_cost)}</span>}
        </div>
      </div>

      {/* Smart insights */}
      {itinerary.smart_insights?.length > 0 && (
        <Card className="p-5 mb-6">
          <h3 className="font-semibold text-slate-700 mb-3 text-sm">Smart Insights</h3>
          <ul className="space-y-1.5">
            {itinerary.smart_insights.map((s, i) => (
              <li key={i} className="text-sm text-slate-600 flex items-start gap-2">
                <span className="text-indigo-400 mt-0.5">•</span> {s}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {/* Days */}
      <div className="space-y-4 mb-10">
        {days.map((day, i) => <ReadOnlyDayCard key={i} day={day} index={i} />)}
      </div>

      {/* CTA */}
      <div className="bg-gradient-to-br from-indigo-50 to-violet-50 rounded-2xl p-8 text-center border border-indigo-100">
        <h3 className="text-xl font-bold text-slate-800 mb-2">Want a trip like this?</h3>
        <p className="text-slate-500 text-sm mb-5">Let AI plan your perfect itinerary in minutes.</p>
        <Link to="/planner" className="inline-flex items-center gap-2 px-8 py-3 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 text-white font-semibold hover:shadow-lg transition-all">
          <Sparkles className="w-4 h-4" /> Plan a Similar Trip
        </Link>
      </div>
    </div>
  );
}

import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowLeft, ShoppingBag, Shirt, CloudRain, Calendar, AlertTriangle, Phone, Camera, ChevronLeft, ChevronRight, Printer } from 'lucide-react';
import toast from 'react-hot-toast';
import { getDailyBriefing } from '../services/api';
import { Spinner, Card } from '../components/ui/index';

export default function DailyBriefing() {
  const { id: tripId, day } = useParams();
  const dayNum = parseInt(day, 10);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setData(null);
    getDailyBriefing(tripId, dayNum)
      .then(setData)
      .catch(() => toast.error('Briefing not available'))
      .finally(() => setLoading(false));
  }, [tripId, dayNum]);

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6 no-print">
        <div className="flex items-center gap-3">
          <Link to={`/trip/${tripId}`} className="p-2 rounded-xl hover:bg-slate-100 transition-colors">
            <ArrowLeft className="w-5 h-5 text-slate-600" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Day {dayNum} Briefing</h1>
            <p className="text-sm text-slate-500">Your personalized daily guide</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {dayNum > 1 && (
            <Link to={`/trip/${tripId}/briefing/${dayNum - 1}`}>
              <button className="p-2 rounded-xl border border-slate-200 hover:bg-slate-50 transition-colors">
                <ChevronLeft className="w-5 h-5 text-slate-600" />
              </button>
            </Link>
          )}
          <Link to={`/trip/${tripId}/briefing/${dayNum + 1}`}>
            <button className="p-2 rounded-xl border border-slate-200 hover:bg-slate-50 transition-colors">
              <ChevronRight className="w-5 h-5 text-slate-600" />
            </button>
          </Link>
          <button onClick={() => window.print()} className="p-2 rounded-xl border border-slate-200 hover:bg-slate-50 transition-colors">
            <Printer className="w-5 h-5 text-slate-600" />
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-8"><Spinner size="lg" className="text-indigo-600" /></div>
      ) : !data ? (
        <div className="text-center py-12">
          <p className="text-slate-500">No briefing available for Day {dayNum}.</p>
        </div>
      ) : (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-5">
          {/* Morning tip */}
          {data.morning_tip && (
            <div className="bg-gradient-to-r from-indigo-50 to-violet-50 rounded-2xl p-5 border border-indigo-100">
              <p className="text-xs font-semibold text-indigo-500 uppercase tracking-wide mb-2">Morning Tip</p>
              <p className="text-slate-700 italic">"{data.morning_tip}"</p>
            </div>
          )}

          {/* Weather */}
          {data.weather_alerts?.length > 0 && (
            <div className="bg-amber-50 rounded-2xl p-5 border border-amber-200">
              <div className="flex items-center gap-2 mb-3">
                <CloudRain className="w-5 h-5 text-amber-600" />
                <h3 className="font-semibold text-amber-800">Weather Alerts</h3>
              </div>
              {data.weather_alerts.map((alert, i) => (
                <p key={i} className="text-sm text-amber-700">{typeof alert === 'string' ? alert : alert.message || JSON.stringify(alert)}</p>
              ))}
            </div>
          )}

          {/* What to carry */}
          {data.what_to_carry?.length > 0 && (
            <Card className="p-5">
              <div className="flex items-center gap-2 mb-4">
                <div className="w-8 h-8 rounded-xl bg-indigo-50 flex items-center justify-center">
                  <ShoppingBag className="w-4 h-4 text-indigo-600" />
                </div>
                <h3 className="font-semibold text-slate-800">What to Carry</h3>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {data.what_to_carry.map((item, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm text-slate-600">
                    <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 flex-shrink-0" />
                    {item}
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Dress code */}
          {data.dress_code && (
            <Card className="p-5">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-8 h-8 rounded-xl bg-violet-50 flex items-center justify-center">
                  <Shirt className="w-4 h-4 text-violet-600" />
                </div>
                <h3 className="font-semibold text-slate-800">Dress Code</h3>
              </div>
              <p className="text-sm text-slate-600">{data.dress_code}</p>
            </Card>
          )}

          {/* Bookings for the day */}
          {data.confirmed_bookings?.length > 0 && (
            <Card className="p-5">
              <div className="flex items-center gap-2 mb-4">
                <div className="w-8 h-8 rounded-xl bg-green-50 flex items-center justify-center">
                  <Calendar className="w-4 h-4 text-green-600" />
                </div>
                <h3 className="font-semibold text-slate-800">Confirmed Bookings</h3>
              </div>
              <div className="space-y-2">
                {data.confirmed_bookings.map((b, i) => (
                  <div key={i} className="flex justify-between text-sm py-2 border-b border-slate-100 last:border-0">
                    <span className="text-slate-700">{b.description || b.type}</span>
                    <span className="text-green-600 font-medium text-xs">Confirmed</span>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Local Events */}
          {data.local_events?.length > 0 && (
            <Card className="p-5">
              <div className="flex items-center gap-2 mb-4">
                <div className="w-8 h-8 rounded-xl bg-amber-50 flex items-center justify-center">
                  <Calendar className="w-4 h-4 text-amber-600" />
                </div>
                <h3 className="font-semibold text-slate-800">Local Events Today</h3>
              </div>
              {data.local_events.map((e, i) => (
                <div key={i} className="text-sm text-slate-600 py-2 border-b border-slate-100 last:border-0">
                  <span className="font-medium">{e.name || e}</span>
                  {e.description && <p className="text-slate-500 text-xs mt-0.5">{e.description}</p>}
                </div>
              ))}
            </Card>
          )}

          {/* Crowd warnings */}
          {data.crowd_warnings?.length > 0 && (
            <div className="bg-red-50 rounded-2xl p-5 border border-red-200">
              <div className="flex items-center gap-2 mb-3">
                <AlertTriangle className="w-5 h-5 text-red-500" />
                <h3 className="font-semibold text-red-700">Crowd Warnings</h3>
              </div>
              {data.crowd_warnings.map((w, i) => (
                <p key={i} className="text-sm text-red-600">{w}</p>
              ))}
            </div>
          )}

          {/* Photo spots */}
          {data.photo_spots?.length > 0 && (
            <Card className="p-5">
              <div className="flex items-center gap-2 mb-4">
                <div className="w-8 h-8 rounded-xl bg-sky-50 flex items-center justify-center">
                  <Camera className="w-4 h-4 text-sky-600" />
                </div>
                <h3 className="font-semibold text-slate-800">Photo Spots</h3>
              </div>
              <div className="space-y-1">
                {data.photo_spots.map((s, i) => (
                  <p key={i} className="text-sm text-slate-600">{s.name || s} {s.best_hour ? <span className="text-xs text-slate-400">Best at {s.best_hour}:00</span> : ''}</p>
                ))}
              </div>
            </Card>
          )}

          {/* Emergency contacts */}
          {data.emergency_contacts && (
            <div className="bg-slate-900 rounded-2xl p-5">
              <div className="flex items-center gap-2 mb-4">
                <Phone className="w-5 h-5 text-white" />
                <h3 className="font-semibold text-white">Emergency Contacts</h3>
              </div>
              {typeof data.emergency_contacts === 'object' ? (
                Object.entries(data.emergency_contacts).map(([k, v]) => (
                  <div key={k} className="flex justify-between text-sm py-1.5 border-b border-slate-700 last:border-0">
                    <span className="text-slate-300 capitalize">{k.replace(/_/g, ' ')}</span>
                    <span className="text-white font-medium">{v}</span>
                  </div>
                ))
              ) : (
                <p className="text-slate-300 text-sm">{data.emergency_contacts}</p>
              )}
            </div>
          )}
        </motion.div>
      )}
    </div>
  );
}

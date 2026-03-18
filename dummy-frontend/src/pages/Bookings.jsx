import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowLeft, Check, X, BookOpen } from 'lucide-react';
import toast from 'react-hot-toast';
import { getBookings, approveBooking, rejectBooking, cancelBooking, executeAllBookings } from '../services/api';
import { Badge, Button, Spinner, EmptyState } from '../components/ui/index';

const formatINR = (n) => `₹${Number(n || 0).toLocaleString('en-IN')}`;

const STATUS_TABS = ['all', 'pending', 'approved', 'booked', 'cancelled'];

export default function Bookings() {
  const { id: tripId } = useParams();
  const [bookings, setBookings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('all');
  const [executing, setExecuting] = useState(false);

  const load = () => {
    setLoading(true);
    getBookings(tripId).then(setBookings).catch(() => toast.error('Failed to load bookings')).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [tripId]);

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

  const allBookings = bookings?.bookings || bookings?.all_bookings || [];
  const filtered = activeTab === 'all' ? allBookings : allBookings.filter(b => b.status === activeTab);

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <div className="flex items-center gap-3 mb-6">
        <Link to={`/trip/${tripId}`} className="p-2 rounded-xl hover:bg-slate-100 transition-colors">
          <ArrowLeft className="w-5 h-5 text-slate-600" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Bookings</h1>
          <p className="text-sm text-slate-500">{allBookings.length} total booking{allBookings.length !== 1 ? 's' : ''}</p>
        </div>
      </div>

      <div className="flex flex-wrap gap-3 mb-6 justify-between">
        <div className="flex gap-1 bg-slate-100 p-1 rounded-xl overflow-x-auto">
          {STATUS_TABS.map(t => (
            <button key={t} onClick={() => setActiveTab(t)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all capitalize whitespace-nowrap ${activeTab === t ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-600 hover:text-slate-800'}`}>
              {t}
            </button>
          ))}
        </div>
        <Button size="sm" loading={executing} onClick={handleExecuteAll}>
          <Check className="w-4 h-4" /> Execute All Approved
        </Button>
      </div>

      {loading ? (
        <div className="flex justify-center py-8"><Spinner className="text-indigo-600" /></div>
      ) : filtered.length === 0 ? (
        <EmptyState icon={BookOpen} title={`No ${activeTab === 'all' ? '' : activeTab} bookings`} description="Bookings will appear here once generated." />
      ) : (
        <div className="space-y-3">
          {filtered.map((b) => (
            <motion.div key={b.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              className="bg-white rounded-2xl border border-slate-100 shadow-sm p-4 flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <Badge status={b.booking_type || 'other'} className="capitalize">{b.booking_type?.replace(/_/g, ' ') || 'other'}</Badge>
                  <Badge status={b.status}>{b.status}</Badge>
                </div>
                <p className="font-medium text-slate-800 text-sm">{b.description || b.booking_reference || 'Booking'}</p>
                {b.cost && <p className="text-xs text-slate-500 mt-0.5">{formatINR(b.cost)}</p>}
                {b.details && <p className="text-xs text-slate-400 mt-1">{typeof b.details === 'string' ? b.details : JSON.stringify(b.details)}</p>}
              </div>
              <div className="flex gap-1 flex-shrink-0">
                {b.status === 'pending' && (
                  <>
                    <button onClick={() => handleAction('approve', b.id)} className="p-1.5 rounded-lg hover:bg-green-100 text-green-600 transition-colors" title="Approve">
                      <Check className="w-4 h-4" />
                    </button>
                    <button onClick={() => handleAction('reject', b.id)} className="p-1.5 rounded-lg hover:bg-red-100 text-red-500 transition-colors" title="Reject">
                      <X className="w-4 h-4" />
                    </button>
                  </>
                )}
                {['approved', 'booked'].includes(b.status) && (
                  <button onClick={() => handleAction('cancel', b.id)} className="px-2 py-1 rounded-lg text-xs font-medium text-red-600 hover:bg-red-50 transition-colors">
                    Cancel
                  </button>
                )}
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { MapPin, Calendar, Users, Wallet, Star, Share2, Trash2, Eye, Plus } from 'lucide-react';
import toast from 'react-hot-toast';
import { getUserTrips, shareTrip } from '../services/api';
import { Button, Badge, Spinner, EmptyState, Card } from '../components/ui/index';

function TripCard({ trip, onView, onShare }) {
  const formatINR = (n) => `₹${Number(n || 0).toLocaleString('en-IN')}`;
  const formatDate = (d) => d ? new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(d)) : null;

  const gradients = ['from-indigo-400 to-violet-500', 'from-amber-400 to-orange-500', 'from-teal-400 to-cyan-500', 'from-rose-400 to-pink-500'];
  const grad = gradients[(trip.id || 0) % gradients.length];
  const destinations = trip.itinerary_json?.itinerary?.map(d => d.location).filter(Boolean).slice(0, 3) || [];
  const uniqueDestinations = [...new Set(destinations)];

  return (
    <Card hover className="overflow-hidden">
      <div className={`h-24 bg-gradient-to-br ${grad} relative p-4 flex items-end`}>
        {trip.quality_score && (
          <span className="absolute top-3 right-3 flex items-center gap-1 bg-white/20 backdrop-blur-sm text-white text-xs font-medium px-2 py-1 rounded-full border border-white/30">
            <Star className="w-3 h-3 fill-amber-300 text-amber-300" />
            {trip.quality_score.toFixed(1)}
          </span>
        )}
        <h3 className="text-white font-bold text-sm leading-tight drop-shadow line-clamp-2">
          {trip.trip_title || `Trip to ${uniqueDestinations[0] || 'Unknown'}`}
        </h3>
      </div>
      <div className="p-4">
        <div className="space-y-2 mb-4">
          {uniqueDestinations.length > 0 && (
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <MapPin className="w-3 h-3 text-indigo-400" />
              <span className="truncate">{uniqueDestinations.join(', ')}</span>
            </div>
          )}
          {trip.duration && (
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <Calendar className="w-3 h-3 text-indigo-400" />
              <span>{trip.duration} day{trip.duration !== 1 ? 's' : ''}</span>
              {formatDate(trip.start_date) && <span className="text-slate-400">• {formatDate(trip.start_date)}</span>}
            </div>
          )}
          {trip.travelers && (
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <Users className="w-3 h-3 text-indigo-400" />
              <span>{trip.travelers} traveler{trip.travelers !== 1 ? 's' : ''}</span>
            </div>
          )}
          {trip.budget && (
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <Wallet className="w-3 h-3 text-indigo-400" />
              <span>{formatINR(trip.budget)}</span>
            </div>
          )}
        </div>

        <div className="flex gap-2">
          <Button size="sm" className="flex-1" onClick={onView}>
            <Eye className="w-3.5 h-3.5" /> View
          </Button>
          <Button size="sm" variant="secondary" onClick={onShare}>
            <Share2 className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>
    </Card>
  );
}

function SkeletonCard() {
  return (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden animate-pulse">
      <div className="h-24 bg-slate-200" />
      <div className="p-4 space-y-3">
        <div className="h-3 bg-slate-200 rounded w-3/4" />
        <div className="h-3 bg-slate-100 rounded w-1/2" />
        <div className="h-3 bg-slate-100 rounded w-2/3" />
        <div className="h-8 bg-slate-100 rounded-xl mt-4" />
      </div>
    </div>
  );
}

export default function MyTrips() {
  const navigate = useNavigate();
  const [trips, setTrips] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [filter, setFilter] = useState('all');

  const fetchTrips = async (p = 1) => {
    setLoading(true);
    try {
      const data = await getUserTrips(p);
      const items = data.trips || data.items || data || [];
      if (p === 1) setTrips(items);
      else setTrips(prev => [...prev, ...items]);
      setHasMore(items.length === 10);
    } catch {
      toast.error('Failed to load trips');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchTrips(1); }, []);

  const handleShare = async (trip) => {
    try {
      const data = await shareTrip(trip.id);
      const url = `${window.location.origin}/trip/shared/${data.share_token || data.token}`;
      await navigator.clipboard.writeText(url);
      toast.success('Share link copied to clipboard!');
    } catch {
      toast.error('Could not generate share link');
    }
  };

  const now = new Date();
  const filtered = trips.filter(t => {
    if (filter === 'all') return true;
    const start = t.start_date ? new Date(t.start_date) : null;
    if (filter === 'upcoming') return start && start >= now;
    if (filter === 'past') return !start || start < now;
    return true;
  });

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 mb-1">My Trips</h1>
          <p className="text-slate-500 text-sm">{trips.length} trip{trips.length !== 1 ? 's' : ''} planned</p>
        </div>
        <Button onClick={() => navigate('/planner')}>
          <Plus className="w-4 h-4" /> Plan New Trip
        </Button>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-1 bg-slate-100 p-1 rounded-xl mb-6 w-fit">
        {['all', 'upcoming', 'past'].map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all capitalize ${filter === f ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-600 hover:text-slate-800'}`}
          >
            {f}
          </button>
        ))}
      </div>

      {loading && page === 1 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
          {Array(8).fill(0).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={MapPin}
          title={filter === 'all' ? "No trips yet" : `No ${filter} trips`}
          description="Start planning your next adventure with AltairGO."
          action={() => navigate('/planner')}
          actionLabel="Plan Your First Trip"
        />
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
            {filtered.map((trip, i) => (
              <motion.div
                key={trip.id}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
              >
                <TripCard
                  trip={trip}
                  onView={() => navigate(`/trip/${trip.id}`)}
                  onShare={() => handleShare(trip)}
                />
              </motion.div>
            ))}
          </div>
          {hasMore && (
            <div className="flex justify-center mt-8">
              <Button variant="secondary" loading={loading} onClick={() => { const next = page + 1; setPage(next); fetchTrips(next); }}>
                Load More
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

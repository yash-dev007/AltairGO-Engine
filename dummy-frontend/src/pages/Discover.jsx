import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Search, Filter, MapPin, Star, X, SlidersHorizontal, Sparkles } from 'lucide-react';
import toast from 'react-hot-toast';
import { getDestinations, getCountries, getRecommendations, search as apiSearch } from '../services/api';
import { Badge, Spinner, Button, EmptyState } from '../components/ui/index';

const TRAVELER_TYPES = ['solo', 'couple', 'family', 'group', 'senior'];
const BUDGET_CATS = ['budget', 'mid', 'luxury'];
const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

function DestCard({ dest, onClick }) {
  const gradients = ['from-indigo-400 to-violet-600','from-amber-400 to-orange-500','from-teal-400 to-cyan-600','from-rose-400 to-pink-600','from-green-400 to-emerald-500','from-purple-400 to-indigo-600','from-sky-400 to-blue-600','from-yellow-400 to-amber-500'];
  const grad = gradients[(dest.id || 0) % gradients.length];
  const budgetLabels = { budget: 'Budget', mid: 'Standard', luxury: 'Luxury' };
  return (
    <motion.div
      whileHover={{ y: -3 }}
      className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden cursor-pointer hover:shadow-md transition-all"
      onClick={onClick}
    >
      <div className={`h-44 bg-gradient-to-br ${grad} relative flex items-end p-4`}>
        {dest.budget_category && (
          <span className="absolute top-3 right-3 text-xs px-2.5 py-1 rounded-full bg-white/20 text-white font-medium backdrop-blur-sm border border-white/30">
            {budgetLabels[dest.budget_category] || dest.budget_category}
          </span>
        )}
        <h3 className="text-white font-bold text-lg drop-shadow-sm">{dest.name}</h3>
      </div>
      <div className="p-4">
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs text-slate-500 flex items-center gap-1">
            <MapPin className="w-3 h-3" />
            {dest.state_name || 'India'}
          </p>
          <div className="flex items-center gap-0.5">
            {[1,2,3,4,5].map(s => (
              <Star key={s} className={`w-3 h-3 ${s <= Math.round(dest.rating || 4) ? 'text-amber-400 fill-amber-400' : 'text-slate-200 fill-slate-200'}`} />
            ))}
            <span className="text-xs text-slate-400 ml-1">{(dest.rating || 4).toFixed(1)}</span>
          </div>
        </div>
        {dest.vibe_tags && (
          <div className="flex flex-wrap gap-1 mt-2">
            {(typeof dest.vibe_tags === 'string' ? JSON.parse(dest.vibe_tags) : dest.vibe_tags).slice(0, 3).map((tag, i) => (
              <span key={i} className="text-xs px-2 py-0.5 rounded-full bg-slate-50 text-slate-500 border border-slate-100">{tag}</span>
            ))}
          </div>
        )}
        <button className="mt-3 w-full text-sm font-medium text-indigo-600 border border-indigo-100 rounded-xl py-2 hover:bg-indigo-50 transition-colors">
          View Details
        </button>
      </div>
    </motion.div>
  );
}

export default function Discover() {
  const navigate = useNavigate();
  const [destinations, setDestinations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [filterOpen, setFilterOpen] = useState(false);
  const [searchQ, setSearchQ] = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [recommendations, setRecommendations] = useState([]);
  const [recLoading, setRecLoading] = useState(false);
  const searchTimer = useRef(null);

  const [filters, setFilters] = useState({
    budget_category: '',
    traveler_type: '',
    month: new Date().getMonth() + 1,
    min_rating: '',
  });

  const fetchDestinations = useCallback(async (p = 1, newFilters = filters) => {
    setLoading(true);
    try {
      const params = { page: p, page_size: 12 };
      if (newFilters.budget_category) params.tag = newFilters.budget_category;
      if (newFilters.min_rating) params.min_rating = newFilters.min_rating;
      const data = await getDestinations(params);
      const items = data.destinations || data.items || data || [];
      if (p === 1) setDestinations(items);
      else setDestinations(prev => [...prev, ...items]);
      setHasMore(items.length === 12);
    } catch {
      toast.error('Failed to load destinations');
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => { fetchDestinations(1); }, []);

  const handleSearch = useCallback((q) => {
    clearTimeout(searchTimer.current);
    if (!q.trim()) { setSearchResults(null); return; }
    searchTimer.current = setTimeout(async () => {
      setSearchLoading(true);
      try {
        const res = await apiSearch(q, 'destination');
        setSearchResults(res.results || res.destinations || []);
      } catch { setSearchResults([]); }
      finally { setSearchLoading(false); }
    }, 300);
  }, []);

  const applyFilters = () => {
    setPage(1);
    fetchDestinations(1, filters);
    setFilterOpen(false);
  };

  const loadRecommendations = async () => {
    setRecLoading(true);
    try {
      const month = new Date().getMonth() + 1;
      const data = await getRecommendations({ month });
      setRecommendations(data.recommendations || data || []);
    } catch { toast.error('Could not load recommendations'); }
    finally { setRecLoading(false); }
  };

  const displayList = searchResults !== null ? searchResults : destinations;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900 mb-2">Discover India</h1>
        <p className="text-slate-500">Explore 200+ destinations curated by AI and loved by travelers.</p>
      </div>

      {/* AI Recommendations bar */}
      <div className="bg-gradient-to-r from-indigo-50 to-violet-50 rounded-2xl p-5 mb-8 border border-indigo-100">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <p className="font-semibold text-slate-800 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-indigo-500" />
              Not sure where to go?
            </p>
            <p className="text-sm text-slate-500 mt-1">Let AI recommend destinations based on current season and trends.</p>
          </div>
          <Button onClick={loadRecommendations} loading={recLoading} variant="primary" size="sm">
            Recommend Me
          </Button>
        </div>
        {recommendations.length > 0 && (
          <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-3">
            {recommendations.slice(0, 3).map((rec, i) => (
              <div
                key={i}
                onClick={() => navigate(`/destination/${rec.id}`)}
                className="bg-white rounded-xl p-3 border border-indigo-100 cursor-pointer hover:border-indigo-300 transition-colors"
              >
                <p className="font-semibold text-sm text-slate-800">{rec.name}</p>
                <p className="text-xs text-slate-500">{rec.reason || rec.state_name || ''}</p>
                <span className="text-xs text-indigo-600 font-medium">Score: {rec.score?.toFixed(0) || rec.recommendation_score?.toFixed(0) || '—'}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Search + Filter row */}
      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <div className="flex-1 relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          {searchLoading && <Spinner size="sm" className="absolute right-4 top-1/2 -translate-y-1/2 text-indigo-500" />}
          <input
            value={searchQ}
            onChange={(e) => { setSearchQ(e.target.value); handleSearch(e.target.value); }}
            placeholder="Search destinations..."
            className="w-full pl-10 pr-4 py-3 rounded-xl border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-400 text-sm"
          />
          {searchQ && (
            <button onClick={() => { setSearchQ(''); setSearchResults(null); }} className="absolute right-10 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
        <Button variant="secondary" onClick={() => setFilterOpen(!filterOpen)} className="flex items-center gap-2">
          <SlidersHorizontal className="w-4 h-4" /> Filters
        </Button>
      </div>

      {/* Filter panel */}
      {filterOpen && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white rounded-2xl border border-slate-100 shadow-sm p-6 mb-6"
        >
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            <div>
              <p className="text-sm font-semibold text-slate-700 mb-2">Budget</p>
              <div className="flex flex-wrap gap-2">
                {BUDGET_CATS.map(b => (
                  <button
                    key={b}
                    onClick={() => setFilters(f => ({ ...f, budget_category: f.budget_category === b ? '' : b }))}
                    className={`px-3 py-1.5 rounded-xl text-sm font-medium border transition-colors capitalize ${filters.budget_category === b ? 'bg-indigo-600 text-white border-indigo-600' : 'border-slate-200 text-slate-600 hover:border-indigo-300'}`}
                  >
                    {b}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-700 mb-2">Traveler Type</p>
              <div className="flex flex-wrap gap-2">
                {TRAVELER_TYPES.map(t => (
                  <button
                    key={t}
                    onClick={() => setFilters(f => ({ ...f, traveler_type: f.traveler_type === t ? '' : t }))}
                    className={`px-3 py-1.5 rounded-xl text-sm font-medium border transition-colors capitalize ${filters.traveler_type === t ? 'bg-indigo-600 text-white border-indigo-600' : 'border-slate-200 text-slate-600 hover:border-indigo-300'}`}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-700 mb-2">Month: {MONTHS[filters.month - 1]}</p>
              <input
                type="range" min="1" max="12" value={filters.month}
                onChange={(e) => setFilters(f => ({ ...f, month: Number(e.target.value) }))}
                className="w-full accent-indigo-600"
              />
            </div>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <Button variant="ghost" size="sm" onClick={() => { setFilters({ budget_category: '', traveler_type: '', month: new Date().getMonth() + 1, min_rating: '' }); }}>
              Reset
            </Button>
            <Button size="sm" onClick={applyFilters}>Apply Filters</Button>
          </div>
        </motion.div>
      )}

      {/* Results */}
      {loading && page === 1 ? (
        <div className="flex justify-center py-16">
          <Spinner size="lg" className="text-indigo-600" />
        </div>
      ) : displayList.length === 0 ? (
        <EmptyState
          icon={MapPin}
          title="No destinations found"
          description="Try adjusting your search or filters."
          action={() => { setSearchQ(''); setSearchResults(null); fetchDestinations(1); }}
          actionLabel="Reset Search"
        />
      ) : (
        <>
          {searchResults !== null && (
            <p className="text-sm text-slate-500 mb-4">{searchResults.length} result{searchResults.length !== 1 ? 's' : ''} for "{searchQ}"</p>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
            {displayList.map((dest, i) => (
              <DestCard key={dest.id || i} dest={dest} onClick={() => navigate(`/destination/${dest.id}`)} />
            ))}
          </div>
          {hasMore && searchResults === null && (
            <div className="flex justify-center mt-8">
              <Button
                variant="secondary"
                loading={loading}
                onClick={() => { const next = page + 1; setPage(next); fetchDestinations(next); }}
              >
                Load More
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

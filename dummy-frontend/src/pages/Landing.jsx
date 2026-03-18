import { useState, useEffect, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Search, Zap, Calendar, Star, ArrowRight, Shield, CloudRain, MapPin, BookOpen, Edit3, Brain } from 'lucide-react';
import { getDestinations } from '../services/api';

function useCountUp(target, duration = 2000) {
  const [count, setCount] = useState(0);
  const ref = useRef(null);
  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        let start = 0;
        const step = target / (duration / 16);
        const timer = setInterval(() => {
          start += step;
          if (start >= target) { setCount(target); clearInterval(timer); }
          else setCount(Math.floor(start));
        }, 16);
        observer.disconnect();
      }
    }, { threshold: 0.5 });
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, [target, duration]);
  return [count, ref];
}

function HeroSection() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');

  const handleSearch = (e) => {
    e.preventDefault();
    if (query.trim()) navigate(`/planner?destination=${encodeURIComponent(query)}`);
    else navigate('/planner');
  };

  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden bg-gradient-to-br from-indigo-900 via-indigo-800 to-violet-900">
      {/* SVG dot pattern */}
      <div className="absolute inset-0 opacity-20">
        <svg className="w-full h-full" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="dots" x="0" y="0" width="24" height="24" patternUnits="userSpaceOnUse">
              <circle cx="2" cy="2" r="1.5" fill="white" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#dots)" />
        </svg>
      </div>

      {/* Glow blobs */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-violet-600 rounded-full filter blur-3xl opacity-20 animate-pulse" />
      <div className="absolute bottom-1/4 right-1/4 w-64 h-64 bg-indigo-400 rounded-full filter blur-3xl opacity-20" />

      <div className="relative z-10 max-w-4xl mx-auto px-4 text-center">
        <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
          <span className="inline-flex items-center gap-2 bg-white/10 border border-white/20 text-white/90 text-xs font-medium px-4 py-2 rounded-full mb-6 backdrop-blur-sm">
            <Zap className="w-3 h-3 text-amber-400" />
            AI-Powered Travel Intelligence
          </span>

          <h1 className="text-4xl sm:text-5xl md:text-6xl font-bold text-white mb-6 leading-tight">
            Plan Your Perfect
            <br />
            <span className="bg-gradient-to-r from-amber-300 to-amber-500 bg-clip-text text-transparent">
              Indian Journey
            </span>
          </h1>

          <p className="text-lg sm:text-xl text-indigo-200 mb-10 max-w-2xl mx-auto">
            AI-powered trip planning that books everything for you — hotels, flights, activities, and restaurants.
          </p>

          <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-3 max-w-xl mx-auto">
            <div className="flex-1 relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-indigo-300" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Where do you want to go?"
                className="w-full pl-12 pr-4 py-4 rounded-2xl bg-white/15 border border-white/25 text-white placeholder-indigo-300 backdrop-blur-sm focus:outline-none focus:ring-2 focus:ring-amber-400 text-base"
              />
            </div>
            <button
              type="submit"
              className="px-8 py-4 rounded-2xl bg-gradient-to-r from-amber-400 to-amber-500 text-slate-900 font-bold text-base hover:shadow-xl hover:from-amber-300 transition-all duration-200 flex items-center gap-2 justify-center whitespace-nowrap"
            >
              Plan My Trip <ArrowRight className="w-5 h-5" />
            </button>
          </form>

          <div className="flex flex-wrap justify-center gap-6 mt-10 text-sm text-indigo-300">
            <span>Popular: Rajasthan</span>
            <span>Kerala Backwaters</span>
            <span>Himalayan Trek</span>
            <span>Goa Beach</span>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

function HowItWorks() {
  const steps = [
    { icon: Search, num: '01', title: 'Tell Us Where', desc: 'Search any destination in India or let AI recommend based on your preferences.' },
    { icon: Brain, num: '02', title: 'AI Builds Your Plan', desc: 'Our 5-step engine clusters attractions, optimizes routes, and allocates budget intelligently.' },
    { icon: Edit3, num: '03', title: 'Review & Customize', desc: 'Tweak every detail — swap hotels, add activities, adjust budget, write notes.' },
    { icon: BookOpen, num: '04', title: 'We Book Everything', desc: 'One click to execute all bookings — hotel, flights, activities, restaurants.' },
  ];

  return (
    <section className="py-20 bg-white">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-14">
          <h2 className="text-3xl sm:text-4xl font-bold text-slate-900 mb-4">How AltairGO Works</h2>
          <p className="text-lg text-slate-500 max-w-xl mx-auto">From idea to booked trip in minutes, not hours.</p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8">
          {steps.map((step, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
              className="relative text-center"
            >
              {i < steps.length - 1 && (
                <div className="hidden lg:block absolute top-8 left-[60%] w-[80%] h-px bg-gradient-to-r from-indigo-200 to-transparent" />
              )}
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center mx-auto mb-4 shadow-lg shadow-indigo-200">
                <step.icon className="w-7 h-7 text-white" />
              </div>
              <span className="text-xs font-bold text-indigo-400 mb-2 block">{step.num}</span>
              <h3 className="font-bold text-slate-800 mb-2">{step.title}</h3>
              <p className="text-sm text-slate-500 leading-relaxed">{step.desc}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Features() {
  const features = [
    { icon: Brain, title: 'AI Itinerary Engine', desc: '5-step deterministic pipeline — filter, cluster, allocate, optimize, assemble — powered by Gemini 2.0.', color: 'indigo' },
    { icon: BookOpen, title: 'Smart Booking Automation', desc: 'Hotels, outbound + return flights, airport transfers, activity tickets, restaurants — all in one click.', color: 'violet' },
    { icon: Shield, title: 'Budget Intelligence', desc: 'Real cost breakdowns with tier-based allocation. Group discounts, hotel cost from live data, zero hidden fees.', color: 'amber' },
    { icon: CloudRain, title: 'Live Weather Alerts', desc: 'Open-Meteo integration. Rainy-day alternatives automatically built into your plan.', color: 'sky' },
    { icon: Calendar, title: 'Local Events Sync', desc: 'Festivals, fairs, and holidays auto-detected for your travel window. Avoid closures, embrace celebrations.', color: 'green' },
    { icon: Edit3, title: 'Full Trip Editor', desc: 'Swap any hotel, add/remove activities, reorder your day, add custom bookings — complete control.', color: 'rose' },
  ];

  const colorMap = {
    indigo: 'bg-indigo-50 text-indigo-600',
    violet: 'bg-violet-50 text-violet-600',
    amber: 'bg-amber-50 text-amber-600',
    sky: 'bg-sky-50 text-sky-600',
    green: 'bg-green-50 text-green-600',
    rose: 'bg-rose-50 text-rose-600',
  };

  return (
    <section className="py-20 bg-slate-50">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-14">
          <h2 className="text-3xl sm:text-4xl font-bold text-slate-900 mb-4">Everything You Need</h2>
          <p className="text-lg text-slate-500 max-w-xl mx-auto">Not just planning — a complete travel intelligence platform.</p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((f, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.08 }}
              className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 hover:shadow-md transition-shadow"
            >
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center mb-4 ${colorMap[f.color]}`}>
                <f.icon className="w-6 h-6" />
              </div>
              <h3 className="font-bold text-slate-800 mb-2">{f.title}</h3>
              <p className="text-sm text-slate-500 leading-relaxed">{f.desc}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

function DestinationGradient({ name, index }) {
  const gradients = [
    'from-indigo-400 to-violet-600',
    'from-amber-400 to-orange-600',
    'from-teal-400 to-cyan-600',
    'from-rose-400 to-pink-600',
    'from-green-400 to-emerald-600',
    'from-purple-400 to-indigo-600',
  ];
  return (
    <div className={`w-full h-48 bg-gradient-to-br ${gradients[index % gradients.length]} flex items-end p-4`}>
      <h3 className="text-white font-bold text-lg drop-shadow">{name}</h3>
    </div>
  );
}

function PopularDestinations() {
  const [destinations, setDestinations] = useState([]);
  const navigate = useNavigate();

  useEffect(() => {
    getDestinations({ limit: 6, page: 1 })
      .then((d) => setDestinations(d.destinations || d.items || d || []))
      .catch(() => {});
  }, []);

  if (destinations.length === 0) return null;

  const budgetLabel = { budget: 'Budget', mid: 'Standard', luxury: 'Luxury' };

  return (
    <section className="py-20 bg-white">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-end justify-between mb-10">
          <div>
            <h2 className="text-3xl sm:text-4xl font-bold text-slate-900 mb-2">Popular Destinations</h2>
            <p className="text-slate-500">Hand-picked, AI-curated, traveler-loved.</p>
          </div>
          <Link to="/discover" className="text-indigo-600 font-medium text-sm hover:text-indigo-700 flex items-center gap-1">
            View all <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {destinations.map((dest, i) => (
            <motion.div
              key={dest.id}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.08 }}
              className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden cursor-pointer hover:shadow-md transition-all duration-200"
              onClick={() => navigate(`/destination/${dest.id}`)}
            >
              <DestinationGradient name={dest.name} index={i} />
              <div className="p-4">
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <h3 className="font-bold text-slate-800">{dest.name}</h3>
                    <p className="text-xs text-slate-500 flex items-center gap-1">
                      <MapPin className="w-3 h-3" />
                      {dest.state_name || dest.country_name || 'India'}
                    </p>
                  </div>
                  {dest.budget_category && (
                    <span className="text-xs px-2 py-1 rounded-full bg-indigo-50 text-indigo-600 font-medium border border-indigo-100">
                      {budgetLabel[dest.budget_category] || dest.budget_category}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-1">
                  {[1,2,3,4,5].map((s) => (
                    <Star
                      key={s}
                      className={`w-3.5 h-3.5 ${s <= Math.round(dest.rating || 4) ? 'text-amber-400 fill-amber-400' : 'text-slate-200 fill-slate-200'}`}
                    />
                  ))}
                  <span className="text-xs text-slate-500 ml-1">{dest.rating?.toFixed(1) || '4.0'}</span>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

function StatItem({ value, label, suffix, prefix }) {
  const [count, ref] = useCountUp(value);
  return (
    <div ref={ref} className="text-center">
      <div className="text-4xl font-bold text-white mb-1">
        {prefix || ''}{count.toLocaleString('en-IN')}{suffix || ''}
      </div>
      <div className="text-indigo-200 text-sm font-medium">{label}</div>
    </div>
  );
}

function StatsBar() {
  const stats = [
    { value: 10000, label: 'Trips Planned', suffix: '+' },
    { value: 200, label: 'Destinations', suffix: '+' },
    { value: 98, label: 'Satisfaction', suffix: '%' },
    { value: 0, label: 'Hidden Fees', prefix: '₹' },
  ];

  return (
    <section className="py-16 bg-gradient-to-r from-indigo-600 to-violet-700">
      <div className="max-w-5xl mx-auto px-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
          {stats.map((stat, i) => <StatItem key={i} {...stat} />)}
        </div>
      </div>
    </section>
  );
}

function CTABanner() {
  const navigate = useNavigate();
  return (
    <section className="py-20 bg-slate-50">
      <div className="max-w-3xl mx-auto px-4 text-center">
        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}>
          <h2 className="text-3xl sm:text-4xl font-bold text-slate-900 mb-4">
            Start Planning for Free
          </h2>
          <p className="text-lg text-slate-500 mb-8">
            Join thousands of travelers who plan smarter with AltairGO.
            No subscription, no hidden costs.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <button
              onClick={() => navigate('/register')}
              className="px-8 py-4 rounded-2xl bg-gradient-to-r from-indigo-600 to-violet-600 text-white font-bold text-base hover:shadow-xl transition-all duration-200"
            >
              Get Started Free
            </button>
            <button
              onClick={() => navigate('/discover')}
              className="px-8 py-4 rounded-2xl border border-slate-200 text-slate-700 font-medium text-base hover:bg-slate-100 transition-colors"
            >
              Browse Destinations
            </button>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

export default function Landing() {
  return (
    <div>
      <HeroSection />
      <HowItWorks />
      <Features />
      <PopularDestinations />
      <StatsBar />
      <CTABanner />
    </div>
  );
}

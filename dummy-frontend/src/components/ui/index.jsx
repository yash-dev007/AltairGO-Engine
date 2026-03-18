import { motion, AnimatePresence } from 'framer-motion';
import { createPortal } from 'react-dom';
import { X, TrendingUp, TrendingDown, Minus } from 'lucide-react';

// ── Button ─────────────────────────────────────────────────────────────────
const variantClasses = {
  primary: 'bg-gradient-to-r from-indigo-600 to-violet-600 text-white hover:from-indigo-700 hover:to-violet-700 shadow-md hover:shadow-lg',
  secondary: 'bg-white text-indigo-600 border border-indigo-200 hover:bg-indigo-50',
  ghost: 'bg-transparent text-slate-600 hover:bg-slate-100',
  danger: 'bg-red-600 text-white hover:bg-red-700',
  outline: 'bg-transparent text-indigo-600 border border-indigo-300 hover:bg-indigo-50',
};
const sizeClasses = {
  sm: 'px-3 py-1.5 text-sm rounded-lg',
  md: 'px-4 py-2 text-sm rounded-xl',
  lg: 'px-6 py-3 text-base rounded-xl',
};

export function Button({
  variant = 'primary', size = 'md', loading = false,
  disabled, className = '', children, ...props
}) {
  return (
    <button
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center gap-2 font-semibold transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:ring-offset-2 disabled:opacity-60 disabled:cursor-not-allowed ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      {...props}
    >
      {loading && <Spinner size="sm" />}
      {children}
    </button>
  );
}

// ── Card ───────────────────────────────────────────────────────────────────
export function Card({ className = '', hover = false, children, ...props }) {
  if (hover) {
    return (
      <motion.div
        whileHover={{ y: -2, boxShadow: '0 12px 40px -8px rgba(79,70,229,0.18)' }}
        transition={{ duration: 0.2 }}
        className={`bg-white rounded-2xl shadow-sm border border-slate-100 ${className}`}
        {...props}
      >
        {children}
      </motion.div>
    );
  }
  return (
    <div className={`bg-white rounded-2xl shadow-sm border border-slate-100 ${className}`} {...props}>
      {children}
    </div>
  );
}

// ── Input ──────────────────────────────────────────────────────────────────
export function Input({ label, error, className = '', id, ...props }) {
  const inputId = id || label?.toLowerCase().replace(/\s+/g, '-');
  return (
    <div className="w-full">
      {label && (
        <label htmlFor={inputId} className="block text-sm font-medium text-slate-700 mb-1.5">
          {label}
        </label>
      )}
      <input
        id={inputId}
        className={`w-full px-4 py-2.5 rounded-xl border ${error ? 'border-red-400 focus:ring-red-400' : 'border-slate-200 focus:ring-indigo-400'} bg-white focus:outline-none focus:ring-2 focus:ring-offset-0 transition-all text-slate-900 placeholder-slate-400 text-sm ${className}`}
        {...props}
      />
      {error && <p className="mt-1 text-xs text-red-500">{error}</p>}
    </div>
  );
}

// ── Select ─────────────────────────────────────────────────────────────────
export function Select({ label, error, className = '', id, children, ...props }) {
  const selectId = id || label?.toLowerCase().replace(/\s+/g, '-');
  return (
    <div className="w-full">
      {label && (
        <label htmlFor={selectId} className="block text-sm font-medium text-slate-700 mb-1.5">
          {label}
        </label>
      )}
      <select
        id={selectId}
        className={`w-full px-4 py-2.5 rounded-xl border ${error ? 'border-red-400' : 'border-slate-200'} bg-white focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:ring-offset-0 transition-all text-slate-900 text-sm ${className}`}
        {...props}
      >
        {children}
      </select>
      {error && <p className="mt-1 text-xs text-red-500">{error}</p>}
    </div>
  );
}

// ── Textarea ───────────────────────────────────────────────────────────────
export function Textarea({ label, error, className = '', id, ...props }) {
  const taId = id || label?.toLowerCase().replace(/\s+/g, '-');
  return (
    <div className="w-full">
      {label && (
        <label htmlFor={taId} className="block text-sm font-medium text-slate-700 mb-1.5">
          {label}
        </label>
      )}
      <textarea
        id={taId}
        className={`w-full px-4 py-2.5 rounded-xl border ${error ? 'border-red-400' : 'border-slate-200'} bg-white focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:ring-offset-0 transition-all text-slate-900 placeholder-slate-400 text-sm resize-none ${className}`}
        {...props}
      />
      {error && <p className="mt-1 text-xs text-red-500">{error}</p>}
    </div>
  );
}

// ── Badge ──────────────────────────────────────────────────────────────────
const badgeColors = {
  completed: 'bg-green-100 text-green-700 border-green-200',
  pending: 'bg-amber-100 text-amber-700 border-amber-200',
  failed: 'bg-red-100 text-red-700 border-red-200',
  processing: 'bg-blue-100 text-blue-700 border-blue-200',
  cancelled: 'bg-slate-100 text-slate-600 border-slate-200',
  approved: 'bg-green-100 text-green-700 border-green-200',
  rejected: 'bg-red-100 text-red-700 border-red-200',
  queued: 'bg-purple-100 text-purple-700 border-purple-200',
  booked: 'bg-indigo-100 text-indigo-700 border-indigo-200',
  self_arranged: 'bg-teal-100 text-teal-700 border-teal-200',
  budget: 'bg-sky-100 text-sky-700 border-sky-200',
  standard: 'bg-violet-100 text-violet-700 border-violet-200',
  luxury: 'bg-amber-100 text-amber-700 border-amber-200',
  intense: 'bg-red-100 text-red-700 border-red-200',
  moderate: 'bg-amber-100 text-amber-700 border-amber-200',
  relaxed: 'bg-green-100 text-green-700 border-green-200',
};

export function Badge({ status, className = '', children }) {
  const color = badgeColors[status] || badgeColors[children?.toLowerCase()] || 'bg-slate-100 text-slate-600 border-slate-200';
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${color} ${className}`}>
      {children || status}
    </span>
  );
}

// ── Spinner ────────────────────────────────────────────────────────────────
const spinnerSizes = { sm: 'w-4 h-4', md: 'w-6 h-6', lg: 'w-8 h-8' };

export function Spinner({ size = 'md', className = '' }) {
  return (
    <svg
      className={`animate-spin ${spinnerSizes[size]} ${className}`}
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}

// ── Modal ──────────────────────────────────────────────────────────────────
export function Modal({ isOpen, onClose, title, children, size = 'md' }) {
  const sizeMap = { sm: 'max-w-sm', md: 'max-w-lg', lg: 'max-w-2xl', xl: 'max-w-4xl' };
  if (typeof document === 'undefined') return null;

  return createPortal(
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
        >
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.95, opacity: 0 }}
            transition={{ type: 'spring', duration: 0.3 }}
            className={`relative bg-white rounded-2xl shadow-2xl w-full ${sizeMap[size]} max-h-[90vh] overflow-y-auto`}
          >
            <div className="flex items-center justify-between p-6 border-b border-slate-100">
              <h3 className="text-lg font-semibold text-slate-900">{title}</h3>
              <button onClick={onClose} className="p-2 rounded-lg hover:bg-slate-100 transition-colors">
                <X className="w-5 h-5 text-slate-500" />
              </button>
            </div>
            <div className="p-6">{children}</div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body
  );
}

// ── ProgressBar ────────────────────────────────────────────────────────────
export function ProgressBar({ value = 0, color = 'indigo', showLabel = true, className = '' }) {
  const colorMap = {
    indigo: 'bg-indigo-500',
    green: 'bg-green-500',
    amber: 'bg-amber-500',
    red: 'bg-red-500',
    violet: 'bg-violet-500',
  };
  return (
    <div className={`w-full ${className}`}>
      <div className="flex justify-between mb-1">
        {showLabel && <span className="text-sm font-medium text-slate-700">{Math.round(value)}%</span>}
      </div>
      <div className="w-full bg-slate-100 rounded-full h-2">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${Math.min(100, Math.max(0, value))}%` }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
          className={`h-2 rounded-full ${colorMap[color] || colorMap.indigo}`}
        />
      </div>
    </div>
  );
}

// ── EmptyState ─────────────────────────────────────────────────────────────
export function EmptyState({ icon: Icon, title, description, action, actionLabel }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
      {Icon && (
        <div className="w-16 h-16 rounded-2xl bg-indigo-50 flex items-center justify-center mb-4">
          <Icon className="w-8 h-8 text-indigo-400" />
        </div>
      )}
      <h3 className="text-lg font-semibold text-slate-700 mb-2">{title}</h3>
      {description && <p className="text-sm text-slate-500 max-w-sm mb-6">{description}</p>}
      {action && actionLabel && (
        <Button onClick={action}>{actionLabel}</Button>
      )}
    </div>
  );
}

// ── StatCard ───────────────────────────────────────────────────────────────
export function StatCard({ icon: Icon, label, value, trend, trendLabel, color = 'indigo' }) {
  const colorMap = {
    indigo: 'bg-indigo-50 text-indigo-600',
    green: 'bg-green-50 text-green-600',
    amber: 'bg-amber-50 text-amber-600',
    violet: 'bg-violet-50 text-violet-600',
    blue: 'bg-blue-50 text-blue-600',
  };
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-slate-500 font-medium mb-1">{label}</p>
          <p className="text-2xl font-bold text-slate-900">{value ?? '—'}</p>
          {trendLabel && (
            <p className="text-xs text-slate-500 mt-1 flex items-center gap-1">
              {trend > 0 ? <TrendingUp className="w-3 h-3 text-green-500" /> :
               trend < 0 ? <TrendingDown className="w-3 h-3 text-red-500" /> :
               <Minus className="w-3 h-3 text-slate-400" />}
              {trendLabel}
            </p>
          )}
        </div>
        {Icon && (
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${colorMap[color]}`}>
            <Icon className="w-5 h-5" />
          </div>
        )}
      </div>
    </Card>
  );
}

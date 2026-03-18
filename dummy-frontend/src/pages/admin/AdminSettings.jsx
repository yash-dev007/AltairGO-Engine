import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Settings, Save, RefreshCw, Info } from 'lucide-react';
import toast from 'react-hot-toast';
import { getEngineConfig, updateEngineConfig } from '../../services/api';
import { Button, Spinner, Card } from '../../components/ui/index';

const CONFIG_META = {
  VALIDATION_STRICT: { label: 'Strict Validation', type: 'boolean', description: 'Enable strict budget/day validation checks.' },
  GEMINI_MODEL: { label: 'Gemini Model', type: 'select', options: ['gemini-2.0-flash', 'gemini-2.0-flash-lite', 'gemini-1.5-pro'], description: 'AI model used for itinerary polish.' },
  THEME_THRESHOLD: { label: 'Theme Threshold', type: 'number', description: 'Min overlap ratio for day theme detection (0.0–1.0). Default: 0.20.' },
  MAX_ACTIVITIES_PER_DAY: { label: 'Max Activities/Day', type: 'number', description: 'Maximum number of activities per day in the itinerary.' },
  POPULARITY_FLOOR: { label: 'Popularity Floor', type: 'number', description: 'Minimum popularity score for an attraction to be included.' },
  SEASONAL_SCORE_FLOOR: { label: 'Seasonal Score Floor', type: 'number', description: 'Minimum seasonal score gate (default 40).' },
  CACHE_TTL_DAYS: { label: 'Cache TTL (days)', type: 'number', description: 'How long itinerary cache lives in Redis.' },
  BUDGET_OVERAGE_PCT: { label: 'Budget Overage %', type: 'number', description: 'Allowed budget overage percentage (default 5).' },
  URBAN_SPEED_KMH: { label: 'Urban Speed (km/h)', type: 'number', description: 'Urban travel speed for route optimization.' },
  CATEGORY_CAP: { label: 'Category Cap', type: 'number', description: 'Max attractions of same type per filter call.' },
};

export default function AdminSettings() {
  const [config, setConfig] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [edited, setEdited] = useState({});

  const load = () => {
    setLoading(true);
    getEngineConfig()
      .then((d) => { setConfig(d.config || d.settings || d || {}); setEdited({}); })
      .catch(() => toast.error('Failed to load config'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleChange = (key, value) => {
    setEdited((e) => ({ ...e, [key]: value }));
  };

  const handleSave = async () => {
    if (Object.keys(edited).length === 0) { toast('No changes to save', { icon: 'ℹ️' }); return; }
    setSaving(true);
    try {
      await updateEngineConfig(edited);
      toast.success('Engine configuration updated');
      setConfig((c) => ({ ...c, ...edited }));
      setEdited({});
    } catch (err) { toast.error(err.message || 'Save failed'); }
    finally { setSaving(false); }
  };

  const currentValue = (key) => edited[key] !== undefined ? edited[key] : config[key];

  if (loading) return <div className="flex justify-center py-8"><Spinner className="text-indigo-600" /></div>;

  const knownKeys = Object.keys(CONFIG_META);
  const unknownKeys = Object.keys(config).filter(k => !knownKeys.includes(k));

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Engine Settings</h1>
          <p className="text-sm text-slate-500 mt-0.5">Runtime configuration — no redeploy required</p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={load}><RefreshCw className="w-4 h-4" /> Reload</Button>
          <Button size="sm" loading={saving} onClick={handleSave}>
            <Save className="w-4 h-4" /> Save Changes
          </Button>
        </div>
      </div>

      {Object.keys(edited).length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm text-amber-700 flex items-center gap-2">
          <Info className="w-4 h-4 flex-shrink-0" />
          {Object.keys(edited).length} unsaved change{Object.keys(edited).length !== 1 ? 's' : ''}. Click Save to apply.
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {knownKeys.map((key) => {
          const meta = CONFIG_META[key];
          const val = currentValue(key);
          const isEdited = edited[key] !== undefined;

          return (
            <motion.div key={key} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <Card className={`p-5 ${isEdited ? 'border-indigo-200 bg-indigo-50/30' : ''}`}>
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <h3 className="font-semibold text-slate-800 text-sm">{meta.label}</h3>
                    <p className="text-xs text-slate-400 font-mono mt-0.5">{key}</p>
                  </div>
                  {isEdited && <span className="text-xs text-indigo-600 font-medium bg-indigo-100 px-2 py-0.5 rounded-full">Modified</span>}
                </div>
                <p className="text-xs text-slate-500 mb-3">{meta.description}</p>

                {meta.type === 'boolean' ? (
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={val === true || val === 'true' || val === '1'}
                      onChange={(e) => handleChange(key, e.target.checked)}
                      className="w-4 h-4 accent-indigo-600"
                    />
                    <span className="text-sm text-slate-700">{val === true || val === 'true' || val === '1' ? 'Enabled' : 'Disabled'}</span>
                  </label>
                ) : meta.type === 'select' ? (
                  <select
                    value={val || ''}
                    onChange={(e) => handleChange(key, e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-400 text-sm bg-white"
                  >
                    {meta.options.map((o) => <option key={o} value={o}>{o}</option>)}
                  </select>
                ) : (
                  <input
                    type="number"
                    step="0.01"
                    value={val !== undefined && val !== null ? val : ''}
                    onChange={(e) => handleChange(key, e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-400 text-sm"
                  />
                )}
              </Card>
            </motion.div>
          );
        })}
      </div>

      {/* Unknown keys from backend */}
      {unknownKeys.length > 0 && (
        <Card className="p-5">
          <h3 className="font-semibold text-slate-700 mb-4 text-sm flex items-center gap-2">
            <Settings className="w-4 h-4" /> Additional Settings
          </h3>
          <div className="space-y-3">
            {unknownKeys.map((key) => {
              const val = currentValue(key);
              return (
                <div key={key} className="flex items-center gap-4">
                  <div className="flex-1">
                    <p className="text-xs font-mono text-slate-600 font-medium">{key}</p>
                  </div>
                  <input
                    type="text"
                    value={val !== undefined && val !== null ? String(val) : ''}
                    onChange={(e) => handleChange(key, e.target.value)}
                    className="w-48 px-3 py-1.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-400 text-sm"
                  />
                </div>
              );
            })}
          </div>
        </Card>
      )}
    </div>
  );
}

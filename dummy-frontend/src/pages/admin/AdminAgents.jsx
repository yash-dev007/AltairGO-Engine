import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Play, Bot, CheckCircle, XCircle, Clock, RefreshCw } from 'lucide-react';
import toast from 'react-hot-toast';
import { getDashboardSummary, triggerAgent } from '../../services/api';
import { Button, Badge, Spinner, Card } from '../../components/ui/index';

const AGENT_DEFS = [
  { key: 'destination_validator', label: 'Destination Validator', description: 'Validates pending destination requests using AI.' },
  { key: 'itinerary_qa', label: 'Itinerary QA', description: 'Reviews final itinerary for quality issues.' },
  { key: 'memory_agent', label: 'Memory Agent', description: 'Maintains user preference memory across sessions.' },
  { key: 'token_optimizer', label: 'Token Optimizer', description: 'Estimates Gemini token usage before API calls.' },
  { key: 'mcp_context', label: 'MCP Context Agent', description: 'Fetches live destination context data.' },
  { key: 'web_scraper', label: 'Web Scraper', description: 'Scrapes additional attraction data from web.' },
];

export default function AdminAgents() {
  const [agents, setAgents] = useState({});
  const [loading, setLoading] = useState(true);
  const [triggeringKey, setTriggeringKey] = useState(null);

  const load = () => {
    setLoading(true);
    getDashboardSummary()
      .then((s) => setAgents(s.agents || {}))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleTrigger = async (key) => {
    setTriggeringKey(key);
    try {
      const res = await triggerAgent(key);
      toast.success(`Agent "${key}" triggered`);
    } catch (err) { toast.error(err.message || 'Trigger failed'); }
    finally { setTriggeringKey(null); }
  };

  const statusIcon = (status) => {
    if (!status || status === 'idle') return <Clock className="w-4 h-4 text-slate-400" />;
    if (status === 'ok' || status === 'success') return <CheckCircle className="w-4 h-4 text-green-500" />;
    if (status === 'error') return <XCircle className="w-4 h-4 text-red-500" />;
    return <Clock className="w-4 h-4 text-amber-400" />;
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">AI Agents</h1>
          <p className="text-sm text-slate-500 mt-0.5">Monitor and trigger AI agent tasks</p>
        </div>
        <Button variant="secondary" size="sm" onClick={load} loading={loading}>
          <RefreshCw className="w-4 h-4" /> Refresh
        </Button>
      </div>

      {loading ? (
        <div className="flex justify-center py-8"><Spinner className="text-indigo-600" /></div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {AGENT_DEFS.map((agent) => {
            const agentData = agents[agent.key] || agents[agent.label.toLowerCase().replace(/\s+/g, '_')] || {};
            const status = agentData.status || 'idle';
            const isTriggering = triggeringKey === agent.key;

            return (
              <motion.div key={agent.key} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
                <Card className="p-5 h-full flex flex-col">
                  <div className="flex items-start justify-between mb-3">
                    <div className="w-10 h-10 rounded-xl bg-violet-50 flex items-center justify-center">
                      <Bot className="w-5 h-5 text-violet-600" />
                    </div>
                    <div className="flex items-center gap-1.5">
                      {statusIcon(status)}
                      <Badge
                        status={status === 'ok' || status === 'success' ? 'completed' : status === 'error' ? 'failed' : status === 'running' ? 'processing' : 'pending'}
                      >
                        {status}
                      </Badge>
                    </div>
                  </div>

                  <h3 className="font-semibold text-slate-800 text-sm mb-1">{agent.label}</h3>
                  <p className="text-xs text-slate-500 leading-relaxed flex-1 mb-4">{agent.description}</p>

                  {agentData.last_run && (
                    <p className="text-xs text-slate-400 mb-3">
                      Last run: {new Date(agentData.last_run).toLocaleString('en-IN')}
                    </p>
                  )}

                  {agentData.result && typeof agentData.result === 'string' && (
                    <p className="text-xs text-slate-500 bg-slate-50 p-2 rounded-lg mb-3 line-clamp-2">{agentData.result}</p>
                  )}

                  <Button
                    size="sm"
                    variant="secondary"
                    loading={isTriggering}
                    onClick={() => handleTrigger(agent.key)}
                    className="w-full"
                  >
                    <Play className="w-3.5 h-3.5" /> Run Agent
                  </Button>
                </Card>
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}

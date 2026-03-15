import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { ShieldCheck, Rocket, Eye, EyeOff, Loader2, AlertCircle } from 'lucide-react';

const LoginPage = () => {
    const { login, loading, error } = useAuth();
    const [key, setKey] = useState('');
    const [showKey, setShowKey] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!key.trim()) return;
        await login(key.trim());
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-green-900 flex items-center justify-center p-4">
            <div className="w-full max-w-md">
                {/* Logo */}
                <div className="text-center mb-8">
                    <div className="inline-flex items-center justify-center size-16 bg-green-500 rounded-2xl shadow-xl shadow-green-500/30 mb-4">
                        <Rocket size={28} className="text-white" fill="currentColor" />
                    </div>
                    <h1 className="text-3xl font-extrabold text-white tracking-tight">
                        Altair<span className="text-green-400">GO</span>
                    </h1>
                    <p className="text-slate-400 text-sm mt-1 font-medium">Mission Control Dashboard</p>
                </div>

                {/* Login Card */}
                <div className="bg-white/5 backdrop-blur-xl rounded-3xl border border-white/10 p-8 shadow-2xl">
                    <div className="flex items-center gap-3 mb-6">
                        <div className="size-10 rounded-xl bg-green-500/20 flex items-center justify-center">
                            <ShieldCheck size={20} className="text-green-400" />
                        </div>
                        <div>
                            <h2 className="text-white font-bold text-lg">Admin Access</h2>
                            <p className="text-slate-400 text-xs">Enter your admin key to continue</p>
                        </div>
                    </div>

                    {error && (
                        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center gap-2 text-red-300 text-sm">
                            <AlertCircle size={16} />
                            {error}
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="relative">
                            <input
                                type={showKey ? 'text' : 'password'}
                                value={key}
                                onChange={(e) => setKey(e.target.value)}
                                placeholder="Enter admin key..."
                                className="w-full px-4 py-3.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-500 focus:ring-2 focus:ring-green-500 focus:border-transparent outline-none transition-all text-sm"
                                autoFocus
                                disabled={loading}
                            />
                            <button
                                type="button"
                                onClick={() => setShowKey(!showKey)}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white transition-colors"
                            >
                                {showKey ? <EyeOff size={18} /> : <Eye size={18} />}
                            </button>
                        </div>

                        <button
                            type="submit"
                            disabled={loading || !key.trim()}
                            className="w-full py-3.5 bg-green-500 hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl text-sm font-bold shadow-lg shadow-green-500/25 transition-all active:scale-[0.98] flex items-center justify-center gap-2 uppercase tracking-widest"
                        >
                            {loading ? (
                                <>
                                    <Loader2 size={16} className="animate-spin" />
                                    Authenticating...
                                </>
                            ) : (
                                'Authenticate'
                            )}
                        </button>
                    </form>

                    <p className="text-center text-slate-500 text-[10px] mt-6 uppercase tracking-widest font-bold">
                        Secured by AltairGO Engine
                    </p>
                </div>
            </div>
        </div>
    );
};

export default LoginPage;

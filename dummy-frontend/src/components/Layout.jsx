import React, { useMemo } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import {
    LayoutDashboard,
    Bot,
    Network,
    Database,
    Settings,
    Activity,
    Rocket,
    Compass,
    LogOut,
    Signal,
} from 'lucide-react';

const PAGE_META = {
    '/': 'Mission Control',
    '/planner': 'Autonomous Trip Architect',
    '/agents': 'AI Agent Matrix',
    '/network': 'Network & Core Data',
    '/data': 'Data Laboratory',
    '/settings': 'Intelligence Config',
};

const SidebarItem = ({ icon: SidebarIcon, label, href, active }) => {
    return (
        <Link
            to={href}
            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-semibold transition-all ${active
                ? 'bg-green-50 text-green-600 shadow-sm'
                : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'
                }`}
        >
            <SidebarIcon size={20} />
            {label}
        </Link>
    );
};

const Layout = ({ children }) => {
    const location = useLocation();
    const currentPath = location.pathname;
    const { logout } = useAuth();
    const pageTitle = useMemo(() => PAGE_META[currentPath] || 'Mission Control', [currentPath]);

    return (
        <div className="flex h-screen overflow-hidden bg-white font-sans">
            {/* Sidebar */}
            <aside className="w-64 border-r border-slate-200 bg-white flex flex-col shrink-0">
                <div className="p-6 flex items-center gap-3">
                    <div className="size-8 bg-green-500 rounded-lg flex items-center justify-center text-white shadow-lg shadow-green-500/20">
                        <Rocket size={18} fill="currentColor" />
                    </div>
                    <h1 className="text-xl font-extrabold tracking-tight text-slate-900">
                        Altair<span className="text-green-500">GO</span>
                    </h1>
                </div>

                <nav className="flex-1 px-4 space-y-1">
                    <SidebarItem
                        icon={LayoutDashboard}
                        label="Dashboard"
                        href="/"
                        active={currentPath === '/'}
                    />
                    <SidebarItem
                        icon={Compass}
                        label="Trip Planner"
                        href="/planner"
                        active={currentPath === '/planner'}
                    />
                    <SidebarItem
                        icon={Bot}
                        label="AI Agents"
                        href="/agents"
                        active={currentPath === '/agents'}
                    />
                    <SidebarItem
                        icon={Network}
                        label="Network Hub"
                        href="/network"
                        active={currentPath === '/network'}
                    />
                    <SidebarItem
                        icon={Database}
                        label="Datasets"
                        href="/data"
                        active={currentPath === '/data'}
                    />

                    <div className="pt-4 pb-2 px-3 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                        Settings
                    </div>
                    <SidebarItem
                        icon={Settings}
                        label="Control Panel"
                        href="/settings"
                        active={currentPath === '/settings'}
                    />
                </nav>

                <div className="p-4 border-t border-slate-200 space-y-2">
                    <div className="flex items-center gap-3 p-2 bg-slate-50 rounded-lg">
                        <div className="size-9 rounded-full bg-green-100 flex items-center justify-center text-xs font-bold text-green-700">
                            AD
                        </div>
                        <div className="overflow-hidden flex-1">
                            <p className="text-xs font-bold truncate text-slate-900">Admin</p>
                            <p className="text-[10px] text-slate-500 truncate">Controller</p>
                        </div>
                    </div>
                    <button
                        onClick={logout}
                        className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-bold text-red-500 hover:bg-red-50 transition-colors"
                    >
                        <LogOut size={14} />
                        Sign Out
                    </button>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 flex flex-col min-w-0 overflow-y-auto bg-slate-50">
                <header className="h-16 shrink-0 border-b border-slate-200 bg-white/80 backdrop-blur sticky top-0 z-10 px-8 flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <h2 className="text-lg font-bold text-slate-900">{pageTitle}</h2>
                        <span className="bg-green-100 text-green-700 text-[10px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wider flex items-center gap-1">
                            <Signal size={8} />
                            SYSTEMS ONLINE
                        </span>
                    </div>

                    <div className="flex items-center gap-3 text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                        <Activity size={14} className="text-green-500" />
                        <span>Admin Control Panel</span>
                    </div>
                </header>

                <div className="p-8">
                    {children}
                </div>
            </main>
        </div>
    );
};

export default Layout;

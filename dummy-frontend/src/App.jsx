import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import TravelerLayout from './components/layout/TravelerLayout';
import AdminLayout from './components/layout/AdminLayout';
import { Spinner } from './components/ui/index';

// Pages - Traveler
import Landing from './pages/Landing';
import Discover from './pages/Discover';
import DestinationDetail from './pages/DestinationDetail';
import Planner from './pages/Planner';
import MyTrips from './pages/MyTrips';
import TripDetail from './pages/TripDetail';
import Bookings from './pages/Bookings';
import Expenses from './pages/Expenses';
import DailyBriefing from './pages/DailyBriefing';
import Profile from './pages/Profile';
import SharedTrip from './pages/SharedTrip';

// Pages - Auth
import Login from './pages/auth/Login';
import Register from './pages/auth/Register';

// Pages - Admin
import AdminLogin from './pages/admin/AdminLogin';
import AdminDashboard from './pages/admin/AdminDashboard';
import AdminData from './pages/admin/AdminData';
import AdminUsers from './pages/admin/AdminUsers';
import AdminAgents from './pages/admin/AdminAgents';
import AdminSettings from './pages/admin/AdminSettings';

import './App.css';

function LoadingScreen() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-indigo-50 to-violet-50">
      <div className="text-center">
        <Spinner size="lg" className="text-indigo-600 mx-auto mb-4" />
        <p className="text-slate-500 text-sm">Loading...</p>
      </div>
    </div>
  );
}

function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return <LoadingScreen />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return children;
}

function AdminRoute({ children }) {
  const { isAdmin, loading } = useAuth();
  if (loading) return <LoadingScreen />;
  if (!isAdmin) return <Navigate to="/admin/login" replace />;
  return children;
}

function PublicOnlyRoute({ children }) {
  const { isAuthenticated } = useAuth();
  if (isAuthenticated) return <Navigate to="/trips" replace />;
  return children;
}

function AppRoutes() {
  return (
    <Routes>
      {/* Public traveler routes */}
      <Route path="/" element={<TravelerLayout><Landing /></TravelerLayout>} />
      <Route path="/discover" element={<TravelerLayout><Discover /></TravelerLayout>} />
      <Route path="/destination/:id" element={<TravelerLayout><DestinationDetail /></TravelerLayout>} />
      <Route path="/trip/shared/:token" element={<TravelerLayout><SharedTrip /></TravelerLayout>} />

      {/* Auth routes */}
      <Route path="/login" element={<PublicOnlyRoute><TravelerLayout><Login /></TravelerLayout></PublicOnlyRoute>} />
      <Route path="/register" element={<PublicOnlyRoute><TravelerLayout><Register /></TravelerLayout></PublicOnlyRoute>} />

      {/* Protected traveler routes */}
      <Route path="/planner/*" element={<TravelerLayout><Planner /></TravelerLayout>} />
      <Route path="/trips" element={<ProtectedRoute><TravelerLayout><MyTrips /></TravelerLayout></ProtectedRoute>} />
      <Route path="/trip/:id" element={<ProtectedRoute><TravelerLayout><TripDetail /></TravelerLayout></ProtectedRoute>} />
      <Route path="/trip/:id/bookings" element={<ProtectedRoute><TravelerLayout><Bookings /></TravelerLayout></ProtectedRoute>} />
      <Route path="/trip/:id/expenses" element={<ProtectedRoute><TravelerLayout><Expenses /></TravelerLayout></ProtectedRoute>} />
      <Route path="/trip/:id/briefing/:day" element={<ProtectedRoute><TravelerLayout><DailyBriefing /></TravelerLayout></ProtectedRoute>} />
      <Route path="/profile" element={<ProtectedRoute><TravelerLayout><Profile /></TravelerLayout></ProtectedRoute>} />

      {/* Admin routes */}
      <Route path="/admin/login" element={<AdminLogin />} />
      <Route path="/admin" element={<AdminRoute><AdminLayout><AdminDashboard /></AdminLayout></AdminRoute>} />
      <Route path="/admin/data" element={<AdminRoute><AdminLayout><AdminData /></AdminLayout></AdminRoute>} />
      <Route path="/admin/users" element={<AdminRoute><AdminLayout><AdminUsers /></AdminLayout></AdminRoute>} />
      <Route path="/admin/agents" element={<AdminRoute><AdminLayout><AdminAgents /></AdminLayout></AdminRoute>} />
      <Route path="/admin/settings" element={<AdminRoute><AdminLayout><AdminSettings /></AdminLayout></AdminRoute>} />

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
        <Toaster
          position="top-right"
          toastOptions={{
            duration: 4000,
            style: {
              borderRadius: '12px',
              background: '#1e293b',
              color: '#f8fafc',
              fontSize: '14px',
            },
            success: { iconTheme: { primary: '#6366f1', secondary: '#fff' } },
          }}
        />
      </BrowserRouter>
    </AuthProvider>
  );
}

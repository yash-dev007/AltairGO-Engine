import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Layout from './components/Layout';
import LoginPage from './pages/LoginPage';
import Dashboard from './pages/Dashboard';
import AIAgentHub from './pages/AIAgentHub';
import NetworkHub from './pages/NetworkHub';
import DataLaboratory from './pages/DataLaboratory';
import IntelligenceHub from './pages/IntelligenceHub';
import Planner from './pages/Planner';
import './App.css';

const ProtectedRoute = ({ children }) => {
    const { isAuthenticated } = useAuth();
    if (!isAuthenticated) return <Navigate to="/login" replace />;
    return children;
};

const App = () => {
    return (
        <AuthProvider>
            <Router>
                <Routes>
                    <Route path="/login" element={<LoginGate />} />
                    <Route
                        path="/*"
                        element={
                            <ProtectedRoute>
                                <Layout>
                                    <Routes>
                                        <Route path="/" element={<Dashboard />} />
                                        <Route path="/planner" element={<Planner />} />
                                        <Route path="/agents" element={<AIAgentHub />} />
                                        <Route path="/network" element={<NetworkHub />} />
                                        <Route path="/data" element={<DataLaboratory />} />
                                        <Route path="/settings" element={<IntelligenceHub />} />
                                        <Route path="*" element={<Navigate to="/" replace />} />
                                    </Routes>
                                </Layout>
                            </ProtectedRoute>
                        }
                    />
                </Routes>
            </Router>
        </AuthProvider>
    );
};

/** Redirect to dashboard if already authenticated */
const LoginGate = () => {
    const { isAuthenticated } = useAuth();
    if (isAuthenticated) return <Navigate to="/" replace />;
    return <LoginPage />;
};

export default App;

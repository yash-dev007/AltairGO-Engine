import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

const AuthContext = createContext(null);

const TOKEN_KEY = 'altairgo_admin_token';

export const AuthProvider = ({ children }) => {
    const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) || '');
    const [isAuthenticated, setIsAuthenticated] = useState(!!localStorage.getItem(TOKEN_KEY));
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:5000';

    const login = useCallback(async (adminKey) => {
        setLoading(true);
        setError('');
        try {
            const resp = await fetch(`${apiBase}/api/admin/verify-key`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ key: adminKey }),
            });
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.error || 'Authentication failed');
            localStorage.setItem(TOKEN_KEY, data.token);
            setToken(data.token);
            setIsAuthenticated(true);
            return true;
        } catch (err) {
            setError(err.message);
            return false;
        } finally {
            setLoading(false);
        }
    }, [apiBase]);

    const logout = useCallback(() => {
        localStorage.removeItem(TOKEN_KEY);
        setToken('');
        setIsAuthenticated(false);
    }, []);

    // Auto-validate token on mount
    useEffect(() => {
        if (token) {
            fetch(`${apiBase}/api/admin/stats`, {
                headers: { Authorization: `Bearer ${token}` },
            }).then(res => {
                if (res.status === 401 || res.status === 422) {
                    logout();
                }
            }).catch(() => {});
        }
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    const value = {
        token,
        isAuthenticated,
        loading,
        error,
        login,
        logout,
        apiBase,
    };

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error('useAuth must be used within AuthProvider');
    return ctx;
};

export default AuthContext;

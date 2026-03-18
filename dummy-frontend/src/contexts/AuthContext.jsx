import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import {
  getToken, getAdminToken, setToken, setAdminToken,
  clearToken, clearAdminToken,
  login as apiLogin, register as apiRegister, getMe, adminLogin as apiAdminLogin,
} from '../services/api';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [loading, setLoading] = useState(true);

  // Hydrate on mount
  useEffect(() => {
    const hydrate = async () => {
      const token = getToken();
      const adminToken = getAdminToken();
      if (adminToken) {
        setIsAdmin(true);
        setIsAuthenticated(true);
      }
      if (token) {
        try {
          const me = await getMe();
          setUser(me);
          setIsAuthenticated(true);
        } catch {
          clearToken();
        }
      }
      setLoading(false);
    };
    hydrate();
  }, []);

  // Listen for unauthorized events
  useEffect(() => {
    const handler = (e) => {
      if (e.detail?.admin) {
        setIsAdmin(false);
        if (!getToken()) setIsAuthenticated(false);
      } else {
        setUser(null);
        setIsAuthenticated(false);
      }
    };
    window.addEventListener('ag:unauthorized', handler);
    return () => window.removeEventListener('ag:unauthorized', handler);
  }, []);

  const login = useCallback(async (email, pw) => {
    const data = await apiLogin(email, pw);
    setToken(data.token);
    if (data.refresh_token) localStorage.setItem('ag_refresh_token', data.refresh_token);
    setUser(data.user);
    setIsAuthenticated(true);
    return data;
  }, []);

  const register = useCallback(async (name, email, pw) => {
    const data = await apiRegister(name, email, pw);
    setToken(data.token);
    if (data.refresh_token) localStorage.setItem('ag_refresh_token', data.refresh_token);
    setUser(data.user);
    setIsAuthenticated(true);
    return data;
  }, []);

  const logout = useCallback(() => {
    clearToken();
    localStorage.removeItem('ag_refresh_token');
    setUser(null);
    setIsAuthenticated(isAdmin); // keep admin session if active
  }, [isAdmin]);

  const adminLogin = useCallback(async (key) => {
    const data = await apiAdminLogin(key);
    setAdminToken(data.token);
    setIsAdmin(true);
    setIsAuthenticated(true);
    return data;
  }, []);

  const adminLogout = useCallback(() => {
    clearAdminToken();
    setIsAdmin(false);
    if (!getToken()) {
      setIsAuthenticated(false);
      setUser(null);
    }
  }, []);

  return (
    <AuthContext.Provider value={{
      user, isAuthenticated, isAdmin, loading,
      login, register, logout, adminLogin, adminLogout,
    }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
};

export default AuthContext;

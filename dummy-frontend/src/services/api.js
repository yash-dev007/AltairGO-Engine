const BASE = import.meta.env.VITE_API_URL || '';

export function getToken() { return localStorage.getItem('ag_token'); }
export function getAdminToken() { return localStorage.getItem('ag_admin_token'); }
export function setToken(t) { localStorage.setItem('ag_token', t); }
export function setAdminToken(t) { localStorage.setItem('ag_admin_token', t); }
export function clearToken() { localStorage.removeItem('ag_token'); }
export function clearAdminToken() { localStorage.removeItem('ag_admin_token'); }

async function req(path, opts = {}) {
  const { admin = false, body, method = body != null ? 'POST' : 'GET', headers = {} } = opts;
  const token = admin ? getAdminToken() : getToken();
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
    ...(body != null ? { body: JSON.stringify(body) } : {}),
  });
  if (res.status === 401) {
    if (admin) clearAdminToken(); else clearToken();
    window.dispatchEvent(new CustomEvent('ag:unauthorized', { detail: { admin } }));
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(data.error || data.message || 'Request failed'), { status: res.status, data });
  return data;
}

// ── Auth ──────────────────────────────────────────────────────────────────
export const register = (name, email, pw) =>
  req('/auth/register', { body: { name, email, password: pw } });

export const login = (email, pw) =>
  req('/auth/login', { body: { email, password: pw } });

export const refreshToken = () =>
  req('/auth/refresh', { method: 'POST' });

export const getMe = () => req('/auth/me');

// ── Admin Auth ────────────────────────────────────────────────────────────
export const adminLogin = (key) =>
  req('/api/admin/verify-key', { body: { key } });

// ── Profile ───────────────────────────────────────────────────────────────
export const getProfile = () => req('/api/user/profile');
export const updateProfile = (data) => req('/api/user/profile', { method: 'PUT', body: data });
export const deleteAccount = (password) => req('/api/user/account', { method: 'DELETE', body: { password } });

// ── Search ────────────────────────────────────────────────────────────────
export const search = (q, type) => {
  const params = new URLSearchParams({ q });
  if (type) params.append('type', type);
  return req(`/api/search?${params}`);
};

// ── Destinations ──────────────────────────────────────────────────────────
export const getDestinations = (params = {}) => {
  const q = new URLSearchParams(params).toString();
  return req(`/destinations${q ? `?${q}` : ''}`);
};
export const getDestination = (id) => req(`/destinations/${id}`);
export const getCountries = () => req('/countries');

// ── Discover ──────────────────────────────────────────────────────────────
export const getRecommendations = (params = {}) => {
  const q = new URLSearchParams(params).toString();
  return req(`/api/discover/recommend${q ? `?${q}` : ''}`);
};
export const getBestTime = (destId) => req(`/api/discover/best-time/${destId}`);
export const isGoodTime = (destId, month) =>
  req(`/api/discover/is-good-time?dest_id=${destId}&month=${month}`);
export const estimateBudget = (params) => req('/api/discover/estimate-budget', { body: params });
export const compareDestinations = (ids) => req('/api/discover/compare', { body: { destination_ids: ids } });

// ── Trips ─────────────────────────────────────────────────────────────────
export const generateItinerary = (params) => req('/generate-itinerary', { body: params });
export const getItineraryStatus = (jobId) => req(`/get-itinerary-status/${jobId}`);
export const saveTrip = (data) => req('/api/save-trip', { body: data });
export const getUserTrips = (page = 1) => req(`/api/user/trips?page=${page}`);
export const getTrip = (id) => req(`/get-trip/${id}`);
export const generateVariants = (id) => req(`/api/trip/${id}/variants`, { method: 'POST' });

// ── Sharing ───────────────────────────────────────────────────────────────
export const shareTrip = (tripId) => req(`/api/trip/${tripId}/share`, { method: 'POST' });
export const revokeShare = (tripId) => req(`/api/trip/${tripId}/share`, { method: 'DELETE' });
export const getSharedTrip = (token) => req(`/api/shared/${token}`);

// ── Booking ───────────────────────────────────────────────────────────────
export const getBookingPlan = (tripId) => req(`/api/trip/${tripId}/booking-plan`);
export const approveBooking = (id) => req(`/api/booking/${id}/approve`, { method: 'POST' });
export const rejectBooking = (id) => req(`/api/booking/${id}/reject`, { method: 'POST' });
export const executeAllBookings = (tripId) =>
  req(`/api/trip/${tripId}/booking-plan/execute-all`, { method: 'POST' });
export const cancelBooking = (id) => req(`/api/booking/${id}/cancel`, { method: 'POST' });
export const getBookings = (tripId) => req(`/api/trip/${tripId}/bookings`);
export const customizeBooking = (id, data) =>
  req(`/api/booking/${id}/customize`, { method: 'PUT', body: data });
export const addCustomBooking = (tripId, data) =>
  req(`/api/trip/${tripId}/booking-plan/add-custom`, { body: data });

// ── Expenses ──────────────────────────────────────────────────────────────
export const addExpense = (tripId, data) => req(`/api/trip/${tripId}/expense`, { body: data });
export const getExpenses = (tripId) => req(`/api/trip/${tripId}/expenses`);
export const deleteExpense = (id) => req(`/api/expense/${id}`, { method: 'DELETE' });

// ── Trip Tools ────────────────────────────────────────────────────────────
export const getTripReadiness = (tripId) => req(`/api/trip/${tripId}/readiness`);
export const getDailyBriefing = (tripId, day) => req(`/api/trip/${tripId}/daily-briefing/${day}`);
export const swapActivity = (tripId, data) =>
  req(`/api/trip/${tripId}/activity/swap`, { method: 'POST', body: data });
export const getNextTripIdeas = (tripId) => req(`/api/trip/${tripId}/next-trip-ideas`);

// ── Trip Editor ───────────────────────────────────────────────────────────
export const getHotelOptions = (tripId, params = {}) => {
  const q = new URLSearchParams(params).toString();
  return req(`/api/trip/${tripId}/hotel-options${q ? `?${q}` : ''}`);
};
export const changeHotel = (tripId, data) =>
  req(`/api/trip/${tripId}/hotel`, { method: 'PUT', body: data });
export const addActivity = (tripId, day, data) =>
  req(`/api/trip/${tripId}/day/${day}/activity/add`, { body: data });
export const removeActivity = (tripId, day, name) =>
  req(`/api/trip/${tripId}/day/${day}/activity/remove`, { method: 'DELETE', body: { name } });
export const editActivity = (tripId, day, data) =>
  req(`/api/trip/${tripId}/day/${day}/activity/edit`, { method: 'PUT', body: data });
export const reorderActivities = (tripId, day, order) =>
  req(`/api/trip/${tripId}/day/${day}/reorder`, { method: 'PUT', body: { order } });
export const saveTripNotes = (tripId, data) =>
  req(`/api/trip/${tripId}/notes`, { method: 'PUT', body: data });

// ── Admin ─────────────────────────────────────────────────────────────────
export const getAdminStats = () => req('/api/admin/stats', { admin: true });
export const getDashboardSummary = () => req('/api/ops/summary', { admin: true });
export const triggerJob = (name) =>
  req('/api/ops/trigger-job', { body: { job_name: name }, admin: true });
export const triggerAgent = (key) =>
  req('/api/ops/trigger-agent', { body: { agent_key: key }, admin: true });
export const getEngineConfig = () => req('/api/ops/engine-config', { admin: true });
export const updateEngineConfig = (data) =>
  req('/api/ops/engine-config', { method: 'POST', body: data, admin: true });

export const getAdminDestinations = (p = 1) =>
  req(`/api/admin/destinations?page=${p}`, { admin: true });
export const createDestination = (data) =>
  req('/api/admin/destinations', { body: data, admin: true });
export const updateDestination = (id, data) =>
  req(`/api/admin/destinations/${id}`, { method: 'PUT', body: data, admin: true });
export const deleteDestination = (id) =>
  req(`/api/admin/destinations/${id}`, { method: 'DELETE', admin: true });

export const getAdminUsers = (p = 1) =>
  req(`/api/admin/users?page=${p}`, { admin: true });
export const getAdminTrips = (p = 1) =>
  req(`/api/admin/trips?page=${p}`, { admin: true });

export const getDestinationRequests = () =>
  req('/api/admin/requests', { admin: true });
export const approveRequest = (id) =>
  req(`/api/admin/requests/${id}/approve`, { method: 'POST', admin: true });
export const rejectRequest = (id) =>
  req(`/api/admin/requests/${id}/reject`, { method: 'POST', admin: true });

// ── SSE Helper ────────────────────────────────────────────────────────────
export const getLiveMetricsURL = () => {
  const token = getAdminToken();
  const base = import.meta.env.VITE_API_URL || '';
  return `${base}/api/ops/live-metrics${token ? `?token=${token}` : ''}`;
};

const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:5000';

/**
 * Get the stored admin JWT token.
 */
const getToken = () => localStorage.getItem('altairgo_admin_token') || '';

/**
 * Authenticated fetch wrapper — attaches JWT Bearer token and handles 401s.
 */
const fetchWithAuth = async (endpoint, options = {}) => {
    const token = getToken();
    const url = `${API_BASE}${endpoint.startsWith('/') ? '' : '/'}${endpoint}`;
    const response = await fetch(url, {
        ...options,
        headers: {
            ...options.headers,
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
    });

    if (response.status === 401 || response.status === 422) {
        // Token expired or invalid — trigger logout
        localStorage.removeItem('altairgo_admin_token');
        window.location.reload();
        throw new Error('Session expired');
    }

    if (!response.ok) {
        const error = await response.json().catch(() => ({ error: 'Unknown error' }));
        throw new Error(error.error || `HTTP error! status: ${response.status}`);
    }

    return response.json();
};

export const api = {
    // ── Dashboard ────────────────────────────────────────────
    getOpsSummary: () => fetchWithAuth('/api/ops/summary'),
    getAdminStats: () => fetchWithAuth('/api/admin/stats'),
    getEngineConfig: () => fetchWithAuth('/api/ops/engine-config'),

    // ── Job Management ───────────────────────────────────────
    triggerJob: (jobName, params = {}) =>
        fetchWithAuth('/api/ops/trigger-job', {
            method: 'POST',
            body: JSON.stringify({ job_name: jobName, ...params }),
        }),

    getJobStatus: (taskId) => fetchWithAuth(`/api/ops/job-status/${taskId}`),

    // ── Destination Management ───────────────────────────────
    getDestinations: (page = 1, pageSize = 20) =>
        fetchWithAuth(`/api/admin/destinations?page=${page}&page_size=${pageSize}`),

    createDestination: (data) =>
        fetchWithAuth('/api/admin/destinations', {
            method: 'POST',
            body: JSON.stringify(data),
        }),

    updateDestination: (destId, data) =>
        fetchWithAuth(`/api/admin/destinations/${destId}`, {
            method: 'PUT',
            body: JSON.stringify(data),
        }),

    deleteDestination: (destId) =>
        fetchWithAuth(`/api/admin/destinations/${destId}`, {
            method: 'DELETE',
        }),

    // ── Destination Requests ─────────────────────────────────
    getDestinationRequests: (page = 1) =>
        fetchWithAuth(`/api/admin/destination-requests?page=${page}`),

    approveRequest: (requestId) =>
        fetchWithAuth(`/api/admin/destination-requests/${requestId}/approve`, {
            method: 'POST',
        }),

    rejectRequest: (requestId) =>
        fetchWithAuth(`/api/admin/destination-requests/${requestId}/reject`, {
            method: 'POST',
        }),

    // ── User Management ──────────────────────────────────────
    getUsers: (page = 1, pageSize = 20) =>
        fetchWithAuth(`/api/admin/users?page=${page}&page_size=${pageSize}`),

    deleteUser: (userId) =>
        fetchWithAuth(`/api/admin/users/${userId}`, {
            method: 'DELETE',
        }),

    // ── Trip Management ──────────────────────────────────────
    getTrips: (page = 1, pageSize = 20) =>
        fetchWithAuth(`/api/admin/trips?page=${page}&page_size=${pageSize}`),

    getTrip: (tripId) => fetchWithAuth(`/api/admin/trips/${tripId}`),

    deleteTrip: (tripId) =>
        fetchWithAuth(`/api/admin/trips/${tripId}`, {
            method: 'DELETE',
        }),

    updateEngineConfig: (config) =>
        fetchWithAuth('/api/ops/engine-config', {
            method: 'POST',
            body: JSON.stringify(config),
        }),

    triggerAgent: (agentKey) =>
        fetchWithAuth('/api/ops/trigger-agent', {
            method: 'POST',
            body: JSON.stringify({ agent_key: agentKey }),
        }),

    // ── SSE Stream ───────────────────────────────────────────
    getLiveMetricsURL: () => `${API_BASE}/api/ops/live-metrics`,
    getToken,
};

export default api;

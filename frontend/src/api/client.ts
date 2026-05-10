import axios from 'axios';
import { useAuthStore } from '../store/authStore';

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8001',
  withCredentials: true, // BUG-06: Send httpOnly cookies for refresh token
  headers: {
    'Content-Type': 'application/json'
  }
});

// ── Request interceptor — attach JWT from memory store ───────────────────────
// BUG-B3: Token is read from Zustand state, NOT localStorage.
apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ── Response interceptor — silent refresh on 401 ─────────────────────────────
// BUG-06: Refresh using the httpOnly cookie; no localStorage reads/writes.
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value?: unknown) => void;
  reject: (reason?: unknown) => void;
}> = [];

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Only attempt refresh on 401 and not already retrying
    if (error.response?.status === 401 && !originalRequest._retry) {
      // Don't refresh on the refresh endpoint itself
      if (originalRequest.url?.includes('/auth/refresh')) {
        useAuthStore.getState().logout();
        return Promise.reject(error);
      }

      if (isRefreshing) {
        // Queue this request while refresh is in progress
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return apiClient(originalRequest);
        }).catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        // BUG-06: Attempt silent refresh using httpOnly cookie
        const refreshRes = await axios.post(
          `${apiClient.defaults.baseURL}/auth/refresh`,
          {},
          { withCredentials: true }
        );

        const newToken = refreshRes.data.access_token;
        const user = refreshRes.data.user;

        // BUG-B3: Write to Zustand memory ONLY — never localStorage
        if (user) {
          useAuthStore.getState().login(newToken, user);
        } else {
          useAuthStore.getState().setToken(newToken);
        }

        processQueue(null, newToken);

        // Retry the original request with new token
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        // Refresh failed — force logout
        useAuthStore.getState().logout();
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

// ── BUG-B3: Silent refresh on page load ──────────────────────────────────────
// Since the access token is no longer in localStorage, we must recover it from
// the httpOnly refresh-token cookie every time the page loads.
// This runs once at module load (before any component mounts) and marks the
// store as hydrated when done so ProtectedRoute can make a correct decision.
(async () => {
  try {
    const refreshRes = await axios.post(
      `${apiClient.defaults.baseURL}/auth/refresh`,
      {},
      { withCredentials: true }
    );
    const newToken = refreshRes.data.access_token;
    const user = refreshRes.data.user;
    if (user) {
      useAuthStore.getState().login(newToken, user);
    } else {
      useAuthStore.getState().setToken(newToken);
    }
  } catch {
    // No valid refresh token cookie — user is not logged in.
    // Mark as hydrated so ProtectedRoute redirects cleanly to /login.
    useAuthStore.setState({ isHydrated: true, isAuthenticated: false });
  }
})();

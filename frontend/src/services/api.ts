import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios';

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
  return match ? decodeURIComponent(match[2]) : null;
}

export const api = axios.create({
  baseURL: '/api',
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor: attach CSRF token if present
api.interceptors.request.use((config) => {
  const csrfToken = getCookie('csrf_token');
  if (csrfToken && config.headers) {
    config.headers['X-CSRF-Token'] = csrfToken;
  }
  return config;
});

// ─── Auto-Refresh Interceptor ──────────────────────────────────────────────
// When a 401 is received, attempt a silent token refresh via POST /api/auth/refresh.
// If the refresh succeeds, the original request is retried transparently.
// If the refresh fails (refresh_token also expired), the user is redirected to /login.

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value: unknown) => void;
  reject: (reason?: unknown) => void;
}> = [];

function processQueue(error: unknown) {
  failedQueue.forEach((p) => {
    if (error) {
      p.reject(error);
    } else {
      p.resolve(undefined);
    }
  });
  failedQueue = [];
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<{ detail?: string }>) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // Only attempt refresh for 401 responses that haven't been retried
    // and are not from auth endpoints themselves
    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes('/auth/refresh') &&
      !originalRequest.url?.includes('/auth/login')
    ) {
      if (isRefreshing) {
        // Queue requests while a refresh is in progress
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then(() => api(originalRequest)).catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        // Attempt silent token refresh
        await axios.post('/api/auth/refresh', {}, { withCredentials: true });

        // Refresh succeeded — update CSRF token from new cookie and retry
        processQueue(null);
        return api(originalRequest);
      } catch (refreshError) {
        // Refresh failed — clear queue and redirect to login
        processQueue(refreshError);
        if (!window.location.pathname.startsWith('/login')) {
          window.location.href = '/login';
        }
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

export default api;

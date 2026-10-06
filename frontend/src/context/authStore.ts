import { create } from 'zustand';
import api from '../services/api';
import type { User, UserRole } from '../types';

interface AuthState {
  user: User | null;
  role: UserRole | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  role: null,
  isAuthenticated: false,
  isLoading: true,
  error: null,

  login: async (username: string, password: string) => {
    set({ isLoading: true, error: null });
    try {
      const response = await api.post('/auth/login', { username, password });
      const data = response.data;
      const user: User = {
        id: data.user_id,
        username: data.username,
        full_name: data.full_name,
        role: data.role,
        is_active: true,
      };
      set({
        user,
        role: data.role,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
    } catch (err: any) {
      const message = err.response?.data?.detail || 'فشل تسجيل الدخول. تحقق من اسم المستخدم وكلمة المرور.';
      set({ error: message, isLoading: false, isAuthenticated: false });
      throw new Error(message);
    }
  },

  logout: async () => {
    try {
      await api.post('/auth/logout');
    } catch (e) {
      // Ignore network errors on logout
    } finally {
      set({
        user: null,
        role: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
      });
    }
  },

  checkAuth: async () => {
    set({ isLoading: true });
    try {
      const response = await api.get('/auth/me');
      const user: User = response.data;
      set({
        user,
        role: user.role,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
    } catch (err) {
      set({
        user: null,
        role: null,
        isAuthenticated: false,
        isLoading: false,
      });
    }
  },

  clearError: () => set({ error: null }),
}));

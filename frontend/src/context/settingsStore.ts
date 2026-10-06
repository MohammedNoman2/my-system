import { create } from 'zustand';
import api from '../services/api';
import type { OfficeSettings } from '../types';

interface SettingsState {
  office: OfficeSettings | null;
  isLoading: boolean;
  error: string | null;

  fetchOfficeSettings: () => Promise<void>;
  updateOfficeSettings: (data: Partial<OfficeSettings>) => Promise<void>;
  uploadLogo: (fileOrData: File | string) => Promise<void>;
}

export const useSettingsStore = create<SettingsState>((set) => ({
  office: null,
  isLoading: false,
  error: null,

  fetchOfficeSettings: async () => {
    set({ isLoading: true, error: null });
    try {
      const res = await api.get('/settings/office');
      set({ office: res.data, isLoading: false });
    } catch (err: any) {
      set({
        isLoading: false,
        error: err.response?.data?.detail || 'فشل تحميل بيانات المكتب',
      });
    }
  },

  updateOfficeSettings: async (data: Partial<OfficeSettings>) => {
    set({ isLoading: true, error: null });
    try {
      const res = await api.put('/settings/office', data);
      set({ office: res.data, isLoading: false });
    } catch (err: any) {
      const message = err.response?.data?.detail || 'فشل تحديث الإعدادات';
      set({ isLoading: false, error: message });
      throw new Error(message);
    }
  },

  uploadLogo: async (fileOrData: File | string) => {
    set({ isLoading: true, error: null });
    try {
      let res;
      if (typeof fileOrData === 'string') {
        res = await api.post('/settings/logo', { logo_data: fileOrData });
      } else {
        const formData = new FormData();
        formData.append('file', fileOrData);
        res = await api.post('/settings/logo', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
      }
      set({ office: res.data, isLoading: false });
    } catch (err: any) {
      const message = err.response?.data?.detail || 'فشل رفع الشعار';
      set({ isLoading: false, error: message });
      throw new Error(message);
    }
  },
}));

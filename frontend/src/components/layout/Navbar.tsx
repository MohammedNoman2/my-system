import React, { useEffect } from 'react';
import { Menu, Building } from 'lucide-react';
import { useUIStore } from '../../context/uiStore';
import { useSettingsStore } from '../../context/settingsStore';
import { useAuthStore } from '../../context/authStore';
import { ShiftWidget } from '../cash/ShiftWidget';

export function Navbar() {
  const toggleSidebar = useUIStore((state) => state.toggleSidebar);
  const { office, fetchOfficeSettings } = useSettingsStore();
  const { user } = useAuthStore();

  useEffect(() => {
    if (!office) {
      fetchOfficeSettings();
    }
  }, [office, fetchOfficeSettings]);

  return (
    <header className="h-16 bg-white border-b border-slate-200/80 px-4 sm:px-6 flex items-center justify-between shadow-2xs sticky top-0 z-30">
      {/* Right side: Mobile Menu Button & Brand */}
      <div className="flex items-center gap-3">
        <button
          onClick={toggleSidebar}
          className="md:hidden p-2 rounded-lg text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-colors"
          aria-label="فتح القائمة الجانبية"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-2">
          {office?.logo_image_url ? (
            <img
              src={office.logo_image_url}
              alt={office.office_name}
              className="h-8 w-auto object-contain"
            />
          ) : (
            <Building className="w-5 h-5 text-[#1e3a8a] hidden sm:block" />
          )}
          <span className="font-bold text-slate-800 text-sm sm:text-base hidden sm:inline">
            {office?.office_name || 'منصة الحجوزات المتقدمة (ARP)'}
          </span>
        </div>
      </div>

      {/* Left side: Shift Widget & User Info */}
      <div className="flex items-center gap-4">
        <ShiftWidget />
        <div className="flex items-center gap-3 border-r border-slate-200 pr-4">
          <div className="text-left">
            <p className="text-xs text-slate-400">مرحباً بك</p>
            <p className="text-xs sm:text-sm font-semibold text-slate-700">
              {user?.full_name || user?.username}
            </p>
          </div>
          <div className="w-9 h-9 rounded-full bg-[#1e3a8a]/10 border border-[#1e3a8a]/20 flex items-center justify-center font-bold text-sm text-[#1e3a8a]">
            {user?.full_name ? user.full_name.charAt(0) : 'م'}
          </div>
        </div>
      </div>
    </header>
  );
}

import React, { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  CalendarCheck,
  Receipt,
  Users,
  Building2,
  BarChart3,
  Settings,
  LogOut,
  X,
  Ticket,
  ChevronDown,
  Search,
  PlusCircle,
} from 'lucide-react';
import { useAuthStore } from '../../context/authStore';
import { useUIStore } from '../../context/uiStore';
import { useSettingsStore } from '../../context/settingsStore';
import { cn } from '../../utils/cn';
import type { UserRole } from '../../types';

interface NavItem {
  title: string;
  href: string;
  icon: React.ReactNode;
  allowedRoles: UserRole[];
}

const navItems: NavItem[] = [
  {
    title: 'لوحة التحكم',
    href: '/dashboard',
    icon: <LayoutDashboard className="w-5 h-5" />,
    allowedRoles: ['admin', 'employee', 'accountant'],
  },
  {
    title: 'المالية والسندات',
    href: '/finance',
    icon: <Receipt className="w-5 h-5" />,
    allowedRoles: ['admin', 'accountant', 'employee'], // Employee can access vouchers
  },
  {
    title: 'العملاء',
    href: '/customers',
    icon: <Users className="w-5 h-5" />,
    allowedRoles: ['admin', 'employee', 'accountant'],
  },
  {
    title: 'الموردون',
    href: '/suppliers',
    icon: <Building2 className="w-5 h-5" />,
    allowedRoles: ['admin', 'accountant'],
  },
  {
    title: 'التقارير',
    href: '/reports',
    icon: <BarChart3 className="w-5 h-5" />,
    allowedRoles: ['admin', 'employee', 'accountant'], // Employee limited to their report (§3)
  },
  {
    title: 'الإعدادات والمستخدمين',
    href: '/settings',
    icon: <Settings className="w-5 h-5" />,
    allowedRoles: ['admin'], // Admin only (§3)
  },
];

export function Sidebar() {
  const location = useLocation();
  const { user, role, logout } = useAuthStore();
  const { sidebarOpen, setSidebarOpen } = useUIStore();
  const { office } = useSettingsStore();

  const isTicketsActive =
    location.pathname.startsWith('/bookings') || location.pathname.includes('/tickets');
  const [ticketsMenuOpen, setTicketsMenuOpen] = useState(true);

  const roleLabels: Record<UserRole, { label: string; badgeClass: string }> = {
    admin: { label: 'مدير النظام', badgeClass: 'bg-red-100 text-red-800' },
    accountant: { label: 'محاسب', badgeClass: 'bg-amber-100 text-amber-800' },
    employee: { label: 'موظف حجوزات', badgeClass: 'bg-blue-100 text-blue-800' },
  };

  const filteredItems = navItems.filter((item) =>
    role ? item.allowedRoles.includes(role) : false
  );

  const canManageTickets = role === 'admin' || role === 'employee';

  return (
    <>
      {/* Mobile Backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-slate-900/60 backdrop-blur-xs md:hidden transition-opacity"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={cn(
          'fixed top-0 right-0 bottom-0 z-40 w-64 bg-[#1e293b] text-white flex flex-col transition-transform duration-300 ease-in-out md:translate-x-0 md:static',
          sidebarOpen ? 'translate-x-0' : 'translate-x-full'
        )}
      >
        {/* Header / Brand */}
        <div className="h-16 flex items-center justify-between px-5 border-b border-slate-700/60">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-tr from-[#1e3a8a] to-blue-500 flex items-center justify-center font-bold text-lg text-white shadow-sm overflow-hidden shrink-0">
              {office?.logo_data || office?.logo_image_url ? (
                <img
                  src={office.logo_data || office.logo_image_url || ''}
                  alt="شعار المكتب"
                  className="w-full h-full object-contain p-0.5 bg-white/10"
                />
              ) : (
                <span>ARP</span>
              )}
            </div>
            <div className="overflow-hidden">
              <h1 className="text-sm font-bold text-white truncate">
                {office?.office_name || 'عالم النقل'}
              </h1>
              <p className="text-[11px] text-slate-400 truncate">
                {office?.tagline || 'للسفريات والنقل البري'}
              </p>
            </div>
          </div>
          {/* Mobile close button */}
          <button
            onClick={() => setSidebarOpen(false)}
            className="md:hidden p-1.5 rounded-lg text-slate-400 hover:bg-slate-800 hover:text-white"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
          {/* Dashboard Link */}
          <NavLink
            to="/dashboard"
            onClick={() => setSidebarOpen(false)}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors',
                isActive
                  ? 'bg-[#1e3a8a] text-white shadow-sm'
                  : 'text-slate-300 hover:bg-slate-800/80 hover:text-white'
              )
            }
          >
            <LayoutDashboard className="w-5 h-5 shrink-0" />
            <span className="truncate">لوحة التحكم</span>
          </NavLink>

          {/* Tickets Management Dropdown */}
          {canManageTickets && (
            <div className="space-y-1">
              <button
                type="button"
                onClick={() => setTicketsMenuOpen((prev) => !prev)}
                className={cn(
                  'w-full flex items-center justify-between px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors text-right',
                  isTicketsActive
                    ? 'bg-[#1e3a8a]/40 text-blue-200 border border-blue-500/30'
                    : 'text-slate-300 hover:bg-slate-800/80 hover:text-white'
                )}
              >
                <div className="flex items-center gap-3">
                  <Ticket className="w-5 h-5 text-blue-400 shrink-0" />
                  <span className="font-semibold">إدارة التذاكر</span>
                </div>
                <ChevronDown
                  className={cn(
                    'w-4 h-4 text-slate-400 transition-transform duration-200',
                    ticketsMenuOpen ? 'rotate-180 text-blue-300' : ''
                  )}
                />
              </button>

              {ticketsMenuOpen && (
                <div className="pr-6 pl-2 space-y-1 py-1 bg-slate-900/30 rounded-lg border-r-2 border-blue-500/60 my-1">
                  <NavLink
                    to="/bookings"
                    onClick={() => setSidebarOpen(false)}
                    className={({ isActive }) =>
                      cn(
                        'flex items-center gap-2.5 px-3 py-2 rounded-md text-xs font-medium transition-colors',
                        isActive && !location.pathname.includes('/search')
                          ? 'bg-blue-600/30 text-white font-bold'
                          : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                      )
                    }
                  >
                    <PlusCircle className="w-3.5 h-3.5 text-blue-400" />
                    <span>حجز جديد (النماذج الموحدة)</span>
                  </NavLink>
                  <NavLink
                    to="/dashboard/tickets/search"
                    onClick={() => setSidebarOpen(false)}
                    className={({ isActive }) =>
                      cn(
                        'flex items-center gap-2.5 px-3 py-2 rounded-md text-xs font-medium transition-colors',
                        isActive
                          ? 'bg-blue-600/30 text-white font-bold'
                          : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                      )
                    }
                  >
                    <Search className="w-3.5 h-3.5 text-emerald-400" />
                    <span>البحث عن تذكرة (10 أعمدة)</span>
                  </NavLink>
                </div>
              )}
            </div>
          )}

          {/* Remaining Links */}
          {filteredItems
            .filter((item) => item.href !== '/dashboard')
            .map((item) => (
              <NavLink
                key={item.href}
                to={item.href}
                onClick={() => setSidebarOpen(false)}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-[#1e3a8a] text-white shadow-sm'
                      : 'text-slate-300 hover:bg-slate-800/80 hover:text-white'
                  )
                }
              >
                <span className="shrink-0">{item.icon}</span>
                <span className="truncate">{item.title}</span>
              </NavLink>
            ))}
        </nav>

        {/* User Card & Logout */}
        <div className="p-3 border-t border-slate-700/60 bg-slate-900/40">
          <div className="flex items-center justify-between gap-2 px-2 py-2">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-white truncate">
                {user?.full_name || user?.username || 'مستخدم'}
              </p>
              {role && (
                <span
                  className={cn(
                    'inline-block text-[10px] font-bold px-2 py-0.5 rounded-full mt-0.5',
                    roleLabels[role].badgeClass
                  )}
                >
                  {roleLabels[role].label}
                </span>
              )}
            </div>
            <button
              onClick={() => logout()}
              title="تسجيل الخروج"
              className="p-2 rounded-lg text-slate-400 hover:bg-red-950/40 hover:text-red-400 transition-colors"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}

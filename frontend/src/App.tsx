import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout';
import { ProtectedRoute } from './components/layout/ProtectedRoute';
import { LoginPage } from './pages/auth/LoginPage';
import { ForgotPasswordPage } from './pages/auth/ForgotPasswordPage';
import { ResetPasswordPage } from './pages/auth/ResetPasswordPage';
import { DashboardPage } from './pages/dashboard/DashboardPage';
import { BookingsPage } from './pages/bookings/BookingsPage';
import { TicketSearchPage } from './pages/bookings/TicketSearchPage';
import { FinancePage } from './pages/finance/FinancePage';
import { CustomersPage } from './pages/customers/CustomersPage';
import { SuppliersPage } from './pages/suppliers/SuppliersPage';
import { ReportsPage } from './pages/reports/ReportsPage';
import { SettingsPage } from './pages/settings/SettingsPage';

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public Auth Routes */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />

        {/* Protected App Routes */}
        <Route
          element={
            <ProtectedRoute>
              <AppLayout />
            </ProtectedRoute>
          }
        >
          <Route path="/dashboard" element={<DashboardPage />} />

          {/* Bookings & Unified Ticket Management: Admin & Employee */}
          <Route
            path="/bookings"
            element={
              <ProtectedRoute allowedRoles={['admin', 'employee']}>
                <BookingsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/dashboard/tickets/search"
            element={
              <ProtectedRoute allowedRoles={['admin', 'employee']}>
                <TicketSearchPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/tickets/search"
            element={
              <ProtectedRoute allowedRoles={['admin', 'employee']}>
                <TicketSearchPage />
              </ProtectedRoute>
            }
          />

          {/* Finance: Admin & Accountant */}
          <Route
            path="/finance"
            element={
              <ProtectedRoute allowedRoles={['admin', 'accountant']}>
                <FinancePage />
              </ProtectedRoute>
            }
          />

          {/* Customers: All */}
          <Route path="/customers" element={<CustomersPage />} />

          {/* Suppliers: Admin & Accountant */}
          <Route
            path="/suppliers"
            element={
              <ProtectedRoute allowedRoles={['admin', 'accountant']}>
                <SuppliersPage />
              </ProtectedRoute>
            }
          />

          {/* Reports: All roles, with server & UI role filtering */}
          <Route path="/reports" element={<ReportsPage />} />

          {/* Settings: Admin only */}
          <Route
            path="/settings"
            element={
              <ProtectedRoute allowedRoles={['admin']}>
                <SettingsPage />
              </ProtectedRoute>
            }
          />
        </Route>

        {/* Default Fallback */}
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;

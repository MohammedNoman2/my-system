import React, { useEffect } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../../context/authStore';
import { Spinner } from '../common/Spinner';
import type { UserRole } from '../../types';

interface ProtectedRouteProps {
  children: React.ReactNode;
  allowedRoles?: UserRole[];
}

export function ProtectedRoute({ children, allowedRoles }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, role, checkAuth } = useAuthStore();
  const location = useLocation();

  useEffect(() => {
    // Check session on mount if not authenticated
    if (!isAuthenticated) {
      checkAuth();
    }
  }, [isAuthenticated, checkAuth]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <Spinner size="lg" label="جارٍ التحقق من الجلسة..." />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (allowedRoles && role && !allowedRoles.includes(role)) {
    return (
      <div className="min-h-[70vh] flex flex-col items-center justify-center text-center p-6">
        <div className="w-16 h-16 bg-red-100 text-red-600 rounded-full flex items-center justify-center mb-4 text-2xl font-bold">
          !
        </div>
        <h2 className="text-xl font-bold text-slate-900 mb-2">غير مصرح لك بالوصول</h2>
        <p className="text-slate-500 text-sm max-w-md mb-6">
          حسابك الحالي بدور ({role}) لا يمتلك الصلاحية الكافية لعرض هذه الصفحة أو تنفيذ هذه العملية.
        </p>
        <a
          href="/dashboard"
          className="inline-flex items-center justify-center px-4 py-2 text-sm font-medium bg-[#1e3a8a] text-white rounded-lg hover:bg-[#1e40af]"
        >
          العودة للوحة التحكم
        </a>
      </div>
    );
  }

  return <>{children}</>;
}

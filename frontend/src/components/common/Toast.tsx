import React from 'react';
import { CheckCircle2, AlertTriangle, AlertCircle, Info, X } from 'lucide-react';
import { useUIStore, type ToastItem } from '../../context/uiStore';
import { cn } from '../../utils/cn';

export interface ToastProps {
  toast: ToastItem;
}

export function Toast({ toast }: ToastProps) {
  const removeToast = useUIStore((state) => state.removeToast);

  const icons = {
    success: <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />,
    error: <AlertCircle className="w-5 h-5 text-red-600 shrink-0" />,
    warning: <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0" />,
    info: <Info className="w-5 h-5 text-blue-600 shrink-0" />,
  };

  const borderStyles = {
    success: 'border-emerald-200 bg-emerald-50/90 text-emerald-950',
    error: 'border-red-200 bg-red-50/90 text-red-950',
    warning: 'border-amber-200 bg-amber-50/90 text-amber-950',
    info: 'border-blue-200 bg-blue-50/90 text-blue-950',
  };

  return (
    <div
      className={cn(
        'pointer-events-auto flex w-full max-w-sm items-center gap-3 rounded-xl border p-4 shadow-lg backdrop-blur-xs transition-all duration-300 animate-in fade-in slide-in-from-top-2',
        borderStyles[toast.type]
      )}
    >
      {icons[toast.type]}
      <p className="flex-1 text-sm font-medium leading-relaxed">{toast.message}</p>
      <button
        onClick={() => removeToast(toast.id)}
        className="rounded-lg p-1 text-slate-400 hover:bg-black/5 hover:text-slate-700 transition-colors"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}

export function ToastContainer() {
  const toasts = useUIStore((state) => state.toasts);

  if (toasts.length === 0) return null;

  return (
    <div className="pointer-events-none fixed inset-0 z-50 flex flex-col items-center gap-2 p-4 sm:items-start sm:p-6 sm:bottom-0 sm:top-auto sm:right-auto sm:left-6">
      {toasts.map((toast) => (
        <Toast key={toast.id} toast={toast} />
      ))}
    </div>
  );
}

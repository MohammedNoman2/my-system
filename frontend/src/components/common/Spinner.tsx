import React from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from '../../utils/cn';

export interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
  label?: string;
}

export function Spinner({ size = 'md', className, label }: SpinnerProps) {
  const sizes = {
    sm: 'w-4 h-4',
    md: 'w-6 h-6',
    lg: 'w-8 h-8',
    xl: 'w-12 h-12',
  };

  return (
    <div className="flex flex-col items-center justify-center p-4 gap-2 text-slate-500">
      <Loader2 className={cn('animate-spin text-[#1e3a8a]', sizes[size], className)} />
      {label && <span className="text-xs font-medium text-slate-500">{label}</span>}
    </div>
  );
}

import React, { useState, useEffect, useRef } from 'react';
import { Loader2, UserCheck } from 'lucide-react';
import api from '../../services/api';
import type { Customer } from '../../types';

interface PassengerNameAutocompleteProps {
  label: string;
  placeholder?: string;
  value: string;
  required?: boolean;
  error?: string;
  onChange: (value: string) => void;
  onSelectCustomer: (customer: Customer) => void;
}

export function PassengerNameAutocomplete({
  label,
  placeholder = 'مثال: محمد أحمد علي',
  value,
  required = true,
  error,
  onChange,
  onSelectCustomer,
}: PassengerNameAutocompleteProps) {
  const [results, setResults] = useState<Customer[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const skipNextFetchRef = useRef(false);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    if (skipNextFetchRef.current) {
      skipNextFetchRef.current = false;
      return;
    }
    const q = value.trim();
    if (q.length < 2) {
      setResults([]);
      setIsOpen(false);
      return;
    }
    const timer = setTimeout(async () => {
      setIsLoading(true);
      try {
        const res = await api.get('/customers/search', {
          params: { q, limit: 6 },
        });
        const list = Array.isArray(res.data) ? res.data : [];
        setResults(list);
        setIsOpen(list.length > 0);
      } catch {
        setResults([]);
      } finally {
        setIsLoading(false);
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [value]);

  return (
    <div className="w-full relative" ref={containerRef}>
      <label className="block text-sm font-medium text-slate-700 mb-1">
        {label}
        {required && <span className="text-red-500 mr-1">*</span>}
      </label>
      <div className="relative">
        <input
          type="text"
          value={value}
          required={required}
          placeholder={placeholder}
          onFocus={() => {
            if (results.length > 0) setIsOpen(true);
          }}
          onChange={(e) => onChange(e.target.value)}
          className={`w-full rounded-xl border bg-white px-3.5 py-2.5 text-sm text-slate-900 transition-colors placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#1e3a8a] focus:border-transparent ${
            error ? 'border-red-400' : 'border-slate-300'
          }`}
        />
        {isLoading && (
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-[#1e3a8a]">
            <Loader2 className="w-4 h-4 animate-spin" />
          </div>
        )}
      </div>
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}

      {isOpen && results.length > 0 && (
        <div className="absolute z-40 mt-1 w-full rounded-xl border border-slate-200 bg-white shadow-xl max-h-56 overflow-y-auto">
          {results.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => {
                skipNextFetchRef.current = true;
                setIsOpen(false);
                onSelectCustomer(c);
              }}
              className="w-full text-right px-3 py-2 hover:bg-blue-50/80 border-b border-slate-100 last:border-b-0 flex items-center justify-between gap-2 transition-colors"
            >
              <div className="min-w-0">
                <p className="text-xs font-bold text-slate-800 truncate">{c.name}</p>
                <p className="text-[11px] text-slate-500 truncate">
                  {c.phone_number}
                  {c.passport_number ? ` | جواز: ${c.passport_number}` : ''}
                  {c.id_number ? ` | هوية: ${c.id_number}` : ''}
                </p>
              </div>
              <UserCheck className="w-3.5 h-3.5 text-[#1e3a8a] shrink-0" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

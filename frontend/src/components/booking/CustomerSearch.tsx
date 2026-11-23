import React, { useState, useEffect, useRef } from 'react';
import { Search, UserCheck, UserPlus, X, Loader2 } from 'lucide-react';
import api from '../../services/api';
import type { Customer } from '../../types';
import { cn } from '../../utils/cn';

interface CustomerSearchProps {
  selectedCustomer: Customer | null;
  onSelectCustomer: (customer: Customer | null) => void;
  onManualModeToggle?: (isManual: boolean) => void;
  onManualNameInput?: (name: string) => void;
}

export function CustomerSearch({
  selectedCustomer,
  onSelectCustomer,
  onManualModeToggle,
  onManualNameInput,
}: CustomerSearchProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Customer[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Debounced search
  useEffect(() => {
    if (!query.trim() || query.length < 1) {
      setResults([]);
      setIsOpen(false);
      return;
    }

    const timer = setTimeout(async () => {
      setIsLoading(true);
      try {
        const res = await api.get('/customers/search', {
          params: { q: query.trim(), limit: 8 },
        });
        setResults(res.data);
        setIsOpen(true);
      } catch (err) {
        console.error('Customer search error', err);
      } finally {
        setIsLoading(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [query]);

  // Click outside to close dropdown
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = (customer: Customer) => {
    onSelectCustomer(customer);
    setQuery('');
    setIsOpen(false);
    if (onManualModeToggle) onManualModeToggle(false);
  };

  const handleClear = () => {
    onSelectCustomer(null);
    setQuery('');
    if (onManualModeToggle) onManualModeToggle(true);
  };

  return (
    <div className="w-full" ref={containerRef}>
      <label className="block text-sm font-semibold text-slate-700 mb-1">
        البحث الذكي عن عميل مسجل مسبقاً (اختياري)
      </label>

      {selectedCustomer ? (
        <div className="flex items-center justify-between p-3 bg-blue-50/80 border border-blue-200 rounded-xl">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-[#1e3a8a] text-white flex items-center justify-center">
              <UserCheck className="w-5 h-5" />
            </div>
            <div>
              <p className="text-sm font-bold text-slate-900">{selectedCustomer.name}</p>
              <div className="flex items-center gap-3 text-xs text-slate-600">
                <span>هاتف: {selectedCustomer.phone_number}</span>
                {selectedCustomer.passport_number && (
                  <span>جواز: {selectedCustomer.passport_number}</span>
                )}
                {selectedCustomer.id_number && (
                  <span>هوية: {selectedCustomer.id_number}</span>
                )}
                <span className={`font-semibold ${Number(selectedCustomer.balance) > 0 ? 'text-red-600' : Number(selectedCustomer.balance) < 0 ? 'text-emerald-700' : 'text-slate-600'}`}>
                  الرصيد المعادل: {Math.abs(Number(selectedCustomer.balance)).toLocaleString()} YER ({Number(selectedCustomer.balance) > 0 ? 'عليه' : Number(selectedCustomer.balance) < 0 ? 'له رصيد دائن' : 'متزن'})
                </span>
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={handleClear}
            className="p-1.5 rounded-lg text-slate-400 hover:bg-white hover:text-red-600 transition-colors"
            title="إلغاء التحديد وإدخال شخص يدوي"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      ) : (
        <div className="relative">
          <div className="relative">
            <input
              type="text"
              value={query}
              onChange={(e) => {
                const val = e.target.value;
                setQuery(val);
                if (onManualNameInput && !/\d/.test(val)) onManualNameInput(val);
              }}
              placeholder="اكتب اسم العميل (أو ابحث بالهاتف/الجواز للاختيار التلقائي أو الإدخال اليدوي)..."
              className="w-full rounded-xl border border-slate-300 bg-white pr-10 pl-10 py-2.5 text-sm text-slate-900 transition-colors placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#1e3a8a] focus:border-transparent"
            />
            <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none text-slate-400">
              <Search className="w-4 h-4" />
            </div>
            {isLoading && (
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-[#1e3a8a]">
                <Loader2 className="w-4 h-4 animate-spin" />
              </div>
            )}
          </div>

          {/* Autocomplete Dropdown */}
          {isOpen && (
            <div className="absolute z-30 mt-1 w-full rounded-xl border border-slate-200 bg-white shadow-xl max-h-60 overflow-y-auto">
              {results.length > 0 ? (
                results.map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => handleSelect(c)}
                    className="w-full text-right px-4 py-2.5 hover:bg-blue-50/70 border-b border-slate-100 last:border-b-0 flex items-center justify-between transition-colors"
                  >
                    <div>
                      <p className="text-sm font-semibold text-slate-800">{c.name}</p>
                      <p className="text-xs text-slate-500">
                        {c.phone_number} {c.passport_number ? `| جواز: ${c.passport_number}` : ''}{' '}
                        {c.id_number ? `| هوية: ${c.id_number}` : ''}
                      </p>
                    </div>
                    <span className="text-xs font-bold text-[#1e3a8a] bg-blue-50 px-2 py-0.5 rounded-md">
                      اختيار
                    </span>
                  </button>
                ))
              ) : (
                <button
                  type="button"
                  onClick={() => {
                    onSelectCustomer(null);
                    const trimmed = query.trim();
                    if (onManualNameInput && !/\d/.test(trimmed)) onManualNameInput(trimmed);
                    setIsOpen(false);
                    if (onManualModeToggle) onManualModeToggle(true);
                  }}
                  className="w-full p-3 text-right text-xs text-emerald-700 hover:bg-emerald-50 flex items-center gap-2 transition-colors"
                >
                  <UserPlus className="w-4 h-4 shrink-0" />
                  <span>
                    استخدام <strong>«{query.trim()}»</strong> كعميل جديد (إدخال يدوي في الخطوة التالية)
                  </span>
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

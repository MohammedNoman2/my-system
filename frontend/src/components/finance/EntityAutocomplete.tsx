import React, { useState, useMemo, useRef, useEffect } from 'react';
import { Search, X, Check } from 'lucide-react';

export interface EntityOption {
  id: number;
  name: string;
  phone_number?: string | null;
  balance?: number;
}

interface EntityAutocompleteProps {
  label: string;
  placeholder?: string;
  options: EntityOption[];
  value?: number | null;
  onChange: (id: number | undefined) => void;
  required?: boolean;
  error?: string;
  showBalance?: boolean;
}

export function EntityAutocomplete({
  label,
  placeholder = 'ابحث بالاسم أو رقم الهاتف...',
  options,
  value,
  onChange,
  required,
  error,
  showBalance = false,
}: EntityAutocompleteProps) {
  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const selectedOption = useMemo(
    () => options.find((o) => o.id === Number(value)),
    [options, value]
  );

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options.slice(0, 25);
    return options
      .filter(
        (o) =>
          o.name.toLowerCase().includes(q) ||
          (o.phone_number && o.phone_number.toLowerCase().includes(q))
      )
      .slice(0, 25);
  }, [options, query]);

  return (
    <div ref={containerRef} className="relative">
      <label className="block text-sm font-medium text-slate-700 mb-1">
        {label} {required && <span className="text-red-500">*</span>}
      </label>

      {selectedOption && !isOpen ? (
        <div
          onClick={() => {
            setQuery('');
            setIsOpen(true);
          }}
          className={`flex items-center justify-between w-full rounded-lg border px-3 py-2 text-sm cursor-pointer bg-slate-50 hover:bg-white transition-colors ${
            error ? 'border-red-400' : 'border-slate-300'
          }`}
        >
          <div className="truncate">
            <span className="font-semibold text-slate-900">{selectedOption.name}</span>
            {selectedOption.phone_number && (
              <span className="text-xs text-slate-500 mr-2" dir="ltr">
                ({selectedOption.phone_number})
              </span>
            )}
            {showBalance && selectedOption.balance !== undefined && (
              <span className="text-xs text-amber-700 font-medium mr-2">
                — رصيد: {Number(selectedOption.balance).toLocaleString()} YER
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onChange(undefined);
              setQuery('');
              setIsOpen(true);
            }}
            className="p-0.5 rounded hover:bg-slate-200 text-slate-500"
            title="تغيير"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      ) : (
        <div className="relative">
          <Search className="w-4 h-4 text-slate-400 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="text"
            value={query}
            onFocus={() => setIsOpen(true)}
            onChange={(e) => {
              setQuery(e.target.value);
              setIsOpen(true);
            }}
            placeholder={placeholder}
            className={`w-full rounded-lg border pr-9 pl-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#1e3a8a] ${
              error ? 'border-red-400' : 'border-slate-300'
            }`}
          />
        </div>
      )}

      {isOpen && (
        <div className="absolute z-50 mt-1 w-full max-h-60 overflow-y-auto bg-white border border-slate-200 rounded-xl shadow-lg">
          {filtered.length === 0 ? (
            <div className="p-3 text-xs text-slate-500 text-center">لا توجد نتائج مطابقة</div>
          ) : (
            filtered.map((opt) => {
              const isSelected = opt.id === Number(value);
              return (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => {
                    onChange(opt.id);
                    setIsOpen(false);
                    setQuery('');
                  }}
                  className={`w-full text-right px-3 py-2 text-sm flex items-center justify-between hover:bg-blue-50 transition-colors ${
                    isSelected ? 'bg-blue-50/70 font-bold text-[#1e3a8a]' : 'text-slate-800'
                  }`}
                >
                  <div className="truncate">
                    <span>{opt.name}</span>
                    {opt.phone_number && (
                      <span className="text-xs text-slate-500 mr-2" dir="ltr">
                        {opt.phone_number}
                      </span>
                    )}
                    {showBalance && opt.balance !== undefined && (
                      <span className="text-xs text-amber-700 mr-2">
                        ({Number(opt.balance).toLocaleString()} YER)
                      </span>
                    )}
                  </div>
                  {isSelected && <Check className="w-4 h-4 text-[#1e3a8a] shrink-0" />}
                </button>
              );
            })
          )}
        </div>
      )}

      {error && <p className="text-xs text-red-600 mt-1">{error}</p>}
    </div>
  );
}

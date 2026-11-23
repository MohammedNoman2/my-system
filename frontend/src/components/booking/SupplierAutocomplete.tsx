import React, { useState, useMemo, useRef, useEffect } from 'react';
import { Building2, Check, PlusCircle } from 'lucide-react';
import type { Supplier } from '../../types';

interface SupplierAutocompleteProps {
  suppliers: Supplier[];
  supplierId?: string | number | null;
  supplierName?: string | null;
  onSelectExisting: (supplier: Supplier) => void;
  onManualChange: (name: string) => void;
  error?: string;
}

export function SupplierAutocomplete({
  suppliers,
  supplierId,
  supplierName,
  onSelectExisting,
  onManualChange,
  error,
}: SupplierAutocompleteProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [inputValue, setInputValue] = useState(supplierName || '');
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (supplierId) {
      const found = suppliers.find((s) => String(s.id) === String(supplierId));
      if (found) setInputValue(found.name);
    } else if (supplierName !== undefined && supplierName !== null) {
      setInputValue(supplierName);
    }
  }, [supplierId, supplierName, suppliers]);

  useEffect(() => {
    function handleOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleOutside);
    return () => document.removeEventListener('mousedown', handleOutside);
  }, []);

  const filtered = useMemo(() => {
    const q = inputValue.trim().toLowerCase();
    if (!q) return suppliers.slice(0, 20);
    return suppliers.filter((s) => s.name.toLowerCase().includes(q)).slice(0, 20);
  }, [suppliers, inputValue]);

  const exactMatch = useMemo(() => {
    const q = inputValue.trim().toLowerCase();
    return suppliers.find((s) => s.name.trim().toLowerCase() === q);
  }, [suppliers, inputValue]);

  return (
    <div ref={containerRef} className="relative">
      <label className="block text-sm font-medium text-slate-700 mb-1">
        المزود / المورد (اكتب الاسم أو اختر من الاقتراحات) <span className="text-red-500">*</span>
      </label>

      <div className="relative">
        <Building2 className="w-4 h-4 text-slate-400 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
        <input
          type="text"
          value={inputValue}
          onFocus={() => setIsOpen(true)}
          onChange={(e) => {
            const val = e.target.value;
            setInputValue(val);
            setIsOpen(true);
            const match = suppliers.find((s) => s.name.trim().toLowerCase() === val.trim().toLowerCase());
            if (match) {
              onSelectExisting(match);
            } else {
              onManualChange(val);
            }
          }}
          placeholder="اكتب اسم المورد يدوياً أو اختره من القائمة المقترحة..."
          className={`w-full rounded-lg border pr-9 pl-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#1e3a8a] ${
            error ? 'border-red-400' : 'border-slate-300'
          }`}
        />
      </div>

      {isOpen && (
        <div className="absolute z-50 mt-1 w-full max-h-56 overflow-y-auto bg-white border border-slate-200 rounded-xl shadow-lg">
          {filtered.map((s) => {
            const selected = String(s.id) === String(supplierId);
            return (
              <button
                key={s.id}
                type="button"
                onClick={() => {
                  setInputValue(s.name);
                  onSelectExisting(s);
                  setIsOpen(false);
                }}
                className={`w-full text-right px-3 py-2 text-sm flex items-center justify-between hover:bg-blue-50 ${
                  selected ? 'bg-blue-50 font-bold text-[#1e3a8a]' : 'text-slate-800'
                }`}
              >
                <span>
                  {s.name}
                  {s.service_type && (
                    <span className="text-xs text-slate-400 mr-2">({s.service_type})</span>
                  )}
                </span>
                {selected && <Check className="w-4 h-4 text-[#1e3a8a]" />}
              </button>
            );
          })}

          {inputValue.trim() && !exactMatch && (
            <button
              type="button"
              onClick={() => {
                onManualChange(inputValue.trim());
                setIsOpen(false);
              }}
              className="w-full text-right px-3 py-2 text-xs font-bold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 flex items-center gap-1.5 border-t border-emerald-100"
            >
              <PlusCircle className="w-4 h-4 shrink-0" />
              اعتماد مورد جديد بالاسم: "{inputValue.trim()}"
            </button>
          )}
        </div>
      )}

      {error && <p className="text-xs text-red-600 mt-1">{error}</p>}
    </div>
  );
}

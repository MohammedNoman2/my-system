import React, { useEffect, useState } from 'react';
import { BookOpen, Download, RefreshCw } from 'lucide-react';
import api from '../../services/api';
import { Modal } from '../common/Modal';
import { Spinner } from '../common/Spinner';
import { EmptyState } from '../common/EmptyState';

interface LedgerModalProps {
  isOpen: boolean;
  onClose: () => void;
  entityType: 'customer' | 'supplier';
  entityId: number | null;
  entityName?: string;
}

export function LedgerModal({
  isOpen,
  onClose,
  entityType,
  entityId,
  entityName,
}: LedgerModalProps) {
  const [data, setData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedCurrency, setSelectedCurrency] = useState<string>('YER');

  useEffect(() => {
    async function fetchLedger() {
      if (!entityId) return;
      setIsLoading(true);
      try {
        const endpoint =
          entityType === 'customer'
            ? `/finance/ledger/customer/${entityId}`
            : `/finance/ledger/supplier/${entityId}`;
        const res = await api.get(endpoint);
        setData(res.data);
        
        // Auto-select first available currency if YER doesn't exist
        if (res.data?.ledgers) {
            const currencies = Object.keys(res.data.ledgers);
            if (currencies.length > 0 && !currencies.includes('YER')) {
                setSelectedCurrency(currencies[0]);
            }
        }
      } catch (err) {
        console.error('Failed to load ledger', err);
      } finally {
        setIsLoading(false);
      }
    }

    if (isOpen && entityId) {
      fetchLedger();
    }
  }, [isOpen, entityId, entityType]);

  if (!entityId) return null;

  const entityInfo = entityType === 'customer' ? data?.customer : data?.supplier;
  const ledgers = data?.ledgers || {};
  const availableCurrencies = Object.keys(ledgers);
  
  // Get data for selected currency
  const currentLedger = ledgers[selectedCurrency] || { entries: [], balance: 0 };
  const entries: any[] = currentLedger.entries;
  const currentBalance = currentLedger.balance;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`كشف حساب وسجل الأستاذ: ${entityName || entityInfo?.name || ''}`}
      description={`عرض تفصيلي لجميع العمليات المالية والحركات المدينة والدائنة والرصيد التراكمي مفصولة حسب العملة`}
      size="full"
    >
      <div className="space-y-4">
        {/* Header KPI Summary */}
        <div className="flex flex-wrap items-center justify-between gap-4 p-4 bg-slate-50 rounded-xl border border-slate-200">
          <div>
            <span className="text-xs text-slate-500">الطرف المعني:</span>
            <p className="text-base font-bold text-slate-900">
              {entityInfo?.name || entityName} ({entityType === 'customer' ? 'عميل' : 'مورد'})
            </p>
            {entityInfo?.phone && (
              <p className="text-xs text-slate-500">هاتف: {entityInfo.phone}</p>
            )}
          </div>

          <div className="text-left">
            <span className="text-xs text-slate-500">الرصيد الحالي المستحق ({selectedCurrency}):</span>
            <div
              className={`text-xl font-black ${
                Number(currentBalance) > 0
                  ? 'text-red-600'
                  : Number(currentBalance) < 0
                  ? 'text-emerald-600'
                  : 'text-slate-800'
              }`}
            >
              {Number(currentBalance).toLocaleString()} {selectedCurrency}
            </div>
            <p className="text-[11px] text-slate-400">
              {Number(currentBalance) > 0
                ? 'مديونية مستحقة'
                : Number(currentBalance) < 0
                ? 'رصيد دائن مسبق'
                : 'رصيد خالص 0.00'}
            </p>
          </div>
        </div>

        {/* Currency Tabs */}
        {availableCurrencies.length > 0 && (
          <div className="flex border-b border-slate-200 gap-2 mb-4">
            {availableCurrencies.map((curr) => (
              <button
                key={curr}
                onClick={() => setSelectedCurrency(curr)}
                className={`py-2 px-4 text-sm font-bold border-b-2 transition-colors ${
                  selectedCurrency === curr
                    ? 'border-emerald-600 text-emerald-700 bg-emerald-50/50'
                    : 'border-transparent text-slate-500 hover:text-slate-700 hover:bg-slate-50'
                }`}
              >
                كشف حساب {curr}
              </button>
            ))}
          </div>
        )}

        {/* Ledger Entries Table */}
        <div className="border border-slate-200 rounded-xl overflow-hidden bg-white shadow-2xs">
          {isLoading ? (
            <div className="py-16">
              <Spinner size="lg" label="جارٍ تحميل حركات كشف الحساب..." />
            </div>
          ) : entries.length === 0 ? (
            <EmptyState
              title={`لا توجد حركات مالية مسجلة بعملة ${selectedCurrency}`}
              description="لم يتم تسجيل أي عمليات حجز أو سندات قبض أو صرف لهذا الطرف بهذه العملة."
            />
          ) : (
            <div className="overflow-x-auto max-h-[55vh]">
              <table className="w-full text-right text-xs sm:text-sm">
                <thead className="bg-slate-50 text-slate-600 border-b border-slate-200 font-semibold sticky top-0">
                  <tr>
                    <th className="px-3.5 py-3">التاريخ</th>
                    <th className="px-3.5 py-3">رقم المرجع</th>
                    <th className="px-3.5 py-3">البيان / الوصف</th>
                    <th className="px-3.5 py-3 text-red-700">مدين (+)</th>
                    <th className="px-3.5 py-3 text-emerald-700">دائن (-)</th>
                    <th className="px-3.5 py-3 font-bold">الرصيد التراكمي</th>
                    <th className="px-3.5 py-3">ملاحظات</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {entries.map((item, idx) => (
                    <tr key={idx} className="hover:bg-slate-50/80 transition-colors">
                      <td className="px-3.5 py-2.5 text-slate-600 whitespace-nowrap">
                        {item.date ? new Date(item.date).toLocaleDateString('ar-EG') : '--'}
                      </td>
                      <td className="px-3.5 py-2.5 font-mono font-bold text-[#1e3a8a]">
                        {item.reference_id || '--'}
                      </td>
                      <td className="px-3.5 py-2.5 font-medium text-slate-800">
                        {item.description}
                      </td>
                      <td className="px-3.5 py-2.5 font-semibold text-red-600">
                        {Number(item.debit) > 0 ? Number(item.debit).toLocaleString() : '--'}
                      </td>
                      <td className="px-3.5 py-2.5 font-semibold text-emerald-600">
                        {Number(item.credit) > 0 ? Number(item.credit).toLocaleString() : '--'}
                      </td>
                      <td className="px-3.5 py-2.5 font-bold font-mono text-slate-900">
                        {Number(item.balance).toLocaleString()} {selectedCurrency}
                      </td>
                      <td className="px-3.5 py-2.5 text-xs text-slate-400 max-w-xs truncate">
                        {item.notes || '--'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
}

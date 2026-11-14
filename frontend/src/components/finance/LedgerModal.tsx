import React, { useEffect, useState } from 'react';
import { BookOpen, Download, RefreshCw, FileText, FileSpreadsheet } from 'lucide-react';
import api from '../../services/api';
import { Modal } from '../common/Modal';
import { Spinner } from '../common/Spinner';
import { EmptyState } from '../common/EmptyState';
import { Input } from '../common/Input';
import { Button } from '../common/Button';
import { useUIStore } from '../../context/uiStore';

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
  const [selectedCurrency, setSelectedCurrency] = useState<string>('all');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const addToast = useUIStore((state) => state.addToast);

  useEffect(() => {
    async function fetchLedger() {
      if (!entityId) return;
      setIsLoading(true);
      try {
        const endpoint = `/finance/ledger/v3/${entityType}/${entityId}`;
        const params = new URLSearchParams();
        if (fromDate) params.append('from_date', fromDate);
        if (toDate) params.append('to_date', toDate);
        
        const res = await api.get(`${endpoint}?${params.toString()}`);
        setData(res.data);
      } catch (err) {
        console.error('Failed to load ledger', err);
        addToast('فشل في تحميل كشف الحساب', 'error');
      } finally {
        setIsLoading(false);
      }
    }

    if (isOpen && entityId) {
      fetchLedger();
    }
  }, [isOpen, entityId, entityType, fromDate, toDate]);

  const handleExport = async (format: 'pdf' | 'excel') => {
    if (!entityId) return;
    try {
      const endpoint = `/finance/ledger/v3/${entityType}/${entityId}/export`;
      const params = new URLSearchParams({ format });
      if (fromDate) params.append('from_date', fromDate);
      if (toDate) params.append('to_date', toDate);
      
      const res = await api.get(`${endpoint}?${params.toString()}`, { responseType: 'blob' });
      
      const contentType = String(res.headers['content-type'] || "");
      if (contentType.includes("text/html")) {
        const text = await res.data.text();
        const printWindow = window.open("", "_blank");
        if (printWindow) {
          printWindow.document.write(text);
          printWindow.document.close();
          printWindow.focus();
        }
      } else {
        const disposition = res.headers['content-disposition'];
        let filename = `ledger-${entityType}-${entityId}.${format === 'excel' ? 'xlsx' : 'pdf'}`;
        if (disposition && disposition.indexOf('filename=') !== -1) {
            filename = disposition.split('filename=')[1].replace(/["']/g, "");
        }
        const url = window.URL.createObjectURL(new Blob([res.data]));
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', filename);
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
      }
    } catch (err: any) {
      console.error('Export failed', err);
      let errorMsg = err?.response?.status === 403 ? 'عذراً، لا تملك الصلاحية' : 'فشل تصدير الكشف';
      if (err?.response?.data instanceof Blob) {
          try {
              const text = await err.response.data.text();
              const json = JSON.parse(text);
              if (json.detail) errorMsg = json.detail;
          } catch(e) {}
      }
      addToast(errorMsg, 'error');
    }
  };

  if (!entityId) return null;

  const entityInfo = data?.entity;
  const ledgers = data?.ledgers || {};
  const currencies = Object.keys(ledgers).filter(c => ledgers[c].entries.length > 0 || ledgers[c].opening_balance !== 0);

  const fmt2 = (v: any) =>
    Number(v || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  const getBalBadgeClass = (bal: number) => {
    if (bal === 0) return 'bg-slate-100 text-slate-600';
    if (entityType === 'customer') {
      return bal > 0 ? 'bg-red-50 text-red-700' : 'bg-emerald-50 text-emerald-700';
    }
    return bal > 0 ? 'bg-amber-50 text-amber-800' : 'bg-emerald-50 text-emerald-700';
  };

  const renderLedgerTable = (curr: string, ledger: any) => (
    <div key={curr} className="mb-6 border border-slate-200 rounded-xl overflow-hidden bg-white shadow-2xs">
        <div className="p-3 bg-slate-50 border-b border-slate-200 flex flex-wrap gap-2 justify-between items-center">
            <h3 className="font-bold text-slate-800">كشف حساب ({curr})</h3>
            <div className="flex flex-wrap gap-4 text-xs font-semibold">
                <span>افتتاحي: {fmt2(ledger.opening_balance)} ({ledger.opening_balance_label || 'متزن'})</span>
                <span className="text-red-600">إجمالي مدين: {fmt2(ledger.total_debit)}</span>
                <span className="text-emerald-600">إجمالي دائن: {fmt2(ledger.total_credit)}</span>
                <span className="text-blue-700">ختامي: {fmt2(ledger.closing_balance)} ({ledger.closing_balance_label || 'متزن'})</span>
            </div>
        </div>
        {ledger.entries.length === 0 ? (
            <div className="p-4 text-center text-slate-500">لا توجد حركات في هذه الفترة</div>
        ) : (
            <div className="overflow-x-auto max-h-[40vh]">
              <table className="w-full text-right text-xs sm:text-sm">
                <thead className="bg-slate-50 text-slate-600 border-b border-slate-200 font-semibold sticky top-0">
                  <tr>
                    <th className="px-3.5 py-3">التاريخ</th>
                    <th className="px-3.5 py-3">رقم المرجع</th>
                    <th className="px-3.5 py-3">البيان / الوصف التفصيلي</th>
                    <th className="px-3.5 py-3 text-red-700">{entityType === 'customer' ? 'مدين (عليه +)' : 'مدين (سداد -)'}</th>
                    <th className="px-3.5 py-3 text-emerald-700">{entityType === 'customer' ? 'دائن (له -)' : 'دائن (مستحق +)'}</th>
                    <th className="px-3.5 py-3 font-bold">الرصيد التراكمي</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {ledger.entries.map((item: any, idx: number) => (
                    <tr key={idx} className="hover:bg-slate-50/80 transition-colors">
                      <td className="px-3.5 py-2.5 text-slate-600 whitespace-nowrap">
                        {item.date}
                      </td>
                      <td className="px-3.5 py-2.5 font-mono font-bold text-[#1e3a8a]">
                        {item.reference_id || '--'}
                      </td>
                      <td className="px-3.5 py-2.5 font-medium text-slate-800">
                        {item.description}
                      </td>
                      <td className="px-3.5 py-2.5 font-semibold text-red-600">
                        {Number(item.debit) > 0 ? fmt2(item.debit) : '--'}
                      </td>
                      <td className="px-3.5 py-2.5 font-semibold text-emerald-600">
                        {Number(item.credit) > 0 ? fmt2(item.credit) : '--'}
                      </td>
                      <td className="px-3.5 py-2.5 font-bold font-mono text-slate-900">
                        <span>{fmt2(item.balance)} {curr}</span>
                        {item.balance_label && (
                          <span className={`mr-1.5 text-[11px] px-1.5 py-0.5 rounded ${getBalBadgeClass(Number(item.balance))}`}>
                            {item.balance_label}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
        )}
    </div>
  );

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`كشف حساب وسجل الأستاذ: ${entityInfo?.name || entityName || ''}`}
      description="عرض تفصيلي للعمليات مفصولة حسب العملة"
      size="full"
    >
      <div className="space-y-4">
        {/* Header KPI & Date Filter */}
        <div className="flex flex-wrap items-center justify-between gap-4 p-4 bg-slate-50 rounded-xl border border-slate-200">
          <div className="flex gap-4 items-end">
            <Input label="من تاريخ" type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
            <Input label="إلى تاريخ" type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} />
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => handleExport('excel')} className="text-emerald-700 border-emerald-200 hover:bg-emerald-50">
                <FileSpreadsheet className="w-4 h-4 ml-2" /> Excel
            </Button>
            <Button variant="outline" onClick={() => handleExport('pdf')} className="text-red-700 border-red-200 hover:bg-red-50">
                <FileText className="w-4 h-4 ml-2" /> PDF
            </Button>
          </div>
        </div>

        {/* Closing Balances Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {['YER', 'SAR', 'USD'].map(curr => {
                const closeBal = Number(ledgers[curr]?.closing_balance || 0);
                const closeLbl = ledgers[curr]?.closing_balance_label || 'متزن';
                const textCol =
                  closeBal === 0
                    ? 'text-slate-800'
                    : entityType === 'customer'
                    ? closeBal > 0
                      ? 'text-red-600'
                      : 'text-emerald-600'
                    : closeBal > 0
                    ? 'text-amber-700'
                    : 'text-emerald-600';
                return (
                  <div key={curr} className="p-4 bg-white border border-slate-200 rounded-lg shadow-sm text-center">
                      <p className="text-sm text-slate-500">الرصيد الختامي ({curr})</p>
                      <p className={`text-xl font-bold ${textCol}`}>
                          {ledgers[curr] ? fmt2(closeBal) : '0.00'}
                      </p>
                      <span className={`inline-block mt-1 text-xs font-bold px-2 py-0.5 rounded-full ${getBalBadgeClass(closeBal)}`}>
                          {closeLbl}
                      </span>
                  </div>
                );
            })}
        </div>

        {/* Currency Tabs */}
        <div className="flex border-b border-slate-200 gap-2 mb-4">
            <button
                onClick={() => setSelectedCurrency('all')}
                className={`py-2 px-4 text-sm font-bold border-b-2 transition-colors ${
                  selectedCurrency === 'all' ? 'border-blue-600 text-blue-700 bg-blue-50/50' : 'border-transparent text-slate-500 hover:text-slate-700 hover:bg-slate-50'
                }`}
            >
                الكل
            </button>
            {currencies.map((curr) => (
              <button
                key={curr}
                onClick={() => setSelectedCurrency(curr)}
                className={`py-2 px-4 text-sm font-bold border-b-2 transition-colors ${
                  selectedCurrency === curr ? 'border-blue-600 text-blue-700 bg-blue-50/50' : 'border-transparent text-slate-500 hover:text-slate-700 hover:bg-slate-50'
                }`}
              >
                {curr}
              </button>
            ))}
        </div>

        {/* Ledger Tables */}
        {isLoading ? (
            <div className="py-16">
              <Spinner size="lg" label="جارٍ تحميل حركات كشف الحساب..." />
            </div>
        ) : (
            <div>
                {selectedCurrency === 'all' ? (
                    currencies.length > 0 ? currencies.map(curr => renderLedgerTable(curr, ledgers[curr])) : (
                        <EmptyState title="لا توجد حركات" description="لا توجد عمليات مالية مسجلة" />
                    )
                ) : (
                    ledgers[selectedCurrency] ? renderLedgerTable(selectedCurrency, ledgers[selectedCurrency]) : (
                        <EmptyState title="لا توجد حركات" description={`لا توجد عمليات مسجلة بعملة ${selectedCurrency}`} />
                    )
                )}
            </div>
        )}
      </div>
    </Modal>
  );
}

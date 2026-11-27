import React, { useState, useEffect } from 'react';
import {
  ArrowDownLeft,
  ArrowUpRight,
  Receipt,
  PlusCircle,
  RefreshCw,
  Search,
  Filter,
  CreditCard,
  Building,
  User,
} from 'lucide-react';
import api from '../../services/api';
import type { FinancialTransaction, TransactionType } from '../../types';
import { Card, CardHeader, CardTitle, CardContent } from '../../components/common/Card';
import { Spinner } from '../../components/common/Spinner';
import { EmptyState } from '../../components/common/EmptyState';
import { ReceiptVoucherModal } from '../../components/finance/ReceiptVoucherModal';
import { PaymentVoucherModal } from '../../components/finance/PaymentVoucherModal';
import { ExpenseModal } from '../../components/finance/ExpenseModal';

export function FinancePage() {
  const [transactions, setTransactions] = useState<FinancialTransaction[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [ratesToYer, setRatesToYer] = useState<Record<string, number>>({
    YER: 1,
    SAR: 140,
    USD: 533,
  });

  const [isReceiptModalOpen, setIsReceiptModalOpen] = useState(false);
  const [isPaymentModalOpen, setIsPaymentModalOpen] = useState(false);
  const [isExpenseModalOpen, setIsExpenseModalOpen] = useState(false);

  const fetchTransactions = async () => {
    setIsLoading(true);
    try {
      const params: any = { limit: 100 };
      if (typeFilter !== 'all') params.tx_type = typeFilter;
      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;

      const [txRes, ratesRes] = await Promise.all([
        api.get('/finance/transactions', { params }),
        api.get('/settings/exchange-rates').catch(() => ({ data: [] })),
      ]);
      setTransactions(txRes.data);

      const rateMap: Record<string, number> = { YER: 1, SAR: 140, USD: 533 };
      if (Array.isArray(ratesRes.data)) {
        for (const item of ratesRes.data) {
          if (item.to_currency === 'YER' && Number(item.rate) > 0) {
            rateMap[String(item.from_currency).toUpperCase()] = Number(item.rate);
          }
        }
      }
      setRatesToYer(rateMap);
    } catch (err) {
      console.error('Failed to load transactions', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleVoidVoucher = async (tx: FinancialTransaction) => {
    const reason = window.prompt(`يرجى إدخال سبب إلغاء السند رقم ${tx.transaction_id}:`);
    if (!reason || !reason.trim()) return;
    try {
      await api.post(`/finance/vouchers/${tx.id}/void`, { void_reason: reason.trim() });
      await fetchTransactions();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'تعذر إلغاء السند المالي');
    }
  };

  useEffect(() => {
    fetchTransactions();
  }, [typeFilter, startDate, endDate]);

  const typeBadges: Record<string, { label: string; className: string }> = {
    payment_in: { label: 'سند قبض (RC)', className: 'bg-emerald-100 text-emerald-800' },
    payment_out: { label: 'سند صرف (PY)', className: 'bg-amber-100 text-amber-800' },
    expense: { label: 'مصروف (EX)', className: 'bg-rose-100 text-rose-800' },
    refund: { label: 'مسترد', className: 'bg-blue-100 text-blue-800' },
  };

  const paymentMethods: Record<string, string> = {
    cash: 'نقداً',
    bank_transfer: 'تحويل بنكي',
    check: 'شيك مصرفي',
    cheque: 'شيك',
    credit: 'آجل',
  };

  // Quick stats grouped accurately by currency + converted to YER equivalent (exclude voided transactions)
  const summarizeByCurrency = (items: FinancialTransaction[]) => {
    const byCurrency: Record<string, number> = {};
    let totalYer = 0;
    for (const t of items) {
      const curr = String(t.currency || 'YER').toUpperCase();
      const amt = Number(t.amount || 0);
      byCurrency[curr] = Number(((byCurrency[curr] || 0) + amt).toFixed(2));
      const rate = ratesToYer[curr] || 1;
      totalYer += amt * rate;
    }
    return {
      totalYer: Number(totalYer.toFixed(2)),
      byCurrency,
    };
  };

  const activeTransactions = transactions.filter((t) => !t.is_void);
  const summaryIn = summarizeByCurrency(activeTransactions.filter((t) => t.type === 'payment_in'));
  const summaryOut = summarizeByCurrency(activeTransactions.filter((t) => t.type === 'payment_out'));
  const summaryExpenses = summarizeByCurrency(activeTransactions.filter((t) => t.type === 'expense'));

  const formatMoney = (val: number) =>
    val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  return (
    <div className="space-y-6">
      {/* Header and Action Buttons */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900">المالية والسندات والحسابات</h1>
          <p className="text-sm text-slate-500">
            إدارة سندات القبض والصرف، تسجيل المصروفات، ومتابعة حركة الخزينة
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setIsReceiptModalOpen(true)}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs sm:text-sm font-bold text-white bg-emerald-700 hover:bg-emerald-800 rounded-xl shadow-xs transition-colors"
          >
            <ArrowDownLeft className="w-4 h-4" />
            سند قبض (RC)
          </button>
          <button
            onClick={() => setIsPaymentModalOpen(true)}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs sm:text-sm font-bold text-white bg-[#d97706] hover:bg-[#b45309] rounded-xl shadow-xs transition-colors"
          >
            <ArrowUpRight className="w-4 h-4" />
            سند صرف (PY)
          </button>
          <button
            onClick={() => setIsExpenseModalOpen(true)}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs sm:text-sm font-bold text-white bg-rose-600 hover:bg-rose-700 rounded-xl shadow-xs transition-colors"
          >
            <Receipt className="w-4 h-4" />
            تسجيل مصروف (EX)
          </button>
        </div>
      </div>

      {/* Financial Summary KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="border-r-4 border-r-emerald-600">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-semibold text-slate-500">
              إجمالي المقبوضات المعروضة (معادل YER)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-black text-emerald-700">
              {formatMoney(summaryIn.totalYer)} YER
            </div>
            <div className="flex flex-wrap gap-1.5 mt-1.5">
              {Object.entries(summaryIn.byCurrency).length === 0 ? (
                <span className="text-xs text-slate-500">سندات القبض المسجلة</span>
              ) : (
                Object.entries(summaryIn.byCurrency).map(([curr, amt]) => (
                  <span key={curr} className="text-[11px] font-semibold px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-800 border border-emerald-200">
                    {formatMoney(amt)} {curr}
                  </span>
                ))
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="border-r-4 border-r-amber-500">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-semibold text-slate-500">
              إجمالي المدفوعات والصرف (معادل YER)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-black text-amber-700">
              {formatMoney(summaryOut.totalYer)} YER
            </div>
            <div className="flex flex-wrap gap-1.5 mt-1.5">
              {Object.entries(summaryOut.byCurrency).length === 0 ? (
                <span className="text-xs text-slate-500">سندات الصرف المسجلة</span>
              ) : (
                Object.entries(summaryOut.byCurrency).map(([curr, amt]) => (
                  <span key={curr} className="text-[11px] font-semibold px-2 py-0.5 rounded-md bg-amber-50 text-amber-800 border border-amber-200">
                    {formatMoney(amt)} {curr}
                  </span>
                ))
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="border-r-4 border-r-rose-600">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-semibold text-slate-500">
              إجمالي المصروفات التشغيلية (معادل YER)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-black text-rose-600">
              {formatMoney(summaryExpenses.totalYer)} YER
            </div>
            <div className="flex flex-wrap gap-1.5 mt-1.5">
              {Object.entries(summaryExpenses.byCurrency).length === 0 ? (
                <span className="text-xs text-slate-500">إيجار، كهرباء، ونثريات</span>
              ) : (
                Object.entries(summaryExpenses.byCurrency).map(([curr, amt]) => (
                  <span key={curr} className="text-[11px] font-semibold px-2 py-0.5 rounded-md bg-rose-50 text-rose-800 border border-rose-200">
                    {formatMoney(amt)} {curr}
                  </span>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-4 bg-white rounded-2xl border border-slate-200 shadow-2xs">
        <div className="flex flex-wrap items-center gap-3">
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs sm:text-sm font-medium text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#1e3a8a]"
          >
            <option value="all">جميع الحركات المالية</option>
            <option value="payment_in">سندات القبض (RC)</option>
            <option value="payment_out">سندات الصرف (PY)</option>
            <option value="expense">المصروفات (EX)</option>
          </select>

          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">من:</span>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="rounded-xl border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#1e3a8a]"
            />
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">إلى:</span>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="rounded-xl border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#1e3a8a]"
            />
          </div>
        </div>

        <button
          onClick={fetchTransactions}
          className="p-2 rounded-xl border border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100 transition-colors"
          title="تحديث البيانات"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Transactions Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-2xs overflow-hidden">
        {isLoading ? (
          <div className="py-16">
            <Spinner size="lg" label="جارٍ تحميل سجل الحركات المالية..." />
          </div>
        ) : transactions.length === 0 ? (
          <EmptyState
            title="لا توجد حركات مالية مطابقة"
            description="لم يتم العثور على أي سندات أو حركات مسجلة حسب الفلاتر المحددة."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-right text-xs sm:text-sm">
              <thead className="bg-slate-50 text-slate-600 border-b border-slate-200 font-semibold">
                <tr>
                  <th className="px-4 py-3">رقم السند</th>
                  <th className="px-4 py-3">النوع</th>
                  <th className="px-4 py-3">الطرف / البيان</th>
                  <th className="px-4 py-3">التاريخ</th>
                  <th className="px-4 py-3">المبلغ</th>
                  <th className="px-4 py-3">طريقة الدفع</th>
                  <th className="px-4 py-3">رقم المرجع</th>
                  <th className="px-4 py-3">ملاحظات</th>
                  <th className="px-4 py-3 text-center">الحالة / إجراءات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {transactions.map((tx) => (
                  <tr key={tx.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="px-4 py-3 font-mono font-bold text-[#1e3a8a]">
                      {tx.transaction_id}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-block text-[11px] font-bold px-2.5 py-0.5 rounded-full ${
                          typeBadges[tx.type]?.className || 'bg-slate-100 text-slate-700'
                        }`}
                      >
                        {typeBadges[tx.type]?.label || tx.type}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-medium text-slate-800">
                      {(tx as any).entity_name || (tx as any).expense_type || 'حركة عامة'}
                    </td>
                    <td className="px-4 py-3 text-slate-500 whitespace-nowrap">
                      {tx.transaction_date ? new Date(tx.transaction_date).toLocaleDateString('ar-EG') : '--'}
                    </td>
                    <td
                      className={`px-4 py-3 font-bold ${
                        tx.type === 'payment_in'
                          ? 'text-emerald-700'
                          : tx.type === 'payment_out'
                          ? 'text-amber-700'
                          : 'text-rose-600'
                      }`}
                    >
                      {Number(tx.amount).toLocaleString()} {tx.currency}
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {paymentMethods[tx.payment_method] || tx.payment_method}
                    </td>
                    <td className="px-4 py-3 font-mono text-slate-400">
                      {(tx as any).reference_document || (tx as any).reference_number || '--'}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500 max-w-xs truncate">
                      {tx.notes || '--'}
                    </td>
                    <td className="px-4 py-3 text-center whitespace-nowrap">
                      {tx.is_void ? (
                        <span
                          className="inline-block text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-red-100 text-red-700"
                          title={tx.void_reason || 'سند ملغي'}
                        >
                          ملغي
                        </span>
                      ) : (
                        <button
                          onClick={() => handleVoidVoucher(tx)}
                          className="text-xs font-bold text-rose-600 hover:text-rose-800 px-2 py-1 rounded-lg hover:bg-rose-50 transition-colors"
                        >
                          إلغاء السند
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modals */}
      <ReceiptVoucherModal
        isOpen={isReceiptModalOpen}
        onClose={() => setIsReceiptModalOpen(false)}
        onSuccess={fetchTransactions}
      />

      <PaymentVoucherModal
        isOpen={isPaymentModalOpen}
        onClose={() => setIsPaymentModalOpen(false)}
        onSuccess={fetchTransactions}
      />

      <ExpenseModal
        isOpen={isExpenseModalOpen}
        onClose={() => setIsExpenseModalOpen(false)}
        onSuccess={fetchTransactions}
      />
    </div>
  );
}

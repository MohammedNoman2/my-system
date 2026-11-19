/**
 * ShiftWidget — مؤشر حالة الوردية النقدية متعدد العملات في الترويسة
 * يعرض شارة مع زر لفتح/إغلاق وردية الصندوق وجرد العملات الثلاث (YER / SAR / USD)
 */
import React, { useEffect, useState, useCallback } from 'react';
import { Clock, DollarSign, X, CheckCircle, AlertTriangle, Loader2 } from 'lucide-react';
import api from '../../services/api';
import { useUIStore } from '../../context/uiStore';

interface CurrencyBalanceSummary {
  starting: number;
  total_in: number;
  total_out: number;
  current_system_balance: number;
}

interface ShiftInfo {
  id: number;
  shift_number: string;
  opened_at: string;
  starting_balance: number;
  total_in: number;
  total_out: number;
  current_system_balance: number;
  balances_by_currency?: {
    YER: CurrencyBalanceSummary;
    SAR: CurrencyBalanceSummary;
    USD: CurrencyBalanceSummary;
  };
}

interface ShiftState {
  active: boolean;
  shift: ShiftInfo | null;
}

const CURRENCIES: Array<{ code: 'YER' | 'SAR' | 'USD'; label: string; step: string }> = [
  { code: 'YER', label: 'ريال يمني (YER)', step: '100' },
  { code: 'SAR', label: 'ريال سعودي (SAR)', step: '10' },
  { code: 'USD', label: 'دولار أمريكي (USD)', step: '1' },
];

export function ShiftWidget() {
  const addToast = useUIStore((s) => s.addToast);
  const [shiftState, setShiftState] = useState<ShiftState>({ active: false, shift: null });
  const [loading] = useState(false);
  const [showModal, setShowModal] = useState<'open' | 'close' | null>(null);

  // Open shift form state (3 currencies)
  const [startingYer, setStartingYer] = useState('0');
  const [startingSar, setStartingSar] = useState('0');
  const [startingUsd, setStartingUsd] = useState('0');

  // Close shift form state (3 currencies)
  const [actualYer, setActualYer] = useState('');
  const [actualSar, setActualSar] = useState('0');
  const [actualUsd, setActualUsd] = useState('0');
  const [closeNotes, setCloseNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const fetchShiftStatus = useCallback(async () => {
    try {
      const res = await api.get('/finance/shifts/active');
      setShiftState(res.data);
    } catch {
      // Silent fail
    }
  }, []);

  useEffect(() => {
    fetchShiftStatus();
    const interval = setInterval(fetchShiftStatus, 180_000);
    return () => clearInterval(interval);
  }, [fetchShiftStatus]);

  const handleOpenShift = async () => {
    setSubmitting(true);
    try {
      const res = await api.post('/finance/shifts/open', {
        starting_balance: parseFloat(startingYer) || 0,
        starting_balance_sar: parseFloat(startingSar) || 0,
        starting_balance_usd: parseFloat(startingUsd) || 0,
      });
      addToast(`تم فتح الوردية ${res.data.shift_number} بنجاح ✅`, 'success');
      setShowModal(null);
      await fetchShiftStatus();
    } catch (e: any) {
      addToast(e.response?.data?.detail || 'فشل فتح الوردية', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCloseShift = async () => {
    if (!shiftState.shift) return;
    if (actualYer === '') {
      addToast('يجب إدخال النقدية الفعلية بالريال اليمني عند الجرد', 'error');
      return;
    }
    setSubmitting(true);
    try {
      const res = await api.post('/finance/shifts/close', {
        shift_id: shiftState.shift.id,
        actual_cash: parseFloat(actualYer) || 0,
        actual_cash_sar: parseFloat(actualSar) || 0,
        actual_cash_usd: parseFloat(actualUsd) || 0,
        notes: closeNotes || null,
      });
      const diffYer = Number(res.data.difference || 0);
      const diffSar = Number(res.data.balances_by_currency?.SAR?.difference || 0);
      const diffUsd = Number(res.data.balances_by_currency?.USD?.difference || 0);
      addToast(
        `تم إغلاق الوردية ${res.data.shift_number} ✅ | الفروق: YER ${diffYer.toLocaleString()} | SAR ${diffSar.toLocaleString()} | USD ${diffUsd.toLocaleString()}`,
        'success'
      );
      setShowModal(null);
      setActualYer('');
      setActualSar('0');
      setActualUsd('0');
      setCloseNotes('');
      await fetchShiftStatus();
    } catch (e: any) {
      addToast(e.response?.data?.detail || 'فشل إغلاق الوردية', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const getCurrencySummary = (code: 'YER' | 'SAR' | 'USD'): CurrencyBalanceSummary => {
    if (shiftState.shift?.balances_by_currency?.[code]) {
      return shiftState.shift.balances_by_currency[code];
    }
    if (code === 'YER' && shiftState.shift) {
      return {
        starting: shiftState.shift.starting_balance,
        total_in: shiftState.shift.total_in,
        total_out: shiftState.shift.total_out,
        current_system_balance: shiftState.shift.current_system_balance,
      };
    }
    return { starting: 0, total_in: 0, total_out: 0, current_system_balance: 0 };
  };

  const actualMap = {
    YER: actualYer,
    SAR: actualSar,
    USD: actualUsd,
  };

  return (
    <>
      {/* Shift Status Badge */}
      <div className="flex items-center gap-2">
        {loading ? (
          <Loader2 className="w-4 h-4 animate-spin text-slate-400" />
        ) : shiftState.active && shiftState.shift ? (
          <button
            onClick={() => {
              setActualYer('');
              setActualSar('0');
              setActualUsd('0');
              setShowModal('close');
            }}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-emerald-50 border border-emerald-200 hover:bg-emerald-100 transition-colors cursor-pointer"
            title="إغلاق الوردية"
          >
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-[11px] font-bold text-emerald-700 hidden sm:inline">
              {shiftState.shift.shift_number}
            </span>
            <Clock className="w-3.5 h-3.5 text-emerald-600" />
          </button>
        ) : (
          <button
            onClick={() => setShowModal('open')}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-red-50 border border-red-200 hover:bg-red-100 transition-colors cursor-pointer"
            title="فتح وردية"
          >
            <span className="w-2 h-2 rounded-full bg-red-500" />
            <span className="text-[11px] font-bold text-red-700 hidden sm:inline">لا وردية</span>
            <DollarSign className="w-3.5 h-3.5 text-red-600" />
          </button>
        )}
      </div>

      {/* ─── Open Shift Modal (Multi-Currency) ─────────────────────────── */}
      {showModal === 'open' && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <DollarSign className="w-5 h-5 text-emerald-600" />
                فتح وردية نقدية جديدة (متعددة العملات)
              </h2>
              <button onClick={() => setShowModal(null)} className="p-1 rounded-lg hover:bg-slate-100">
                <X className="w-5 h-5 text-slate-500" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  العهدة الافتتاحية — ريال يمني (YER)
                </label>
                <input
                  type="number"
                  min="0"
                  step="100"
                  value={startingYer}
                  onChange={(e) => setStartingYer(e.target.value)}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#1e3a8a]"
                  placeholder="0.00"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    ريال سعودي (SAR)
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="10"
                    value={startingSar}
                    onChange={(e) => setStartingSar(e.target.value)}
                    className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#1e3a8a]"
                    placeholder="0.00"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    دولار أمريكي (USD)
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="1"
                    value={startingUsd}
                    onChange={(e) => setStartingUsd(e.target.value)}
                    className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#1e3a8a]"
                    placeholder="0.00"
                  />
                </div>
              </div>

              <p className="text-xs text-slate-500">
                أدخل المبالغ النقدية الموجودة فعلياً في الصندوق لكل عملة عند بدء الوردية.
              </p>

              <button
                onClick={handleOpenShift}
                disabled={submitting}
                className="w-full py-3 rounded-xl bg-[#1e3a8a] text-white font-bold text-sm hover:bg-[#1e3a8a]/90 transition-colors disabled:opacity-60 flex items-center justify-center gap-2"
              >
                {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <DollarSign className="w-4 h-4" />}
                {submitting ? 'جاري الفتح...' : 'فتح الوردية الآن'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── Close Shift Modal (Multi-Currency) ────────────────────────── */}
      {showModal === 'close' && shiftState.shift && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 backdrop-blur-sm p-4 overflow-y-auto">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl p-6 animate-in fade-in zoom-in-95 duration-200 my-8">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <Clock className="w-5 h-5 text-amber-600" />
                إغلاق وجرد الوردية — {shiftState.shift.shift_number}
              </h2>
              <button onClick={() => setShowModal(null)} className="p-1 rounded-lg hover:bg-slate-100">
                <X className="w-5 h-5 text-slate-500" />
              </button>
            </div>

            {/* Multi-Currency Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-5">
              {CURRENCIES.map(({ code }) => {
                const summary = getCurrencySummary(code);
                const actualVal = parseFloat(actualMap[code] || '0');
                const diff = actualVal - summary.current_system_balance;
                const hasActual = actualMap[code] !== '';
                return (
                  <div key={code} className="border border-slate-200 rounded-xl p-3 bg-slate-50/70">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-bold text-slate-800">{code}</span>
                      <span className="text-[10px] text-slate-500">افتتاح: {summary.starting.toLocaleString()}</span>
                    </div>
                    <div className="text-xs space-y-1 text-slate-600 mb-2">
                      <div className="flex justify-between">
                        <span>مقبوض نقداً:</span>
                        <span className="font-semibold text-emerald-700">+{summary.total_in.toLocaleString()}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>منصرف نقداً:</span>
                        <span className="font-semibold text-rose-700">-{summary.total_out.toLocaleString()}</span>
                      </div>
                      <div className="flex justify-between border-t border-slate-200 pt-1">
                        <span className="font-bold text-slate-800">الرصيد الدفتري:</span>
                        <span className="font-bold text-blue-700">{summary.current_system_balance.toLocaleString()}</span>
                      </div>
                    </div>
                    {hasActual && (
                      <div
                        className={`text-[11px] font-bold px-2 py-1 rounded-lg flex items-center gap-1 ${
                          diff === 0
                            ? 'bg-emerald-100 text-emerald-800'
                            : diff > 0
                            ? 'bg-blue-100 text-blue-800'
                            : 'bg-red-100 text-red-800'
                        }`}
                      >
                        {diff === 0 ? (
                          <CheckCircle className="w-3.5 h-3.5 shrink-0" />
                        ) : (
                          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                        )}
                        <span>
                          {diff === 0
                            ? 'متطابق ✅'
                            : diff > 0
                            ? `فائض +${diff.toLocaleString()}`
                            : `عجز -${Math.abs(diff).toLocaleString()}`}
                        </span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    النقدية الفعلية (YER) <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="100"
                    value={actualYer}
                    onChange={(e) => setActualYer(e.target.value)}
                    className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#1e3a8a]"
                    placeholder="0.00"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    النقدية الفعلية (SAR)
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="10"
                    value={actualSar}
                    onChange={(e) => setActualSar(e.target.value)}
                    className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#1e3a8a]"
                    placeholder="0.00"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    النقدية الفعلية (USD)
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="1"
                    value={actualUsd}
                    onChange={(e) => setActualUsd(e.target.value)}
                    className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#1e3a8a]"
                    placeholder="0.00"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">ملاحظات التسليم</label>
                <textarea
                  value={closeNotes}
                  onChange={(e) => setCloseNotes(e.target.value)}
                  rows={2}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#1e3a8a]"
                  placeholder="أي ملاحظات عند تسليم الوردية..."
                />
              </div>

              <button
                onClick={handleCloseShift}
                disabled={submitting || actualYer === ''}
                className="w-full py-3 rounded-xl bg-amber-600 text-white font-bold text-sm hover:bg-amber-700 transition-colors disabled:opacity-60 flex items-center justify-center gap-2"
              >
                {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Clock className="w-4 h-4" />}
                {submitting ? 'جاري الإغلاق...' : 'إغلاق الوردية وتسليمها'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

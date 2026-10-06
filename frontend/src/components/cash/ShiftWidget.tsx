/**
 * ShiftWidget — مؤشر حالة الوردية النقدية في الترويسة
 * يعرض شارة مع زر لفتح/إغلاق وردية الصندوق
 */
import React, { useEffect, useState, useCallback } from 'react';
import { Clock, DollarSign, X, CheckCircle, AlertTriangle, Loader2 } from 'lucide-react';
import api from '../../services/api';
import { useAuthStore } from '../../context/authStore';
import { useUIStore } from '../../context/uiStore';

interface ShiftInfo {
  id: number;
  shift_number: string;
  opened_at: string;
  starting_balance: number;
  total_in: number;
  total_out: number;
  current_system_balance: number;
}

interface ShiftState {
  active: boolean;
  shift: ShiftInfo | null;
}

export function ShiftWidget() {
  const { role } = useAuthStore();
  const addToast = useUIStore((s) => s.addToast);
  const [shiftState, setShiftState] = useState<ShiftState>({ active: false, shift: null });
  const [loading, setLoading] = useState(false);
  const [showModal, setShowModal] = useState<'open' | 'close' | null>(null);

  // Form state
  const [startingBalance, setStartingBalance] = useState('0');
  const [actualCash, setActualCash] = useState('');
  const [closeNotes, setCloseNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const fetchShiftStatus = useCallback(async () => {
    try {
      const res = await api.get('/finance/shifts/active');
      setShiftState(res.data);
    } catch (e) {
      // Silent fail
    }
  }, []);

  useEffect(() => {
    fetchShiftStatus();
    const interval = setInterval(fetchShiftStatus, 60_000);
    return () => clearInterval(interval);
  }, [fetchShiftStatus]);

  const handleOpenShift = async () => {
    setSubmitting(true);
    try {
      const res = await api.post('/finance/shifts/open', {
        starting_balance: parseFloat(startingBalance) || 0,
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
    if (!actualCash) {
      addToast('يجب إدخال النقدية الفعلية عند الجرد', 'error');
      return;
    }
    setSubmitting(true);
    try {
      const res = await api.post('/finance/shifts/close', {
        shift_id: shiftState.shift.id,
        actual_cash: parseFloat(actualCash),
        notes: closeNotes || null,
      });
      const diff = res.data.difference;
      const diffText = diff >= 0 ? `فائض: ${diff.toLocaleString()} ريال` : `عجز: ${Math.abs(diff).toLocaleString()} ريال`;
      addToast(`تم إغلاق الوردية ${res.data.shift_number} ✅ | ${diffText}`, 'success');
      setShowModal(null);
      setActualCash('');
      setCloseNotes('');
      await fetchShiftStatus();
    } catch (e: any) {
      addToast(e.response?.data?.detail || 'فشل إغلاق الوردية', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const diff = shiftState.shift
    ? parseFloat(actualCash || '0') - shiftState.shift.current_system_balance
    : 0;

  return (
    <>
      {/* Shift Status Badge */}
      <div className="flex items-center gap-2">
        {loading ? (
          <Loader2 className="w-4 h-4 animate-spin text-slate-400" />
        ) : shiftState.active && shiftState.shift ? (
          <button
            onClick={() => { setActualCash(''); setShowModal('close'); }}
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

      {/* ─── Open Shift Modal ─────────────────────────────────────────── */}
      {showModal === 'open' && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <DollarSign className="w-5 h-5 text-emerald-600" />
                فتح وردية نقدية جديدة
              </h2>
              <button onClick={() => setShowModal(null)} className="p-1 rounded-lg hover:bg-slate-100">
                <X className="w-5 h-5 text-slate-500" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  العهدة النقدية الافتتاحية (ريال يمني)
                </label>
                <input
                  type="number"
                  min="0"
                  step="100"
                  value={startingBalance}
                  onChange={(e) => setStartingBalance(e.target.value)}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#1e3a8a]"
                  placeholder="0.00"
                />
                <p className="text-xs text-slate-500 mt-1">
                  المبلغ النقدي الموجود في الصندوق عند بدء الوردية
                </p>
              </div>

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

      {/* ─── Close Shift Modal ────────────────────────────────────────── */}
      {showModal === 'close' && shiftState.shift && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg p-6 animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <Clock className="w-5 h-5 text-amber-600" />
                إغلاق الوردية — {shiftState.shift.shift_number}
              </h2>
              <button onClick={() => setShowModal(null)} className="p-1 rounded-lg hover:bg-slate-100">
                <X className="w-5 h-5 text-slate-500" />
              </button>
            </div>

            {/* Summary */}
            <div className="grid grid-cols-3 gap-3 mb-5">
              {[
                { label: 'رصيد الافتتاح', value: shiftState.shift.starting_balance, color: 'slate' },
                { label: 'إجمالي المقبوض', value: shiftState.shift.total_in, color: 'emerald' },
                { label: 'الرصيد الدفتري', value: shiftState.shift.current_system_balance, color: 'blue' },
              ].map((item) => (
                <div key={item.label} className={`bg-${item.color}-50 border border-${item.color}-100 rounded-xl p-3 text-center`}>
                  <p className={`text-[10px] text-${item.color}-600 font-medium mb-1`}>{item.label}</p>
                  <p className={`text-sm font-bold text-${item.color}-800`}>
                    {item.value.toLocaleString()}
                  </p>
                  <p className="text-[9px] text-slate-400">YER</p>
                </div>
              ))}
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  النقدية الفعلية عند الجرد <span className="text-red-500">*</span>
                </label>
                <input
                  type="number"
                  min="0"
                  step="100"
                  value={actualCash}
                  onChange={(e) => setActualCash(e.target.value)}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#1e3a8a]"
                  placeholder="0.00"
                />
              </div>

              {/* Live Difference */}
              {actualCash && (
                <div className={`flex items-center gap-2 p-3 rounded-xl border ${
                  diff === 0 ? 'bg-emerald-50 border-emerald-200' :
                  diff > 0 ? 'bg-blue-50 border-blue-200' :
                  'bg-red-50 border-red-200'
                }`}>
                  {diff === 0 ? <CheckCircle className="w-4 h-4 text-emerald-600" /> :
                   <AlertTriangle className="w-4 h-4 text-amber-600" />}
                  <span className={`text-sm font-bold ${
                    diff === 0 ? 'text-emerald-700' : diff > 0 ? 'text-blue-700' : 'text-red-700'
                  }`}>
                    {diff === 0 ? 'الرصيد متطابق تماماً ✅' :
                     diff > 0 ? `فائض: +${Math.abs(diff).toLocaleString()} YER` :
                     `عجز: -${Math.abs(diff).toLocaleString()} YER`}
                  </span>
                </div>
              )}

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
                disabled={submitting || !actualCash}
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

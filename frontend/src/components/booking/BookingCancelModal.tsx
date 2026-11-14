import React, { useEffect, useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import api from '../../services/api';
import { useUIStore } from '../../context/uiStore';
import { Modal } from '../common/Modal';
import { Input } from '../common/Input';
import { Button } from '../common/Button';

interface BookingCancelModalProps {
  booking: {
    id: number;
    ticket_number: string;
    paid_amount: number;
    credit_applied?: number;
    currency?: string;
  } | null;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function BookingCancelModal({
  booking,
  isOpen,
  onClose,
  onSuccess,
}: BookingCancelModalProps) {
  const [reason, setReason] = useState('');
  const [refundAmount, setRefundAmount] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const addToast = useUIStore((state) => state.addToast);

  const creditApplied = Number(booking?.credit_applied || 0);
  const cashPaid = Math.max(
    0,
    Number((Number(booking?.paid_amount || 0) - creditApplied).toFixed(2))
  );
  const curr = booking?.currency || 'YER';

  useEffect(() => {
    if (booking && isOpen) {
      setRefundAmount(cashPaid);
      setReason('');
    }
  }, [booking, isOpen, cashPaid]);

  if (!booking) return null;

  const handleCancel = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reason.trim()) {
      addToast('يرجى كتابة سبب الإلغاء', 'error');
      return;
    }

    setIsLoading(true);
    try {
      await api.post(`/bookings/${booking.id}/cancel`, {
        reason: reason.trim(),
        refund_amount: Number(refundAmount) || 0,
      });
      addToast('تم إلغاء الحجز وتحديث الأثر المالي ورصيد العميل بنجاح', 'success');
      onSuccess();
      onClose();
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'فشل إلغاء الحجز';
      addToast(msg, 'error');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`إلغاء الحجز رقم (${booking.ticket_number})`}
      description="سيتم تغيير حالة الحجز إلى ملغي وتحديث الأثر المالي على رصيد العميل"
      size="md"
    >
      <form onSubmit={handleCancel} className="space-y-4">
        <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p>
              تنبيه: المبلغ المدفوع نقداً في هذا الحجز هو ({cashPaid.toLocaleString()} {curr}).
              أي مبلغ مسترد نقداً سيتم خصمه من الصندوق ويُسجل في سجل التدقيق.
            </p>
            {creditApplied > 0 && (
              <p className="font-bold text-emerald-800">
                سيتم تلقائياً إعادة الرصيد الدائن المخصوم ({creditApplied.toLocaleString()} {curr}) إلى رصيد العميل المتاح في حسابه.
              </p>
            )}
          </div>
        </div>

        <div>
          <label className="block text-sm font-semibold text-slate-700 mb-1">
            سبب الإلغاء <span className="text-red-500">*</span>
          </label>
          <textarea
            required
            rows={3}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="مثال: طلب العميل إلغاء السفر لظروف خاصة..."
            className="w-full rounded-lg border border-slate-300 p-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent"
          />
        </div>

        <Input
          label={`المبلغ المسترد نقداً للعميل (${curr})`}
          type="number"
          step="0.01"
          max={cashPaid}
          value={refundAmount}
          onChange={(e) => setRefundAmount(Number(e.target.value))}
          helperText={`الحد الأقصى للاسترداد النقدي: ${cashPaid.toLocaleString()} ${curr}`}
        />

        <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
          <Button type="button" variant="ghost" onClick={onClose}>
            تراجع
          </Button>
          <Button
            type="submit"
            variant="danger"
            isLoading={isLoading}
          >
            تأكيد إلغاء الحجز
          </Button>
        </div>
      </form>
    </Modal>
  );
}

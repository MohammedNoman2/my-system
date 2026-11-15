import React, { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as yup from 'yup';
import { ArrowDownLeft, CheckCircle2, RefreshCw } from 'lucide-react';
import api from '../../services/api';
import { useUIStore } from '../../context/uiStore';
import type { Customer, Supplier } from '../../types';
import { Modal } from '../common/Modal';
import { Input } from '../common/Input';
import { Select } from '../common/Select';
import { Button } from '../common/Button';

const receiptSchema = yup.object({
  entity_type: yup.string().oneOf(['customer', 'supplier']).required('نوع الجهة مطلوب'),
  entity_id: yup.number().positive('يرجى اختيار العميل أو المورد').required('الجهة مطلوبة'),
  amount: yup.number().positive('المبلغ يجب أن يكون أكبر من الصفر').required('المبلغ مطلوب'),
  currency: yup.string().default('YER'),
  payment_method: yup.string().oneOf(['cash', 'bank_transfer', 'check']).default('cash'),
  reference_document: yup.string().nullable().optional(),
  notes: yup.string().nullable().optional(),
  transaction_date: yup.string().required('تاريخ السند مطلوب'),
  booking_id: yup.number().nullable().optional(),
  exchange_rate: yup.number().positive().default(1).optional(),
});

type ReceiptFormValues = yup.InferType<typeof receiptSchema>;

interface ReceiptVoucherModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  initialCustomerId?: number;
}

export function ReceiptVoucherModal({
  isOpen,
  onClose,
  onSuccess,
  initialCustomerId,
}: ReceiptVoucherModalProps) {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [unpaidBookings, setUnpaidBookings] = useState<any[]>([]);
  const [ratesToYer, setRatesToYer] = useState<Record<string, number>>({
    YER: 1,
    SAR: 140,
    USD: 530,
  });
  const [isLoading, setIsLoading] = useState(false);
  const addToast = useUIStore((state) => state.addToast);

  const form = useForm<ReceiptFormValues>({
    resolver: yupResolver(receiptSchema) as any,
    defaultValues: {
      entity_type: 'customer',
      entity_id: initialCustomerId || undefined,
      currency: 'YER',
      payment_method: 'cash',
      transaction_date: new Date().toISOString().split('T')[0],
      exchange_rate: 1,
    },
  });

  const { register, watch, setValue, handleSubmit, reset, formState: { errors } } = form;
  const entityType = watch('entity_type');
  const entityId = watch('entity_id');
  const selectedBookingId = watch('booking_id');
  const receiptCurrency = watch('currency');
  const amount = watch('amount') || 0;
  const exchangeRate = watch('exchange_rate') || 1;

  useEffect(() => {
    if (initialCustomerId) {
      setValue('entity_id', initialCustomerId);
    }
  }, [initialCustomerId, setValue]);

  useEffect(() => {
    async function loadEntitiesAndRates() {
      try {
        const [cRes, sRes, rRes] = await Promise.all([
          api.get('/customers/?limit=1000'),
          api.get('/suppliers/?limit=1000'),
          api.get('/settings/exchange-rates').catch(() => ({ data: [] })),
        ]);
        setCustomers(cRes.data || []);
        setSuppliers(sRes.data || []);

        const rateMap: Record<string, number> = { YER: 1, SAR: 140, USD: 530 };
        if (Array.isArray(rRes.data)) {
          for (const item of rRes.data) {
            if (item.to_currency === 'YER' && Number(item.rate) > 0) {
              rateMap[String(item.from_currency).toUpperCase()] = Number(item.rate);
            }
          }
        }
        setRatesToYer(rateMap);
      } catch (err) {
        console.error('Failed to load entities', err);
      }
    }
    if (isOpen) {
      loadEntitiesAndRates();
    }
  }, [isOpen]);

  useEffect(() => {
    async function fetchBookings() {
      if (!entityId || entityType !== 'customer') {
        setUnpaidBookings([]);
        return;
      }
      try {
        const res = await api.get('/bookings/unpaid', {
          params: { customer_id: entityId },
        });
        setUnpaidBookings(res.data || []);
      } catch (err) {
        console.error('Failed to load unpaid bookings', err);
        setUnpaidBookings([]);
      }
    }
    fetchBookings();
  }, [entityId, entityType]);

  const selectedBooking = unpaidBookings.find(b => b.id === selectedBookingId);
  const isCrossCurrency = selectedBooking && selectedBooking.currency !== receiptCurrency;

  // حساب سعر الصرف الافتراضي ديناميكياً من أسعار الصرف المعتمدة في الإعدادات (كم وحدة من عملة السند مقابل 1 من عملة التذكرة)
  useEffect(() => {
    if (isCrossCurrency && selectedBooking) {
      const targetCurr = String(selectedBooking.currency || 'YER').toUpperCase();
      const voucherCurr = String(receiptCurrency || 'YER').toUpperCase();
      const targetInYer = ratesToYer[targetCurr] || 1;
      const voucherInYer = ratesToYer[voucherCurr] || 1;
      const computedUiRate = Number((targetInYer / voucherInYer).toFixed(4));
      setValue('exchange_rate', computedUiRate > 0 ? computedUiRate : 1);
    } else {
      setValue('exchange_rate', 1);
    }
  }, [receiptCurrency, selectedBooking?.currency, isCrossCurrency, ratesToYer, setValue]);

  const allocatedInBookingCurrency = isCrossCurrency ? amount / exchangeRate : amount;

  const onSubmit = async (values: ReceiptFormValues) => {
    setIsLoading(true);
    try {
      const payload: any = {
        entity_type: values.entity_type,
        entity_id: Number(values.entity_id),
        total_amount: Number(values.amount),
        currency: values.currency,
        payment_method: values.payment_method,
        reference_number: values.reference_document || null,
        notes: values.notes || null,
        transaction_date: values.transaction_date,
        allocations: []
      };

      if (values.booking_id) {
        // backend logic calculates: allocated_amount * exchange_rate
        // since our UI uses division (amount / rate), we send (1 / rate) to backend
        const rateToSend = isCrossCurrency ? (1 / Number(values.exchange_rate)) : 1;
        payload.allocations.push({
          booking_id: Number(values.booking_id),
          allocated_amount: Number(values.amount),
          exchange_rate: rateToSend
        });
      }

      const res = await api.post('/finance/receipt-voucher/v2', payload);

      addToast(`تم إصدار سند القبض بنجاح برقم (${res.data.transaction_id}) وتحديث الرصيد`, 'success');
      reset();
      onSuccess();
      onClose();
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'فشل إنشاء سند القبض';
      addToast(msg, 'error');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="إصدار سند قبض نقدية / تحويل (RC)"
      description="استلام مبالغ مالية وقيدها مع إمكانية تسوية التذاكر المفتوحة وعمليات المصارفة"
      size="lg"
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Select
            label="نوع الجهة المقبوض منها"
            required
            error={errors.entity_type?.message}
            {...register('entity_type')}
          >
            <option value="customer">عميل</option>
            <option value="supplier">مورد</option>
          </Select>

          {entityType === 'customer' ? (
            <Select
              label="اختر العميل"
              required
              error={errors.entity_id?.message}
              {...register('entity_id', { valueAsNumber: true })}
            >
              <option value="">-- اختر العميل --</option>
              {customers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          ) : (
            <Select
              label="اختر المورد"
              required
              error={errors.entity_id?.message}
              {...register('entity_id', { valueAsNumber: true })}
            >
              <option value="">-- اختر المورد --</option>
              {suppliers.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </Select>
          )}

          <div className="sm:col-span-2">
            <Select
              label="تخصيص السداد لتذكرة محددة (اختياري)"
              error={errors.booking_id?.message}
              {...register('booking_id', { valueAsNumber: true })}
            >
              <option value="">-- إضافة كرصيد دائن عام (بدون تخصيص) --</option>
              {unpaidBookings.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.ticket_number} - المتبقي: {b.remaining_amount} {b.currency}
                </option>
              ))}
            </Select>
          </div>

          <Input
            label="المبلغ المقبوض"
            type="number"
            step="0.01"
            placeholder="0.00"
            required
            error={errors.amount?.message}
            {...register('amount', { valueAsNumber: true })}
          />

          <Select
            label="عملة السند المقبوض"
            required
            error={errors.currency?.message}
            {...register('currency')}
          >
            <option value="YER">ريال يمني (YER)</option>
            <option value="SAR">ريال سعودي (SAR)</option>
            <option value="USD">دولار أمريكي (USD)</option>
          </Select>
          
          {isCrossCurrency && (
            <div className="sm:col-span-2 bg-blue-50 border border-blue-200 p-4 rounded-xl space-y-3">
              <h4 className="text-sm font-bold text-blue-800 flex items-center gap-2">
                <RefreshCw className="w-4 h-4" />
                تسوية العملات المتقاطعة (مصارفة)
              </h4>
              <p className="text-xs text-blue-700">
                التذكرة مقومة بـ {selectedBooking.currency} بينما السند المقبوض بـ {receiptCurrency}. يرجى تحديد سعر الصرف للخصم.
              </p>
              <Input
                label={`سعر الصرف (كم ${receiptCurrency} مقابل 1 ${selectedBooking.currency})`}
                type="number"
                step="0.0001"
                required={isCrossCurrency}
                error={errors.exchange_rate?.message}
                {...register('exchange_rate', { valueAsNumber: true })}
              />
              <div className="text-sm font-bold text-blue-900 bg-white p-2 rounded border border-blue-100 flex justify-between items-center">
                <span>المبلغ المعادل المخصوم من التذكرة:</span>
                <span>{allocatedInBookingCurrency.toLocaleString(undefined, { maximumFractionDigits: 2 })} {selectedBooking.currency}</span>
              </div>
            </div>
          )}

          <Select
            label="طريقة الاستلام"
            required
            error={errors.payment_method?.message}
            {...register('payment_method')}
          >
            <option value="cash">نقداً (الصندوق)</option>
            <option value="bank_transfer">حوالة / تحويل بنكي</option>
            <option value="check">شيك مصرفي</option>
          </Select>

          <Input
            label="تاريخ القبض"
            type="date"
            required
            error={errors.transaction_date?.message}
            {...register('transaction_date')}
          />

          <div className="sm:col-span-2">
            <Input
              label="رقم المستند المرجعي / رقم الحوالة أو الشيك (اختياري)"
              placeholder="مثال: حوالة كريمي رقم 12345678"
              error={errors.reference_document?.message}
              {...register('reference_document')}
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            البيان والملاحظات
          </label>
          <textarea
            rows={2}
            placeholder="دفعة عن حساب حجز تذكرة طيران..."
            className="w-full rounded-lg border border-slate-300 p-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#1e3a8a]"
            {...register('notes')}
          />
        </div>

        <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
          <Button type="button" variant="ghost" onClick={onClose}>
            إلغاء
          </Button>
          <Button
            type="submit"
            variant="primary"
            isLoading={isLoading}
            icon={<ArrowDownLeft className="w-4 h-4" />}
            className="bg-emerald-700 hover:bg-emerald-800"
          >
            إصدار سند القبض
          </Button>
        </div>
      </form>
    </Modal>
  );
}

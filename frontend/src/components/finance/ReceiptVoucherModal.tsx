import React, { useState, useEffect, useMemo } from 'react';
import { useForm } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as yup from 'yup';
import { ArrowDownLeft, Plus, Trash2, RefreshCw } from 'lucide-react';
import api from '../../services/api';
import { useUIStore } from '../../context/uiStore';
import type { Customer, Supplier } from '../../types';
import { Modal } from '../common/Modal';
import { Input } from '../common/Input';
import { Select } from '../common/Select';
import { Button } from '../common/Button';
import { EntityAutocomplete } from './EntityAutocomplete';

const receiptSchema = yup.object({
  entity_type: yup.string().oneOf(['customer', 'supplier']).required('نوع الجهة مطلوب'),
  entity_id: yup.number().positive('يرجى اختيار العميل أو المورد').required('الجهة مطلوبة'),
  amount: yup.number().positive('المبلغ يجب أن يكون أكبر من الصفر').required('المبلغ مطلوب'),
  currency: yup.string().default('YER'),
  payment_method: yup.string().oneOf(['cash', 'bank_transfer', 'check']).default('cash'),
  reference_document: yup.string().nullable().optional(),
  notes: yup.string().nullable().optional(),
  transaction_date: yup.string().required('تاريخ السند مطلوب'),
});

type ReceiptFormValues = yup.InferType<typeof receiptSchema>;

interface AllocationDraft {
  booking_id: number;
  ticket_number: string;
  booking_currency: string;
  remaining_amount: number;
  allocated_amount: number;
  ui_exchange_rate: number; // كم من عملة السند مقابل 1 من عملة التذكرة
}

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
  const [allocations, setAllocations] = useState<AllocationDraft[]>([]);
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
    },
  });

  const { register, watch, setValue, handleSubmit, reset, formState: { errors } } = form;
  const entityType = watch('entity_type');
  const entityId = watch('entity_id');
  const receiptCurrency = String(watch('currency') || 'YER').toUpperCase();
  const amount = Number(watch('amount') || 0);

  useEffect(() => {
    if (initialCustomerId) {
      setValue('entity_type', 'customer');
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
      setAllocations([]);
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

  const computeUiRate = (bookingCurr: string, voucherCurr: string) => {
    const bCurr = (bookingCurr || 'YER').toUpperCase();
    const vCurr = (voucherCurr || 'YER').toUpperCase();
    if (bCurr === vCurr) return 1;
    const targetInYer = ratesToYer[bCurr] || 1;
    const voucherInYer = ratesToYer[vCurr] || 1;
    const r = Number((targetInYer / voucherInYer).toFixed(4));
    return r > 0 ? r : 1;
  };

  // إعادة حساب سعر الصرف التلقائي للتخصيصات عند تغيير عملة السند
  useEffect(() => {
    setAllocations((prev) =>
      prev.map((a) => ({
        ...a,
        ui_exchange_rate: computeUiRate(a.booking_currency, receiptCurrency),
      }))
    );
  }, [receiptCurrency, ratesToYer]);

  const handleAddAllocation = (bookingId: number) => {
    const b = unpaidBookings.find((item) => item.id === bookingId);
    if (!b) return;
    if (allocations.some((a) => a.booking_id === bookingId)) return;

    const uiRate = computeUiRate(b.currency, receiptCurrency);
    const defaultNeededInReceiptCurr = Number((Number(b.remaining_amount) * uiRate).toFixed(2));
    const remainingBudget = Math.max(0, Number((amount - totalAllocated).toFixed(2)));
    const initialAlloc = remainingBudget > 0 ? Math.min(defaultNeededInReceiptCurr, remainingBudget) : defaultNeededInReceiptCurr;

    setAllocations((prev) => [
      ...prev,
      {
        booking_id: b.id,
        ticket_number: b.ticket_number,
        booking_currency: String(b.currency || 'YER').toUpperCase(),
        remaining_amount: Number(b.remaining_amount || 0),
        allocated_amount: initialAlloc,
        ui_exchange_rate: uiRate,
      },
    ]);
  };

  const totalAllocated = useMemo(
    () =>
      Number(
        allocations.reduce((sum, a) => sum + Number(a.allocated_amount || 0), 0).toFixed(2)
      ),
    [allocations]
  );
  const unallocatedSurplus = Number((amount - totalAllocated).toFixed(2));

  const availableToAdd = unpaidBookings.filter(
    (b) => !allocations.some((a) => a.booking_id === b.id)
  );

  const onSubmit = async (values: ReceiptFormValues) => {
    if (totalAllocated > Number(values.amount)) {
      addToast('مجموع المبالغ المخصصة للتذاكر يتجاوز إجمالي مبلغ السند', 'error');
      return;
    }

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
        allocations: allocations
          .filter((a) => Number(a.allocated_amount) > 0)
          .map((a) => {
            const isCross = a.booking_currency !== String(values.currency).toUpperCase();
            const rateToSend = isCross ? Number((1 / Number(a.ui_exchange_rate || 1)).toFixed(6)) : 1;
            return {
              booking_id: a.booking_id,
              allocated_amount: Number(a.allocated_amount),
              exchange_rate: rateToSend,
            };
          }),
      };

      const res = await api.post('/finance/receipt-voucher/v2', payload);

      addToast(`تم إصدار سند القبض بنجاح برقم (${res.data.transaction_id}) وتحديث الرصيد`, 'success');
      reset();
      setAllocations([]);
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
      description="استلام مبالغ مالية وقيدها مع إمكانية تسوية عدة تذاكر مفتوحة وعمليات المصارفة"
      size="lg"
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Select
            label="نوع الجهة المقبوض منها"
            required
            error={errors.entity_type?.message}
            {...register('entity_type', {
              onChange: () => {
                setValue('entity_id', undefined as any);
                setAllocations([]);
              },
            })}
          >
            <option value="customer">عميل</option>
            <option value="supplier">مورد</option>
          </Select>

          <EntityAutocomplete
            label={entityType === 'customer' ? 'اختر العميل (بحث بالاسم أو الهاتف)' : 'اختر المورد (بحث)'}
            options={entityType === 'customer' ? customers : suppliers}
            value={entityId}
            onChange={(id) => setValue('entity_id', id as any, { shouldValidate: true })}
            required
            error={errors.entity_id?.message}
          />

          <Input
            label="إجمالي المبلغ المقبوض"
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

        {/* Multi-Booking Allocations Section */}
        {entityType === 'customer' && entityId && (
          <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <h4 className="text-sm font-bold text-slate-800 flex items-center gap-2">
                <Plus className="w-4 h-4 text-emerald-600" />
                تخصيص السداد على تذكرة أو أكثر (اختياري)
              </h4>
              {availableToAdd.length > 0 && (
                <select
                  value=""
                  onChange={(e) => {
                    const id = Number(e.target.value);
                    if (id) handleAddAllocation(id);
                  }}
                  className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1e3a8a]"
                >
                  <option value="">+ أضف تذكرة للتسوية...</option>
                  {availableToAdd.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.ticket_number} — المتبقي: {Number(b.remaining_amount).toLocaleString()} {b.currency}
                    </option>
                  ))}
                </select>
              )}
            </div>

            {allocations.length === 0 ? (
              <p className="text-xs text-slate-500">
                {unpaidBookings.length > 0
                  ? 'يمكنك إضافة تذكرة أو عدة تذاكر من القائمة أعلاه لتسويتها، أو تركها فارغة لإضافة المبلغ كرصيد دائن للعميل.'
                  : 'لا توجد تذاكر آجلة مفتوحة لهذا العميل — سيُضاف المبلغ كرصيد دائن.'}
              </p>
            ) : (
              <div className="space-y-2">
                {allocations.map((alloc, idx) => {
                  const isCross = alloc.booking_currency !== receiptCurrency;
                  const eqBooking = isCross
                    ? Number((alloc.allocated_amount / (alloc.ui_exchange_rate || 1)).toFixed(2))
                    : alloc.allocated_amount;
                  return (
                    <div
                      key={alloc.booking_id}
                      className="bg-white border border-slate-200 rounded-lg p-3 space-y-2"
                    >
                      <div className="flex items-center justify-between">
                        <div className="text-xs font-bold text-slate-900">
                          {alloc.ticket_number}{' '}
                          <span className="font-normal text-slate-500">
                            (المتبقي: {alloc.remaining_amount.toLocaleString()} {alloc.booking_currency})
                          </span>
                        </div>
                        <button
                          type="button"
                          onClick={() =>
                            setAllocations((prev) =>
                              prev.filter((item) => item.booking_id !== alloc.booking_id)
                            )
                          }
                          className="text-red-500 hover:text-red-700 p-1"
                          title="إزالة"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>

                      <div className={`grid gap-2 ${isCross ? 'grid-cols-1 sm:grid-cols-3' : 'grid-cols-1'}`}>
                        <div>
                          <label className="block text-[11px] text-slate-600 mb-1">
                            المبلغ المخصص ({receiptCurrency})
                          </label>
                          <input
                            type="number"
                            min="0.01"
                            step="0.01"
                            value={alloc.allocated_amount}
                            onChange={(e) => {
                              const val = parseFloat(e.target.value) || 0;
                              setAllocations((prev) =>
                                prev.map((row, i) =>
                                  i === idx ? { ...row, allocated_amount: val } : row
                                )
                              );
                            }}
                            className="w-full rounded-lg border border-slate-300 px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-[#1e3a8a]"
                          />
                        </div>

                        {isCross && (
                          <>
                            <div>
                              <label className="block text-[11px] text-blue-700 mb-1 flex items-center gap-1">
                                <RefreshCw className="w-3 h-3" />
                                سعر الصرف ({receiptCurrency} / 1 {alloc.booking_currency})
                              </label>
                              <input
                                type="number"
                                min="0.0001"
                                step="0.0001"
                                value={alloc.ui_exchange_rate}
                                onChange={(e) => {
                                  const rate = parseFloat(e.target.value) || 1;
                                  setAllocations((prev) =>
                                    prev.map((row, i) =>
                                      i === idx ? { ...row, ui_exchange_rate: rate } : row
                                    )
                                  );
                                }}
                                className="w-full rounded-lg border border-blue-300 bg-blue-50/40 px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
                              />
                            </div>
                            <div className="flex flex-col justify-end">
                              <div className="text-[11px] text-slate-500">المخصوم من التذكرة:</div>
                              <div className="text-xs font-bold text-blue-800 bg-blue-50 px-2.5 py-1.5 rounded-lg border border-blue-100">
                                {eqBooking.toLocaleString()} {alloc.booking_currency}
                              </div>
                            </div>
                          </>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-slate-200 text-xs">
              <span>
                المخصص للتذاكر:{' '}
                <strong className="text-slate-900">
                  {totalAllocated.toLocaleString()} {receiptCurrency}
                </strong>
              </span>
              <span className={unallocatedSurplus < 0 ? 'text-red-600 font-bold' : 'text-emerald-700 font-bold'}>
                {unallocatedSurplus < 0
                  ? `تجاوز المبلغ بـ ${Math.abs(unallocatedSurplus).toLocaleString()} ${receiptCurrency}`
                  : `الفائض (رصيد دائن للعميل): ${unallocatedSurplus.toLocaleString()} ${receiptCurrency}`}
              </span>
            </div>
          </div>
        )}

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

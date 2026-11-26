import React, { useEffect, useState } from 'react';
import { UseFormReturn } from 'react-hook-form';
import { DollarSign, AlertCircle, Wallet } from 'lucide-react';
import { useAuthStore } from '../../context/authStore';
import api from '../../services/api';
import type { Customer, Supplier } from '../../types';
import { Input } from '../common/Input';
import { Select } from '../common/Select';
import { SupplierAutocomplete } from './SupplierAutocomplete';

interface BookingFinancialStepProps {
  form: UseFormReturn<any>;
  selectedCustomer?: Customer | null;
  passengerCount?: number;
}

export function BookingFinancialStep({ form, selectedCustomer, passengerCount = 1 }: BookingFinancialStepProps) {
  const { role } = useAuthStore();
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [creditBalances, setCreditBalances] = useState<Record<string, number>>({});
  const isEmployee = role === 'employee';

  const { register, watch, setValue, formState: { errors } } = form;

  const count = Math.max(1, passengerCount);
  const unitSellingPrice = Number(watch('selling_price') || 0);
  const sellingPrice = Number((unitSellingPrice * count).toFixed(2));
  const paidAmount = Number(watch('paid_amount') || 0);
  const currency = String(watch('currency') || 'YER').toUpperCase();
  const useCreditBalance = watch('use_credit_balance') !== false;
  const paymentMethod = watch('payment_method') || 'cash';

  const passengerPhone =
    watch('passenger_phone') || watch('applicant_phone') || watch('sender_phone') || '';
  const passengerName =
    watch('passenger_name') || watch('applicant_name') || watch('sender_name') || '';

  const availableCredit = Number(creditBalances[currency] || 0);
  // الخادم يخصم الرصيد الدائن المتاح أولاً من سعر البيع، ثم يُسدّد المتبقي نقداً/بنكياً/آجلاً
  const effectivePaid = paymentMethod === 'deferred' ? 0 : paidAmount;
  const creditApplied = useCreditBalance
    ? Math.min(availableCredit, sellingPrice)
    : 0;
  const remainingAfterCredit = Math.max(
    0,
    Number((sellingPrice - creditApplied).toFixed(2))
  );
  const remainingAmount = Math.max(
    0,
    Number((remainingAfterCredit - effectivePaid).toFixed(2))
  );
  const cashExceedsAfterCredit = paymentMethod !== 'deferred' && effectivePaid > remainingAfterCredit + 0.01;

  // Initialize use_credit_balance and payment_method if unset
  useEffect(() => {
    if (watch('use_credit_balance') === undefined) {
      setValue('use_credit_balance', true);
    }
    if (!watch('payment_method')) {
      setValue('payment_method', 'cash');
    }
  }, [setValue, watch]);

  // Update remaining_amount in form whenever selling_price, paid_amount, payment_method, or creditApplied changes
  useEffect(() => {
    setValue('remaining_amount', remainingAmount, { shouldValidate: true });
  }, [sellingPrice, effectivePaid, remainingAmount, setValue]);

  // When paymentMethod switches to 'deferred', force paid_amount to 0
  useEffect(() => {
    if (paymentMethod === 'deferred') {
      setValue('paid_amount', 0, { shouldValidate: true });
    }
  }, [paymentMethod, setValue]);

  // Resolve credit_balances strictly from selectedCustomer (or single exact phone+name match)
  useEffect(() => {
    let isCancelled = false;

    async function resolveCreditBalances() {
      if (selectedCustomer) {
        if (selectedCustomer.credit_balances) {
          setCreditBalances(selectedCustomer.credit_balances);
          return;
        }
        try {
          const res = await api.get(`/customers/${selectedCustomer.id}`);
          if (!isCancelled && res.data?.credit_balances) {
            setCreditBalances(res.data.credit_balances);
          }
        } catch {
          if (!isCancelled) setCreditBalances({});
        }
        return;
      }

      const cleanPhone = String(passengerPhone).replace(/\D/g, '').trim();
      const cleanName = String(passengerName).trim().replace(/\s+/g, ' ');
      if (cleanPhone.length < 9 || !cleanName) {
        setCreditBalances({});
        return;
      }

      try {
        const res = await api.get('/customers/search', {
          params: { q: cleanPhone, limit: 10 },
        });
        const items: Customer[] = Array.isArray(res.data) ? res.data : [];
        const exactPhoneItems = items.filter(
          (c) => String(c.phone_number).replace(/\D/g, '') === cleanPhone
        );
        if (
          !isCancelled &&
          exactPhoneItems.length === 1 &&
          exactPhoneItems[0].name.trim().replace(/\s+/g, ' ') === cleanName &&
          exactPhoneItems[0].credit_balances
        ) {
          setCreditBalances(exactPhoneItems[0].credit_balances);
        } else if (!isCancelled) {
          setCreditBalances({});
        }
      } catch {
        if (!isCancelled) setCreditBalances({});
      }
    }

    resolveCreditBalances();
    return () => {
      isCancelled = true;
    };
  }, [selectedCustomer, passengerPhone, passengerName]);

  // Load suppliers
  useEffect(() => {
    async function loadSuppliers() {
      try {
        const res = await api.get('/suppliers/');
        setSuppliers(res.data);
      } catch (err) {
        console.error('Failed to load suppliers', err);
      }
    }
    loadSuppliers();
  }, []);

  return (
    <div className="space-y-6">
      <div className="bg-slate-50/80 p-4 rounded-xl border border-slate-200">
        <h4 className="text-sm font-bold text-slate-800 mb-4 flex items-center gap-2">
          <DollarSign className="w-4 h-4 text-emerald-600" />
          البيانات المالية للحجز والأسعار
        </h4>

        {availableCredit > 0 && (
          <div className="mb-4 p-3.5 bg-emerald-50 border border-emerald-200 rounded-xl flex items-start gap-3">
            <Wallet className="w-5 h-5 text-emerald-700 shrink-0 mt-0.5" />
            <div className="text-xs text-emerald-900 space-y-1.5 flex-1">
              <p className="font-bold text-sm">
                لدى العميل رصيد دائن متاح في حسابه ({currency}): {availableCredit.toLocaleString()} {currency}
              </p>
              <label className="inline-flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  className="rounded border-emerald-400 text-emerald-700 focus:ring-emerald-600"
                  checked={useCreditBalance}
                  onChange={(e) => setValue('use_credit_balance', e.target.checked, { shouldValidate: true })}
                />
                <span className="font-semibold">
                  خصم الرصيد الدائن المتاح ({Math.min(availableCredit, Math.max(0, sellingPrice - effectivePaid)).toLocaleString()} {currency}) تلقائياً من هذا الحجز
                </span>
              </label>
              {creditApplied > 0 && (
                <p className="text-emerald-700 font-medium">
                  ✓ سيتم استهلاك {creditApplied.toLocaleString()} {currency} من الرصيد الدائن، والمتبقي نقداً/آجلاً: {remainingAmount.toLocaleString()} {currency}
                </p>
              )}
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Input
            label="سعر البيع (للعميل) *"
            type="number"
            step="0.01"
            placeholder="0.00"
            {...register('selling_price', {
              required: 'سعر البيع مطلوب',
              min: { value: 0.01, message: 'يجب أن يكون أكبر من صفر' }
            })}
            error={errors.selling_price?.message as string}
          />

          {!isEmployee && (
            <Input
              label="سعر التكلفة (شراء) *"
              type="number"
              step="0.01"
              placeholder="0.00"
              {...register('cost_price', {
                required: 'سعر التكلفة مطلوب',
                min: { value: 0, message: 'لا يمكن أن يكون سالباً' }
              })}
              error={errors.cost_price?.message as string}
            />
          )}

          <Select
            label="العملة *"
            {...register('currency', { required: 'العملة مطلوبة' })}
            error={errors.currency?.message as string}
            options={[
              { value: 'YER', label: 'ريال يمني (YER)' },
              { value: 'SAR', label: 'ريال سعودي (SAR)' },
              { value: 'USD', label: 'دولار أمريكي (USD)' },
            ]}
          />
        </div>

        {/* طريقة السداد وقناة الدفع */}
        <div className="mt-4 pt-4 border-t border-slate-200/80">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Select
              label="طريقة السداد *"
              {...register('payment_method', { required: 'طريقة السداد مطلوبة' })}
              error={errors.payment_method?.message as string}
              options={[
                { value: 'cash', label: 'نقداً في الصندوق (1101)' },
                { value: 'bank_transfer', label: 'تحويل بنكي / صرافة (1102)' },
                { value: 'check', label: 'شيك بنكي (1102)' },
                { value: 'deferred', label: 'آجل بالكامل (بدون دفعة نقدية فورية)' },
              ]}
            />

            {paymentMethod !== 'deferred' && (
              <Input
                label="الدفعة المقدمة المدفوعة الآن"
                type="number"
                step="0.01"
                placeholder="0.00"
                {...register('paid_amount', {
                  min: { value: 0, message: 'لا يمكن أن تكون سالبة' }
                })}
                error={
                  (errors.paid_amount?.message as string) ||
                  (cashExceedsAfterCredit
                    ? `المبلغ يتجاوز المتبقي بعد الرصيد الدائن (${remainingAfterCredit.toLocaleString()} ${currency}). ألغِ تفعيل خصم الرصيد الدائن إذا أردت دفع كامل المبلغ نقداً.`
                    : undefined)
                }
              />
            )}

            {(paymentMethod === 'bank_transfer' || paymentMethod === 'check') && (
              <Input
                label="رقم المرجع / الإشعار / الشيك"
                type="text"
                placeholder="مثال: حوالة #884920 أو إيداع بنكي"
                {...register('reference_number')}
                error={errors.reference_number?.message as string}
              />
            )}
          </div>
        </div>

        {/* ملخص الحساب */}
        <div className="mt-4 p-3 bg-white rounded-lg border border-slate-200 flex flex-wrap items-center justify-between gap-3 text-xs">
          <div>
            <span className="text-slate-500">
              {count > 1 ? `إجمالي البيع (${count} أفراد): ` : 'سعر البيع: '}
            </span>
            <span className="font-bold text-slate-800">{sellingPrice.toLocaleString()} {currency}</span>
          </div>
          {paymentMethod !== 'deferred' && (
            <div>
              <span className="text-slate-500">المدفوع نقداً/بنكياً: </span>
              <span className="font-bold text-emerald-600">{paidAmount.toLocaleString()} {currency}</span>
            </div>
          )}
          {creditApplied > 0 && (
            <div>
              <span className="text-slate-500">مخصوم من الرصيد الدائن: </span>
              <span className="font-bold text-indigo-600">{creditApplied.toLocaleString()} {currency}</span>
            </div>
          )}
          <div>
            <span className="text-slate-500">المتبقي على العميل: </span>
            <span className={`font-bold ${remainingAmount > 0 ? 'text-amber-600' : 'text-emerald-600'}`}>
              {remainingAmount.toLocaleString()} {currency}
            </span>
          </div>
        </div>

        {!isEmployee && (
          <div className="mt-4 pt-4 border-t border-slate-200">
            <SupplierAutocomplete
              suppliers={suppliers}
              supplierId={watch('supplier_id')}
              supplierName={watch('supplier_name')}
              onSelectExisting={(s) => {
                setValue('supplier_id', String(s.id), { shouldValidate: true });
                setValue('supplier_name', s.name);
              }}
              onManualChange={(name) => {
                setValue('supplier_id', '', { shouldValidate: true });
                setValue('supplier_name', name, { shouldValidate: true });
              }}
              error={(errors.supplier_id?.message || errors.supplier_name?.message) as string}
            />
          </div>
        )}

        <div className="mt-4">
          <Input
            label="ملاحظات مالية أو تفاصيل إضافية"
            type="text"
            placeholder="مثال: تم الاتفاق على السداد عند الاستلام أو تحويل رقم..."
            {...register('notes')}
          />
        </div>
      </div>
    </div>
  );
}

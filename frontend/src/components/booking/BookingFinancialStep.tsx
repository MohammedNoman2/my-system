import React, { useEffect, useState } from 'react';
import { UseFormReturn } from 'react-hook-form';
import { DollarSign, AlertCircle, Wallet } from 'lucide-react';
import { useAuthStore } from '../../context/authStore';
import api from '../../services/api';
import type { Customer, Supplier } from '../../types';
import { Input } from '../common/Input';
import { Select } from '../common/Select';

interface BookingFinancialStepProps {
  form: UseFormReturn<any>;
  selectedCustomer?: Customer | null;
}

export function BookingFinancialStep({ form, selectedCustomer }: BookingFinancialStepProps) {
  const { role } = useAuthStore();
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [creditBalances, setCreditBalances] = useState<Record<string, number>>({});
  const isEmployee = role === 'employee';

  const { register, watch, setValue, formState: { errors } } = form;

  const sellingPrice = Number(watch('selling_price') || 0);
  const paidAmount = Number(watch('paid_amount') || 0);
  const currency = String(watch('currency') || 'YER').toUpperCase();
  const useCreditBalance = watch('use_credit_balance') !== false;

  const passengerPhone =
    watch('passenger_phone') || watch('applicant_phone') || watch('sender_phone') || '';
  const passengerName =
    watch('passenger_name') || watch('applicant_name') || watch('sender_name') || '';

  const availableCredit = Number(creditBalances[currency] || 0);
  const creditApplied = useCreditBalance
    ? Math.min(availableCredit, Math.max(0, sellingPrice - paidAmount))
    : 0;
  const remainingAmount = Math.max(
    0,
    Number((sellingPrice - paidAmount - creditApplied).toFixed(2))
  );

  // Initialize use_credit_balance to true if unset
  useEffect(() => {
    if (watch('use_credit_balance') === undefined) {
      setValue('use_credit_balance', true);
    }
  }, [setValue, watch]);

  // Update remaining_amount in form whenever selling_price, paid_amount, or creditApplied changes
  useEffect(() => {
    setValue('remaining_amount', remainingAmount, { shouldValidate: true });
  }, [sellingPrice, paidAmount, remainingAmount, setValue]);

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
                  خصم الرصيد الدائن المتاح ({Math.min(availableCredit, Math.max(0, sellingPrice - paidAmount)).toLocaleString()} {currency}) تلقائياً من هذا الحجز
                </span>
              </label>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* Selling Price */}
          <Input
            label="سعر البيع للعميل"
            type="number"
            step="0.01"
            placeholder="0.00"
            required
            error={errors.selling_price?.message as string}
            {...register('selling_price', { valueAsNumber: true })}
          />

          {/* Paid Amount */}
          <Input
            label="المبلغ المدفوع نقداً الآن"
            type="number"
            step="0.01"
            placeholder="0.00"
            error={errors.paid_amount?.message as string}
            {...register('paid_amount', { valueAsNumber: true })}
          />

          {/* Remaining Amount (Readonly) */}
          <div className="w-full">
            <label className="block text-sm font-medium text-slate-700 mb-1">
              صافي المتبقي على العميل (آلياً)
            </label>
            <div className="w-full rounded-lg border border-slate-200 bg-slate-100 px-3 py-2 text-sm font-bold text-slate-800">
              {remainingAmount.toLocaleString()} {currency}
              {creditApplied > 0 && (
                <span className="mr-2 text-xs font-semibold text-emerald-700">
                  (شمل خصم {creditApplied.toLocaleString()} {currency} رصيد دائن)
                </span>
              )}
            </div>
          </div>

          {/* Currency */}
          <Select
            label="العملة"
            required
            error={errors.currency?.message as string}
            {...register('currency')}
          >
            <option value="YER">ريال يمني (YER)</option>
            <option value="SAR">ريال سعودي (SAR)</option>
            <option value="USD">دولار أمريكي (USD)</option>
          </Select>

          {/* Supplier with free-text & autocomplete */}
          <div className="w-full">
            <label className="block text-sm font-medium text-slate-700 mb-1">
              المورد / الشركة المصدرة
            </label>
            <input
              type="text"
              list="suppliers-datalist"
              placeholder="اختر مورداً أو اكتب اسماً جديداً..."
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#1e3a8a] focus:border-transparent bg-white"
              onChange={(e) => {
                const val = e.target.value;
                const matched = suppliers.find((s) => s.name.trim().toLowerCase() === val.trim().toLowerCase());
                if (matched) {
                  setValue('supplier_id', matched.id);
                  setValue('supplier_name', matched.name);
                } else {
                  setValue('supplier_id', null);
                  setValue('supplier_name', val.trim() || null);
                }
              }}
            />
            <datalist id="suppliers-datalist">
              {suppliers.map((s) => (
                <option key={s.id} value={s.name}>
                  {s.service_type ? `${s.name} (${s.service_type})` : s.name}
                </option>
              ))}
            </datalist>
            <span className="text-[11px] text-slate-500 mt-1 block">
              يمكنك الاختيار من القائمة أو كتابة اسم مورد جديد مباشرة لتوليد حسابه تلقائياً
            </span>
          </div>

          {/* Cost Price: Strictly hidden / absent from DOM for employee (§1, §3) */}
          {!isEmployee && (
            <Input
              label="سعر التكلفة (خاص بالإدارة والمحاسبة)"
              type="number"
              step="0.01"
              placeholder="0.00"
              error={errors.cost_price?.message as string}
              {...register('cost_price', { valueAsNumber: true })}
            />
          )}
        </div>

        {paidAmount > sellingPrice && (
          <div className="mt-3 p-3 bg-red-50 text-red-700 text-xs rounded-lg flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>تنبيه: المبلغ المدفوع أكبر من سعر البيع! يرجى تصحيح القيمة.</span>
          </div>
        )}
      </div>

      {/* Notes */}
      <div>
        <label className="block text-sm font-medium text-slate-700 mb-1">
          ملاحظات وتفاصيل إضافية حول الحجز
        </label>
        <textarea
          rows={3}
          placeholder="أي تعليمات أو ملاحظات خاصة بالحجز والعميل..."
          className="w-full rounded-lg border border-slate-300 bg-white p-3 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#1e3a8a] focus:border-transparent"
          {...register('notes')}
        />
      </div>
    </div>
  );
}

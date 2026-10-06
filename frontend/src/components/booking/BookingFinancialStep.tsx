import React, { useEffect, useState } from 'react';
import { UseFormReturn } from 'react-hook-form';
import { DollarSign, Building2, FileText, AlertCircle } from 'lucide-react';
import { useAuthStore } from '../../context/authStore';
import api from '../../services/api';
import type { Supplier } from '../../types';
import { Input } from '../common/Input';
import { Select } from '../common/Select';

interface BookingFinancialStepProps {
  form: UseFormReturn<any>;
}

export function BookingFinancialStep({ form }: BookingFinancialStepProps) {
  const { role } = useAuthStore();
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const isEmployee = role === 'employee';

  const { register, watch, setValue, formState: { errors } } = form;

  const sellingPrice = Number(watch('selling_price') || 0);
  const paidAmount = Number(watch('paid_amount') || 0);
  const remainingAmount = Math.max(0, sellingPrice - paidAmount);

  // Update remaining_amount in form whenever selling_price or paid_amount changes
  useEffect(() => {
    setValue('remaining_amount', remainingAmount, { shouldValidate: true });
  }, [sellingPrice, paidAmount, remainingAmount, setValue]);

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
            label="المبلغ المدفوع مقدماً"
            type="number"
            step="0.01"
            placeholder="0.00"
            error={errors.paid_amount?.message as string}
            {...register('paid_amount', { valueAsNumber: true })}
          />

          {/* Remaining Amount (Readonly) */}
          <div className="w-full">
            <label className="block text-sm font-medium text-slate-700 mb-1">
              المبلغ المتبقي (آلياً)
            </label>
            <div className="w-full rounded-lg border border-slate-200 bg-slate-100 px-3 py-2 text-sm font-bold text-slate-800">
              {remainingAmount.toLocaleString()} {watch('currency') || 'YER'}
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

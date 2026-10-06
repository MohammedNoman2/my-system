import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as yup from 'yup';
import { Receipt, CheckCircle2 } from 'lucide-react';
import api from '../../services/api';
import { useUIStore } from '../../context/uiStore';
import { Modal } from '../common/Modal';
import { Input } from '../common/Input';
import { Select } from '../common/Select';
import { Button } from '../common/Button';

const expenseSchema = yup.object({
  expense_type: yup.string().required('نوع وبند المصروف مطلوب (نص حر)'),
  amount: yup.number().positive('المبلغ يجب أن يكون أكبر من الصفر').required('المبلغ مطلوب'),
  currency: yup.string().default('YER'),
  payment_method: yup.string().oneOf(['cash', 'bank_transfer', 'credit', 'cheque']).default('cash'),
  reference_number: yup.string().nullable().optional(),
  notes: yup.string().nullable().optional(),
  transaction_date: yup.string().required('تاريخ المصروف مطلوب'),
});

type ExpenseFormValues = yup.InferType<typeof expenseSchema>;

interface ExpenseModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function ExpenseModal({ isOpen, onClose, onSuccess }: ExpenseModalProps) {
  const [isLoading, setIsLoading] = useState(false);
  const addToast = useUIStore((state) => state.addToast);

  const form = useForm<ExpenseFormValues>({
    resolver: yupResolver(expenseSchema) as any,
    defaultValues: {
      currency: 'YER',
      payment_method: 'cash',
      transaction_date: new Date().toISOString().split('T')[0],
    },
  });

  const { register, handleSubmit, reset, formState: { errors } } = form;

  const onSubmit = async (values: ExpenseFormValues) => {
    setIsLoading(true);
    try {
      const res = await api.post('/finance/expense', {
        expense_type: values.expense_type,
        amount: Number(values.amount),
        currency: values.currency,
        payment_method: values.payment_method,
        reference_number: values.reference_number || null,
        notes: values.notes || null,
        transaction_date: values.transaction_date,
      });

      addToast(`تم قيد المصروف بنجاح برقم (${res.data.transaction_id})`, 'success');
      reset();
      onSuccess();
      onClose();
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'فشل تسجيل المصروف';
      addToast(msg, 'error');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="تسجيل مصروف تشغيلي / إداري (EX)"
      description="إثبات المصروفات التشغيلية للمكتب (إيجار، كهرباء، إنترنت، ضيافة، قرطاسية...)"
      size="md"
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <Input
          label="بند / نوع المصروف (نص حر)"
          placeholder="مثال: إيجار شهر مارس / فاتورة كهرباء وإنترنت..."
          required
          error={errors.expense_type?.message}
          {...register('expense_type')}
        />

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Input
            label="المبلغ"
            type="number"
            step="0.01"
            placeholder="0.00"
            required
            error={errors.amount?.message}
            {...register('amount', { valueAsNumber: true })}
          />

          <Select
            label="العملة"
            required
            error={errors.currency?.message}
            {...register('currency')}
          >
            <option value="YER">ريال يمني (YER)</option>
            <option value="SAR">ريال سعودي (SAR)</option>
            <option value="USD">دولار أمريكي (USD)</option>
          </Select>

          <Select
            label="طريقة الدفع"
            required
            error={errors.payment_method?.message}
            {...register('payment_method')}
          >
            <option value="cash">نقداً (الصندوق)</option>
            <option value="bank_transfer">تحويل بنكي</option>
            <option value="cheque">شيك</option>
            <option value="credit">آجل</option>
          </Select>

          <Input
            label="تاريخ الصرف"
            type="date"
            required
            error={errors.transaction_date?.message}
            {...register('transaction_date')}
          />
        </div>

        <Input
          label="رقم الفاتورة أو المستند الخارجي (اختياري)"
          placeholder="مثال: فاتورة رقم 4587"
          error={errors.reference_number?.message}
          {...register('reference_number')}
        />

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            ملاحظات إضافية
          </label>
          <textarea
            rows={2}
            placeholder="أي تفاصيل حول المصروف والمستلم..."
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
            variant="danger"
            isLoading={isLoading}
            icon={<Receipt className="w-4 h-4" />}
          >
            حفظ وقيد المصروف
          </Button>
        </div>
      </form>
    </Modal>
  );
}

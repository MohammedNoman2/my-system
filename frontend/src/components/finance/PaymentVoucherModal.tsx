import React, { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as yup from 'yup';
import { ArrowUpRight } from 'lucide-react';
import api from '../../services/api';
import { useUIStore } from '../../context/uiStore';
import type { Customer, Supplier } from '../../types';
import { Modal } from '../common/Modal';
import { Input } from '../common/Input';
import { Select } from '../common/Select';
import { Button } from '../common/Button';

const paymentSchema = yup.object({
  entity_type: yup.string().oneOf(['customer', 'supplier']).required('نوع الجهة مطلوب'),
  entity_id: yup.number().positive('يرجى اختيار الجهة').required('الجهة مطلوبة'),
  amount: yup.number().positive('المبلغ يجب أن يكون أكبر من الصفر').required('المبلغ مطلوب'),
  currency: yup.string().default('YER'),
  payment_method: yup.string().oneOf(['cash', 'bank_transfer', 'check']).default('cash'),
  reference_document: yup.string().nullable().optional(),
  notes: yup.string().nullable().optional(),
  transaction_date: yup.string().required('تاريخ السند مطلوب'),
});

type PaymentFormValues = yup.InferType<typeof paymentSchema>;

interface PaymentVoucherModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  initialSupplierId?: number;
}

export function PaymentVoucherModal({
  isOpen,
  onClose,
  onSuccess,
  initialSupplierId,
}: PaymentVoucherModalProps) {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const addToast = useUIStore((state) => state.addToast);

  const form = useForm<PaymentFormValues>({
    resolver: yupResolver(paymentSchema) as any,
    defaultValues: {
      entity_type: 'supplier',
      entity_id: initialSupplierId || undefined,
      currency: 'YER',
      payment_method: 'cash',
      transaction_date: new Date().toISOString().split('T')[0],
    },
  });

  const { register, watch, setValue, handleSubmit, reset, formState: { errors } } = form;
  const entityType = watch('entity_type');

  useEffect(() => {
    if (initialSupplierId) {
      setValue('entity_id', initialSupplierId);
    }
  }, [initialSupplierId, setValue]);

  useEffect(() => {
    async function loadEntities() {
      try {
        const [cRes, sRes] = await Promise.all([
          api.get('/customers/?limit=1000'),
          api.get('/suppliers/?limit=1000'),
        ]);
        setCustomers(cRes.data);
        setSuppliers(sRes.data);
      } catch (err) {
        console.error('Failed to load entities', err);
      }
    }
    if (isOpen) {
      loadEntities();
    }
  }, [isOpen]);

  const onSubmit = async (values: PaymentFormValues) => {
    setIsLoading(true);
    try {
      const res = await api.post('/finance/payment-voucher', {
        entity_type: values.entity_type,
        entity_id: Number(values.entity_id),
        amount: Number(values.amount),
        currency: values.currency,
        payment_method: values.payment_method,
        reference_number: values.reference_document || null,
        notes: values.notes || null,
        transaction_date: values.transaction_date,
      });

      addToast(`تم إصدار سند الصرف بنجاح برقم (${res.data.transaction_id}) وتحديث الرصيد`, 'success');
      reset();
      onSuccess();
      onClose();
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'فشل إنشاء سند الصرف';
      addToast(msg, 'error');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="إصدار سند صرف / دفع (PY)"
      description="صرف مبالغ مالية لمورد أو تسوية مستحقات وتخفيض رصيده"
      size="lg"
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Select
            label="نوع الجهة المصروف لها"
            required
            error={errors.entity_type?.message}
            {...register('entity_type')}
          >
            <option value="supplier">مورد / شركة طيران أو نقل</option>
            <option value="customer">عميل (مستردات)</option>
          </Select>

          {entityType === 'supplier' ? (
            <Select
              label="اختر المورد"
              required
              error={errors.entity_id?.message}
              {...register('entity_id', { valueAsNumber: true })}
            >
              <option value="">-- اختر المورد --</option>
              {suppliers.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} (رصيد مستحق له: {Number(s.balance).toLocaleString()} YER)
                </option>
              ))}
            </Select>
          ) : (
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
          )}

          <Input
            label="المبلغ المصروف"
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
            label="طريقة الصرف"
            required
            error={errors.payment_method?.message}
            {...register('payment_method')}
          >
            <option value="cash">نقداً (الصندوق)</option>
            <option value="bank_transfer">حوالة / تحويل بنكي</option>
            <option value="check">شيك مصرفي</option>
          </Select>

          <Input
            label="تاريخ الصرف"
            type="date"
            required
            error={errors.transaction_date?.message}
            {...register('transaction_date')}
          />

          <div className="sm:col-span-2">
            <Input
              label="رقم المستند المرجعي / رقم السند أو الإشعار البنكي"
              placeholder="مثال: إشعار تحويل بنكي رقم 987654"
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
            placeholder="سداد مستحقات تذاكر طيران عن شهر..."
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
            icon={<ArrowUpRight className="w-4 h-4" />}
            className="bg-[#d97706] hover:bg-[#b45309]"
          >
            إصدار سند الصرف
          </Button>
        </div>
      </form>
    </Modal>
  );
}

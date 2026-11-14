import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as yup from 'yup';
import { BookOpen, ArrowLeft, ArrowRight, CheckCircle2 } from 'lucide-react';
import { useAuthStore } from '../../context/authStore';
import api from '../../services/api';
import type { Customer } from '../../types';
import { useUIStore } from '../../context/uiStore';
import { StepperForm } from './StepperForm';
import { CustomerSearch } from './CustomerSearch';
import { OcrScanButton } from './OcrScanButton';
import { BookingFinancialStep } from './BookingFinancialStep';
import { Input } from '../common/Input';
import { Select } from '../common/Select';
import { Button } from '../common/Button';

const passportSchema = yup.object({
  // Step 1: Passport transaction details
  passport_type: yup.string().oneOf(['new', 'renewal', 'lost', 'damaged']).default('new'),
  priority: yup.string().oneOf(['normal', 'urgent']).default('normal'),
  application_date: yup.string().required('تاريخ التقديم مطلوب'),
  expected_delivery_date: yup.string().nullable().optional(),

  // Step 2: Applicant details
  applicant_name: yup.string().required('اسم صاحب الجواز مطلوب'),
  applicant_phone: yup.string().required('رقم الهاتف مطلوب'),
  id_number: yup.string().required('رقم البطاقة الشخصية مطلوب'),
  birth_date: yup.string().required('تاريخ الميلاد مطلوب'),
  birth_place: yup.string().required('مكان الميلاد مطلوب'),

  // Step 3: Financials
  selling_price: yup.number().positive('سعر البيع يجب أن يكون أكبر من الصفر').required('سعر البيع مطلوب'),
  paid_amount: yup.number().min(0).default(0),
  remaining_amount: yup.number().default(0),
  currency: yup.string().default('YER'),
  supplier_id: yup.string().nullable().optional(),
  cost_price: yup.number().min(0).optional(),
  notes: yup.string().nullable().optional(),
});

type PassportFormValues = yup.InferType<typeof passportSchema>;

interface PassportBookingFormProps {
  onSuccess: (bookingId: number) => void;
  onCancel: () => void;
}

const STEPS = [
  { id: 1, title: 'نوع المعاملة والجواز', description: 'نوع الطلب ومستوى الأولوية' },
  { id: 2, title: 'بيانات صاحب الجواز', description: 'الهوية والمعلومات الشخصية' },
  { id: 3, title: 'المالية والتأكيد', description: 'الرسوم وتأكيد الحجز' },
];

export function PassportBookingForm({ onSuccess, onCancel }: PassportBookingFormProps) {
  const [currentStep, setCurrentStep] = useState(1);
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const addToast = useUIStore((state) => state.addToast);

  const { role } = useAuthStore();
  const isEmployee = role === 'employee';

  const form = useForm<PassportFormValues>({
    resolver: yupResolver(passportSchema) as any,
    defaultValues: {
      passport_type: 'new',
      priority: 'normal',
      currency: 'YER',
      paid_amount: 0,
      cost_price: 0,
      application_date: new Date().toISOString().split('T')[0],
    },
    mode: 'onTouched',
  });

  const { register, setValue, trigger, handleSubmit, formState: { errors } } = form;

  const handleCustomerSelect = (customer: Customer | null) => {
    setSelectedCustomer(customer);
    if (customer) {
      setValue('applicant_name', customer.name, { shouldValidate: true });
      setValue('applicant_phone', customer.phone_number, { shouldValidate: true });
      if (customer.id_number) {
        setValue('id_number', customer.id_number, { shouldValidate: true });
      }
    }
  };

  const handleOcrExtracted = (data: any) => {
    if (data.passenger_name) setValue('applicant_name', data.passenger_name, { shouldValidate: true });
    if (data.id_number) setValue('id_number', data.id_number, { shouldValidate: true });
    if (data.birth_date) setValue('birth_date', data.birth_date, { shouldValidate: true });
    if (data.birth_place) setValue('birth_place', data.birth_place, { shouldValidate: true });
  };

  const nextStep = async () => {
    let fieldsToValidate: (keyof PassportFormValues)[] = [];
    if (currentStep === 1) {
      fieldsToValidate = ['passport_type', 'priority', 'application_date'];
    } else if (currentStep === 2) {
      fieldsToValidate = ['applicant_name', 'applicant_phone', 'id_number', 'birth_date', 'birth_place'];
    }

    const isValid = await trigger(fieldsToValidate);
    if (isValid) setCurrentStep((prev) => prev + 1);
  };

  const prevStep = () => setCurrentStep((prev) => prev - 1);

  const onSubmit = async (values: PassportFormValues) => {
    setIsSubmitting(true);
    try {
      const payload = {
        type: 'passport',
        customer_id: selectedCustomer ? selectedCustomer.id : null,
        selling_price: values.selling_price,
        paid_amount: values.paid_amount || 0,
        currency: values.currency,
        supplier_id: values.supplier_id ? Number(values.supplier_id) : null,
        supplier_name: (values as any).supplier_name || null,
        ...(isEmployee ? {} : { cost_price: values.cost_price || 0 }),
        notes: values.notes || null,
        use_credit_balance: (values as any).use_credit_balance ?? true,
        passport_details: {
          passport_type: values.passport_type,
          priority: values.priority,
          application_date: values.application_date,
          expected_delivery_date: values.expected_delivery_date || null,
          applicant_name: values.applicant_name,
          applicant_phone: values.applicant_phone,
          id_number: values.id_number,
          birth_date: values.birth_date,
          birth_place: values.birth_place,
        },
      };

      const res = await api.post('/bookings/', payload);
      addToast('تم إنشاء معاملة الجواز بنجاح', 'success');
      onSuccess(res.data.id);
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'فشل حفظ معاملة الجواز';
      addToast(msg, 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
      <div className="flex items-center gap-3 pb-4 mb-6 border-b border-slate-100">
        <div className="w-10 h-10 rounded-xl bg-purple-50 text-purple-700 flex items-center justify-center">
          <BookOpen className="w-5 h-5" />
        </div>
        <div>
          <h2 className="text-lg font-bold text-slate-900">إنشاء معاملة استخراج/تجديد جواز (PA)</h2>
          <p className="text-xs text-slate-500">معاملات مصلحة الهجرة والجوازات</p>
        </div>
      </div>

      <StepperForm steps={STEPS} currentStep={currentStep} />

      <form onSubmit={handleSubmit(onSubmit)}>
        {/* Step 1: Passport type */}
        {currentStep === 1 && (
          <div className="space-y-4 animate-in fade-in duration-200">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <Select
                label="نوع المعاملة"
                required
                error={errors.passport_type?.message}
                {...register('passport_type')}
              >
                <option value="new">إصدار جواز جديد لأول مرة</option>
                <option value="renewal">تجديد جواز منتهي</option>
                <option value="lost">بدل فاقد</option>
                <option value="damaged">بدل تالف</option>
              </Select>

              <Select
                label="مستوى الأولوية"
                required
                error={errors.priority?.message}
                {...register('priority')}
              >
                <option value="normal">عادي (روتين طبيعي)</option>
                <option value="urgent">مستعجل (أولوية قصوى)</option>
              </Select>

              <Input
                label="تاريخ التقديم"
                type="date"
                required
                error={errors.application_date?.message}
                {...register('application_date')}
              />

              <Input
                label="تاريخ الاستلام المتوقع"
                type="date"
                error={errors.expected_delivery_date?.message}
                {...register('expected_delivery_date')}
              />
            </div>
          </div>
        )}

        {/* Step 2: Applicant details */}
        {currentStep === 2 && (
          <div className="space-y-6 animate-in fade-in duration-200">
            <CustomerSearch
              selectedCustomer={selectedCustomer}
              onSelectCustomer={handleCustomerSelect}
            />

            <div className="pt-2 border-t border-slate-100">
              <div className="flex items-center justify-between mb-4">
                <h4 className="text-sm font-bold text-slate-800">بيانات صاحب الجواز والهوية</h4>
                <OcrScanButton type="id" onExtracted={handleOcrExtracted} />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                <Input
                  label="الاسم الكامل"
                  placeholder="الاسم الرباعي واللقب..."
                  required
                  error={errors.applicant_name?.message}
                  {...register('applicant_name')}
                />

                <Input
                  label="رقم الهاتف للتواصل"
                  placeholder="77xxxxxxx"
                  required
                  error={errors.applicant_phone?.message}
                  {...register('applicant_phone')}
                />

                <Input
                  label="رقم البطاقة الشخصية"
                  placeholder="0101xxxxxxxx"
                  required
                  error={errors.id_number?.message}
                  {...register('id_number')}
                />

                <Input
                  label="تاريخ الميلاد"
                  type="date"
                  required
                  error={errors.birth_date?.message}
                  {...register('birth_date')}
                />

                <Input
                  label="مكان الميلاد"
                  placeholder="المحافظة / المديرية..."
                  required
                  error={errors.birth_place?.message}
                  {...register('birth_place')}
                />
              </div>
            </div>
          </div>
        )}

        {/* Step 3: Financials */}
        {currentStep === 3 && (
          <div className="animate-in fade-in duration-200">
            <BookingFinancialStep form={form as any} selectedCustomer={selectedCustomer} />
          </div>
        )}

        {/* Action Controls */}
        <div className="flex items-center justify-between pt-6 mt-6 border-t border-slate-100">
          <div>
            {currentStep > 1 ? (
              <Button type="button" variant="outline" onClick={prevStep} icon={<ArrowRight className="w-4 h-4" />}>
                السابق
              </Button>
            ) : (
              <Button type="button" variant="ghost" onClick={onCancel}>
                إلغاء
              </Button>
            )}
          </div>

          <div>
            {currentStep < 3 ? (
              <Button type="button" variant="primary" onClick={nextStep} icon={<ArrowLeft className="w-4 h-4" />}>
                التالي
              </Button>
            ) : (
              <Button
                type="submit"
                variant="primary"
                isLoading={isSubmitting}
                icon={<CheckCircle2 className="w-4 h-4" />}
                className="bg-emerald-700 hover:bg-emerald-800"
              >
                تأكيد وحفظ المعاملة وطباعة السند
              </Button>
            )}
          </div>
        </div>
      </form>
    </div>
  );
}

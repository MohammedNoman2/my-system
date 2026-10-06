import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as yup from 'yup';
import { Stamp, ArrowLeft, ArrowRight, CheckCircle2 } from 'lucide-react';
import { useAuthStore } from '../../context/authStore';
import api from '../../services/api';
import type { Customer } from '../../types';
import { useUIStore } from '../../context/uiStore';
import { StepperForm } from './StepperForm';
import { CustomerSearch } from './CustomerSearch';
import { OcrScanButton } from './OcrScanButton';
import { BookingFinancialStep } from './BookingFinancialStep';
import { Input } from '../common/Input';
import { Button } from '../common/Button';

const visaSchema = yup.object({
  // Step 1: Visa details (NO country/duration/expected_issue_date per specification §1)
  visa_type: yup.string().required('نوع التأشيرة مطلوب (عمرة / عمل / زيارة / سياحة)'),
  application_date: yup.string().required('تاريخ التقديم مطلوب'),

  // Step 2: Applicant details
  applicant_name: yup.string().required('اسم مقدم الطلب مطلوب'),
  applicant_phone: yup.string().required('رقم الهاتف مطلوب'),
  passport_number: yup.string().required('رقم الجواز مطلوب'),
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

type VisaFormValues = yup.InferType<typeof visaSchema>;

interface VisaBookingFormProps {
  onSuccess: (bookingId: number) => void;
  onCancel: () => void;
}

const STEPS = [
  { id: 1, title: 'نوع ومعاملة التأشيرة', description: 'بيانات الطلب والنوع' },
  { id: 2, title: 'بيانات مقدم الطلب', description: 'معلومات الجواز والشخص' },
  { id: 3, title: 'المالية والتأكيد', description: 'الرسوم وتأكيد الحجز' },
];

export function VisaBookingForm({ onSuccess, onCancel }: VisaBookingFormProps) {
  const [currentStep, setCurrentStep] = useState(1);
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const addToast = useUIStore((state) => state.addToast);

  const { role } = useAuthStore();
  const isEmployee = role === 'employee';

  const form = useForm<VisaFormValues>({
    resolver: yupResolver(visaSchema) as any,
    defaultValues: {
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
      if (customer.passport_number) {
        setValue('passport_number', customer.passport_number, { shouldValidate: true });
      }
    }
  };

  const handleOcrExtracted = (data: any) => {
    if (data.passenger_name) setValue('applicant_name', data.passenger_name, { shouldValidate: true });
    if (data.passport_number) setValue('passport_number', data.passport_number, { shouldValidate: true });
    if (data.birth_date) setValue('birth_date', data.birth_date, { shouldValidate: true });
    if (data.birth_place) setValue('birth_place', data.birth_place, { shouldValidate: true });
  };

  const nextStep = async () => {
    let fieldsToValidate: (keyof VisaFormValues)[] = [];
    if (currentStep === 1) {
      fieldsToValidate = ['visa_type', 'application_date'];
    } else if (currentStep === 2) {
      fieldsToValidate = ['applicant_name', 'applicant_phone', 'passport_number', 'birth_date', 'birth_place'];
    }

    const isValid = await trigger(fieldsToValidate);
    if (isValid) setCurrentStep((prev) => prev + 1);
  };

  const prevStep = () => setCurrentStep((prev) => prev - 1);

  const onSubmit = async (values: VisaFormValues) => {
    setIsSubmitting(true);
    try {
      const payload = {
        type: 'visa',
        customer_id: selectedCustomer ? selectedCustomer.id : null,
        selling_price: values.selling_price,
        paid_amount: values.paid_amount || 0,
        currency: values.currency,
        supplier_id: values.supplier_id ? Number(values.supplier_id) : null,
        supplier_name: (values as any).supplier_name || null,
        ...(isEmployee ? {} : { cost_price: values.cost_price || 0 }),
        notes: values.notes || null,
        visa_details: {
          visa_type: values.visa_type,
          application_date: values.application_date,
          applicant_name: values.applicant_name,
          applicant_phone: values.applicant_phone,
          passport_number: values.passport_number,
          birth_date: values.birth_date,
          birth_place: values.birth_place,
        },
      };

      const res = await api.post('/bookings/', payload);
      addToast('تم إنشاء معاملة التأشيرة بنجاح', 'success');
      onSuccess(res.data.id);
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'فشل حفظ معاملة التأشيرة';
      addToast(msg, 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
      <div className="flex items-center gap-3 pb-4 mb-6 border-b border-slate-100">
        <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
          <Stamp className="w-5 h-5" />
        </div>
        <div>
          <h2 className="text-lg font-bold text-slate-900">إنشاء معاملة تأشيرة (VI)</h2>
          <p className="text-xs text-slate-500">معاملات التأشيرات (عمرة، زيارة، عمل، سياحة)</p>
        </div>
      </div>

      <StepperForm steps={STEPS} currentStep={currentStep} />

      <form onSubmit={handleSubmit(onSubmit)}>
        {/* Step 1: Visa details */}
        {currentStep === 1 && (
          <div className="space-y-4 animate-in fade-in duration-200">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label="نوع التأشيرة"
                placeholder="تأشيرة عمرة / عمل / زيارة عائلية / سياحة..."
                required
                error={errors.visa_type?.message}
                {...register('visa_type')}
              />

              <Input
                label="تاريخ التقديم"
                type="date"
                required
                error={errors.application_date?.message}
                {...register('application_date')}
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
                <h4 className="text-sm font-bold text-slate-800">بيانات مقدم طلب التأشيرة</h4>
                <OcrScanButton type="passport" onExtracted={handleOcrExtracted} />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                <Input
                  label="اسم مقدم الطلب"
                  placeholder="كما هو في الجواز..."
                  required
                  error={errors.applicant_name?.message}
                  {...register('applicant_name')}
                />

                <Input
                  label="رقم الهاتف"
                  placeholder="77xxxxxxx"
                  required
                  error={errors.applicant_phone?.message}
                  {...register('applicant_phone')}
                />

                <Input
                  label="رقم الجواز"
                  placeholder="08xxxxxx"
                  required
                  error={errors.passport_number?.message}
                  {...register('passport_number')}
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
                  placeholder="صنعاء / تعز / عدن..."
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
            <BookingFinancialStep form={form as any} />
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

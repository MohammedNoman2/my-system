import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as yup from 'yup';
import { FileCheck2, ArrowLeft, ArrowRight, CheckCircle2, Plus, Trash2, Users } from 'lucide-react';
import { useAuthStore } from '../../context/authStore';
import api from '../../services/api';
import type { Customer } from '../../types';
import { useUIStore } from '../../context/uiStore';
import { StepperForm } from './StepperForm';
import { CustomerSearch } from './CustomerSearch';
import { PassengerNameAutocomplete } from './PassengerNameAutocomplete';
import { OcrScanButton } from './OcrScanButton';
import { BookingFinancialStep } from './BookingFinancialStep';
import { Input } from '../common/Input';
import { Button } from '../common/Button';

interface VisaApplicantDraft {
  first_middle_name: string;
  last_name: string;
  applicant_phone: string;
  passport_number: string;
  birth_date: string;
  birth_place: string;
}

const emptyApplicant = (): VisaApplicantDraft => ({
  first_middle_name: '',
  last_name: '',
  applicant_phone: '',
  passport_number: '',
  birth_date: '',
  birth_place: '',
});

const visaSchema = yup.object({
  visa_type: yup.string().required('نوع التأشيرة مطلوب'),
  application_date: yup.string().required('تاريخ التقديم مطلوب'),
  selling_price: yup.number().positive('سعر البيع يجب أن يكون أكبر من الصفر').required('سعر البيع مطلوب'),
  paid_amount: yup.number().min(0).default(0),
  remaining_amount: yup.number().default(0),
  currency: yup.string().default('YER'),
  supplier_id: yup.string().nullable().optional(),
  supplier_name: yup.string().nullable().optional(),
  cost_price: yup.number().min(0).optional(),
  notes: yup.string().nullable().optional(),
  payment_method: yup.string().default('cash'),
  reference_number: yup.string().nullable().optional(),
  use_credit_balance: yup.boolean().default(true),
});

type VisaFormValues = yup.InferType<typeof visaSchema>;

interface VisaBookingFormProps {
  onSuccess: (bookingIds: number | number[]) => void;
  onCancel: () => void;
}

const STEPS = [
  { id: 1, title: 'بيانات التأشيرة', description: 'النوع وتاريخ التقديم' },
  { id: 2, title: 'بيانات المتقدمين', description: 'الاسم الثلاثي والجواز' },
  { id: 3, title: 'المالية والتأكيد', description: 'الأسعار والدفع' },
];

export function VisaBookingForm({ onSuccess, onCancel }: VisaBookingFormProps) {
  const [currentStep, setCurrentStep] = useState(1);
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [applicants, setApplicants] = useState<VisaApplicantDraft[]>([emptyApplicant()]);
  const [applicantError, setApplicantError] = useState<string | null>(null);
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

  const updateApplicant = (idx: number, patch: Partial<VisaApplicantDraft>) => {
    setApplicants((prev) => prev.map((a, i) => (i === idx ? { ...a, ...patch } : a)));
  };

  const handleCustomerSelect = (customer: Customer | null) => {
    setSelectedCustomer(customer);
    if (customer) {
      const parts = customer.name.trim().split(/\s+/);
      updateApplicant(0, {
        first_middle_name: parts.slice(0, 3).join(' '),
        last_name: parts.slice(3).join(' '),
        applicant_phone: customer.phone_number || '',
        passport_number: customer.passport_number || '',
      });
      setValue('applicant_name' as any, customer.name);
      setValue('applicant_phone' as any, customer.phone_number);
    }
  };

  const handleOcrExtracted = (data: any) => {
    updateApplicant(0, {
      ...(data.passport_number || data.id_number ? { passport_number: data.passport_number || data.id_number } : {}),
      ...(data.birth_date ? { birth_date: data.birth_date } : {}),
      ...(data.birth_place ? { birth_place: data.birth_place } : {}),
    });
  };

  const validateApplicants = (): boolean => {
    for (let i = 0; i < applicants.length; i++) {
      const a = applicants[i];
      const lbl = `المتقدم #${i + 1}`;
      if (a.first_middle_name.trim().split(/\s+/).filter(Boolean).length !== 3) {
        setApplicantError(`${lbl}: الاسم الثلاثي يجب أن يتكون من 3 أسماء بالضبط`);
        return false;
      }
      if (!a.last_name.trim()) {
        setApplicantError(`${lbl}: اللقب مطلوب`);
        return false;
      }
      if (a.applicant_phone.replace(/\D/g, '').length < 9) {
        setApplicantError(`${lbl}: رقم الهاتف يجب أن يكون 9 أرقام على الأقل`);
        return false;
      }
      if (!a.passport_number.trim() || !a.birth_date || !a.birth_place.trim()) {
        setApplicantError(`${lbl}: رقم الجواز وتاريخ ومكان الميلاد مطلوبان`);
        return false;
      }
    }
    setApplicantError(null);
    return true;
  };

  const nextStep = async () => {
    if (currentStep === 1) {
      if (await trigger(['visa_type', 'application_date'])) setCurrentStep(2);
    } else if (currentStep === 2) {
      if (validateApplicants()) setCurrentStep(3);
    }
  };

  const prevStep = () => setCurrentStep((prev) => prev - 1);

  const onSubmit = async (values: VisaFormValues) => {
    if (!validateApplicants()) {
      setCurrentStep(2);
      return;
    }

    const items = applicants.map((a) => ({
      visa_details: {
        visa_type: values.visa_type,
        application_date: values.application_date,
        first_middle_name: a.first_middle_name.trim(),
        last_name: a.last_name.trim(),
        applicant_name: `${a.first_middle_name.trim()} ${a.last_name.trim()}`,
        applicant_phone: a.applicant_phone.trim(),
        passport_number: a.passport_number.trim(),
        birth_date: a.birth_date,
        birth_place: a.birth_place.trim(),
      },
    }));

    const isDeferred = values.payment_method === 'deferred';
    const paidVal = isDeferred ? 0 : (values.paid_amount || 0);
    const pmVal = isDeferred ? 'cash' : (values.payment_method || 'cash');

    setIsSubmitting(true);
    try {
      if (items.length === 1) {
        const res = await api.post('/bookings/', {
          type: 'visa',
          customer_id: selectedCustomer ? selectedCustomer.id : null,
          selling_price: values.selling_price,
          paid_amount: paidVal,
          payment_method: pmVal,
          reference_number: values.reference_number || null,
          currency: values.currency,
          supplier_id: values.supplier_id ? Number(values.supplier_id) : null,
          supplier_name: values.supplier_name || null,
          ...(isEmployee ? {} : { cost_price: values.cost_price || 0 }),
          notes: values.notes || null,
          use_credit_balance: values.use_credit_balance ?? true,
          visa_details: items[0].visa_details,
        });
        addToast('تم تسجيل طلب التأشيرة بنجاح', 'success');
        onSuccess(res.data.id);
      } else {
        const res = await api.post('/bookings/batch', {
          type: 'visa',
          customer_id: selectedCustomer ? selectedCustomer.id : null,
          selling_price: values.selling_price,
          ...(isEmployee ? {} : { cost_price: values.cost_price || 0 }),
          paid_amount: paidVal,
          payment_method: pmVal,
          reference_number: values.reference_number || null,
          currency: values.currency,
          supplier_id: values.supplier_id ? Number(values.supplier_id) : null,
          supplier_name: values.supplier_name || null,
          notes: values.notes || null,
          use_credit_balance: values.use_credit_balance ?? true,
          items,
        });
        addToast(`تم إصدار ${res.data.count} معاملات تأشيرة بنجاح`, 'success');
        onSuccess(res.data.booking_ids || []);
      }
    } catch (err: any) {
      addToast(err.response?.data?.detail || 'فشل حفظ طلب التأشيرة', 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
      <div className="flex items-center gap-3 pb-4 mb-6 border-b border-slate-100">
        <div className="w-10 h-10 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center">
          <FileCheck2 className="w-5 h-5" />
        </div>
        <div>
          <h2 className="text-lg font-bold text-slate-900">إنشاء معاملة تأشيرة (VI)</h2>
          <p className="text-xs text-slate-500">يدعم تعدد المتقدمين والاسم الثلاثي واللقب</p>
        </div>
      </div>

      <StepperForm steps={STEPS} currentStep={currentStep} />

      <form onSubmit={handleSubmit(onSubmit)}>
        {currentStep === 1 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 animate-in fade-in duration-200">
            <Input label="نوع التأشيرة" placeholder="عمرة / زيارة عائلية / عمل..." required error={errors.visa_type?.message} {...register('visa_type')} />
            <Input label="تاريخ التقديم" type="date" required error={errors.application_date?.message} {...register('application_date')} />
          </div>
        )}

        {currentStep === 2 && (
          <div className="space-y-6 animate-in fade-in duration-200">
          <CustomerSearch
            selectedCustomer={selectedCustomer}
            onSelectCustomer={handleCustomerSelect}
            onManualNameInput={(name) => {
              const parts = name.trim().split(/\s+/).filter(Boolean);
              updateApplicant(0, {
                first_middle_name: parts.slice(0, 3).join(' '),
                last_name: parts.slice(3).join(' '),
              });
            }}
          />

            <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-slate-100">
              <h4 className="text-sm font-bold text-slate-800 flex items-center gap-2">
                <Users className="w-4 h-4 text-purple-600" />
                المتقدمون ({applicants.length})
              </h4>
              <div className="flex items-center gap-2">
                <OcrScanButton type="passport" onExtracted={handleOcrExtracted} />
                <Button type="button" variant="secondary" onClick={() => setApplicants((prev) => [...prev, emptyApplicant()])} icon={<Plus className="w-4 h-4" />}>
                  إضافة متقدم آخر
                </Button>
              </div>
            </div>

            {applicantError && (
              <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-xs font-bold text-red-700">{applicantError}</div>
            )}

            <div className="space-y-4">
              {applicants.map((a, idx) => (
                <div key={idx} className="border border-slate-200 rounded-xl p-4 bg-slate-50/60 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-purple-700">المتقدم #{idx + 1}</span>
                    {applicants.length > 1 && (
                      <button type="button" onClick={() => setApplicants((prev) => prev.filter((_, i) => i !== idx))} className="text-xs text-red-600 hover:underline flex items-center gap-1">
                        <Trash2 className="w-3.5 h-3.5" /> حذف
                      </button>
                    )}
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    <PassengerNameAutocomplete
                      label="الاسم الثلاثي فقط"
                      placeholder="مثال: محمد أحمد علي"
                      required
                      value={a.first_middle_name}
                      onChange={(val) => {
                        if (idx === 0) setSelectedCustomer(null);
                        updateApplicant(idx, { first_middle_name: val });
                      }}
                      onSelectCustomer={(c) => {
                        const parts = c.name.trim().split(/\s+/);
                        updateApplicant(idx, {
                          first_middle_name: parts.slice(0, 3).join(' '),
                          last_name: parts.slice(3).join(' '),
                          applicant_phone: c.phone_number || '',
                          passport_number: c.passport_number || '',
                        });
                        if (idx === 0) {
                          setSelectedCustomer(c);
                          setValue('applicant_name' as any, c.name);
                          setValue('applicant_phone' as any, c.phone_number);
                        }
                      }}
                    />
                    <PassengerNameAutocomplete
                      label="اللقب"
                      placeholder="مثال: الصالحي"
                      required
                      value={a.last_name}
                      onChange={(val) => {
                        if (idx === 0) setSelectedCustomer(null);
                        updateApplicant(idx, { last_name: val });
                      }}
                      onSelectCustomer={(c) => {
                        const parts = c.name.trim().split(/\s+/);
                        updateApplicant(idx, {
                          first_middle_name: parts.slice(0, 3).join(' '),
                          last_name: parts.slice(3).join(' '),
                          applicant_phone: c.phone_number || '',
                          passport_number: c.passport_number || '',
                        });
                        if (idx === 0) {
                          setSelectedCustomer(c);
                          setValue('applicant_name' as any, c.name);
                          setValue('applicant_phone' as any, c.phone_number);
                        }
                      }}
                    />
                    <Input label="رقم الهاتف" placeholder="77xxxxxxx" required value={a.applicant_phone} onChange={(e) => updateApplicant(idx, { applicant_phone: e.target.value })} />
                    <Input label="رقم الجواز" placeholder="P1234567" required value={a.passport_number} onChange={(e) => updateApplicant(idx, { passport_number: e.target.value })} />
                    <Input label="تاريخ الميلاد" type="date" required value={a.birth_date} onChange={(e) => updateApplicant(idx, { birth_date: e.target.value })} />
                    <Input label="مكان الميلاد" placeholder="صنعاء / عدن..." required value={a.birth_place} onChange={(e) => updateApplicant(idx, { birth_place: e.target.value })} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {currentStep === 3 && <BookingFinancialStep form={form} selectedCustomer={selectedCustomer} passengerCount={applicants.length} />}

        <div className="flex items-center justify-between pt-6 mt-6 border-t border-slate-100">
          {currentStep > 1 ? (
            <Button type="button" variant="secondary" onClick={prevStep} icon={<ArrowRight className="w-4 h-4" />}>السابق</Button>
          ) : (
            <Button type="button" variant="ghost" onClick={onCancel}>إلغاء</Button>
          )}
          {currentStep < 3 ? (
            <Button type="button" variant="primary" onClick={nextStep} icon={<ArrowLeft className="w-4 h-4" />}>التالي</Button>
          ) : (
            <Button type="submit" variant="primary" isLoading={isSubmitting} icon={<CheckCircle2 className="w-4 h-4" />} className="bg-purple-700 hover:bg-purple-800">
              {applicants.length > 1 ? `تأكيد وإصدار ${applicants.length} تأشيرات` : 'تأكيد وحفظ طلب التأشيرة'}
            </Button>
          )}
        </div>
      </form>
    </div>
  );
}

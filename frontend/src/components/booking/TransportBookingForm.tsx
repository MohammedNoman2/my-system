import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as yup from 'yup';
import { Bus, ArrowLeft, ArrowRight, CheckCircle2 } from 'lucide-react';
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

const transportSchema = yup.object({
  // Step 1: Trip details (NO seat_number per specification §1)
  transport_company: yup.string().required('شركة النقل مطلوبة'),
  departure_station: yup.string().required('محطة الانطلاق مطلوبة'),
  arrival_station: yup.string().required('محطة الوصول مطلوبة'),
  travel_date: yup.string().required('تاريخ السفر مطلوب'),
  travel_time: yup.string().required('وقت السفر مطلوب'),

  // Step 2: Passenger details
  passenger_name: yup.string().required('اسم الراكب مطلوب'),
  passenger_phone: yup.string().required('رقم الهاتف مطلوب'),
  id_number: yup.string().required('رقم البطاقة الشخصية / الهوية مطلوب'),
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

type TransportFormValues = yup.InferType<typeof transportSchema>;

interface TransportBookingFormProps {
  onSuccess: (bookingId: number) => void;
  onCancel: () => void;
}

const STEPS = [
  { id: 1, title: 'بيانات الرحلة البرية', description: 'الشركة والمسار والمواعيد' },
  { id: 2, title: 'بيانات الراكب', description: 'الهوية والمعلومات الشخصية' },
  { id: 3, title: 'المالية والتأكيد', description: 'الأسعار والدفع' },
];

export function TransportBookingForm({ onSuccess, onCancel }: TransportBookingFormProps) {
  const [currentStep, setCurrentStep] = useState(1);
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const addToast = useUIStore((state) => state.addToast);

  const { role } = useAuthStore();
  const isEmployee = role === 'employee';

  const form = useForm<TransportFormValues>({
    resolver: yupResolver(transportSchema) as any,
    defaultValues: {
      currency: 'YER',
      paid_amount: 0,
      cost_price: 0,
    },
    mode: 'onTouched',
  });

  const { register, setValue, trigger, handleSubmit, formState: { errors } } = form;

  const handleCustomerSelect = (customer: Customer | null) => {
    setSelectedCustomer(customer);
    if (customer) {
      setValue('passenger_name', customer.name, { shouldValidate: true });
      setValue('passenger_phone', customer.phone_number, { shouldValidate: true });
      if (customer.id_number) {
        setValue('id_number', customer.id_number, { shouldValidate: true });
      }
    }
  };

  const handleOcrExtracted = (data: any) => {
    if (data.passenger_name) setValue('passenger_name', data.passenger_name, { shouldValidate: true });
    if (data.id_number) setValue('id_number', data.id_number, { shouldValidate: true });
    if (data.birth_date) setValue('birth_date', data.birth_date, { shouldValidate: true });
    if (data.birth_place) setValue('birth_place', data.birth_place, { shouldValidate: true });
  };

  const nextStep = async () => {
    let fieldsToValidate: (keyof TransportFormValues)[] = [];
    if (currentStep === 1) {
      fieldsToValidate = ['transport_company', 'departure_station', 'arrival_station', 'travel_date', 'travel_time'];
    } else if (currentStep === 2) {
      fieldsToValidate = ['passenger_name', 'passenger_phone', 'id_number', 'birth_date', 'birth_place'];
    }

    const isValid = await trigger(fieldsToValidate);
    if (isValid) setCurrentStep((prev) => prev + 1);
  };

  const prevStep = () => setCurrentStep((prev) => prev - 1);

  const onSubmit = async (values: TransportFormValues) => {
    setIsSubmitting(true);
    try {
      const payload = {
        type: 'transport',
        customer_id: selectedCustomer ? selectedCustomer.id : null,
        selling_price: values.selling_price,
        paid_amount: values.paid_amount || 0,
        currency: values.currency,
        supplier_id: values.supplier_id ? Number(values.supplier_id) : null,
        supplier_name: (values as any).supplier_name || null,
        ...(isEmployee ? {} : { cost_price: values.cost_price || 0 }),
        notes: values.notes || null,
        use_credit_balance: (values as any).use_credit_balance ?? true,
        transport_details: {
          transport_company: values.transport_company,
          departure_station: values.departure_station,
          arrival_station: values.arrival_station,
          travel_date: values.travel_date,
          travel_time: values.travel_time,
          passenger_name: values.passenger_name,
          passenger_phone: values.passenger_phone,
          id_number: values.id_number,
          birth_date: values.birth_date,
          birth_place: values.birth_place,
        },
      };

      const res = await api.post('/bookings/', payload);
      addToast('تم إنشاء حجز النقل البري بنجاح', 'success');
      onSuccess(res.data.id);
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'فشل حفظ حجز النقل';
      addToast(msg, 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
      <div className="flex items-center gap-3 pb-4 mb-6 border-b border-slate-100">
        <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
          <Bus className="w-5 h-5" />
        </div>
        <div>
          <h2 className="text-lg font-bold text-slate-900">إنشاء حجز نقل بري (TR)</h2>
          <p className="text-xs text-slate-500">حجز مقاعد الحافلات والرحلات البرية الدولية والمحلية</p>
        </div>
      </div>

      <StepperForm steps={STEPS} currentStep={currentStep} />

      <form onSubmit={handleSubmit(onSubmit)}>
        {/* Step 1: Trip details */}
        {currentStep === 1 && (
          <div className="space-y-4 animate-in fade-in duration-200">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <Input
                label="شركة النقل البري"
                placeholder="شركة النور / بن معمر / الأولى للنقل..."
                required
                error={errors.transport_company?.message}
                {...register('transport_company')}
              />

              <Input
                label="محطة الانطلاق"
                placeholder="صنعاء - فرع الستين / عدن..."
                required
                error={errors.departure_station?.message}
                {...register('departure_station')}
              />

              <Input
                label="محطة الوصول"
                placeholder="الرياض / جدة / مكة / المهرة..."
                required
                error={errors.arrival_station?.message}
                {...register('arrival_station')}
              />

              <Input
                label="تاريخ السفر"
                type="date"
                required
                error={errors.travel_date?.message}
                {...register('travel_date')}
              />

              <Input
                label="وقت الانطلاق"
                type="time"
                required
                error={errors.travel_time?.message}
                {...register('travel_time')}
              />
            </div>
          </div>
        )}

        {/* Step 2: Passenger details */}
        {currentStep === 2 && (
          <div className="space-y-6 animate-in fade-in duration-200">
            <CustomerSearch
              selectedCustomer={selectedCustomer}
              onSelectCustomer={handleCustomerSelect}
            />

            <div className="pt-2 border-t border-slate-100">
              <div className="flex items-center justify-between mb-4">
                <h4 className="text-sm font-bold text-slate-800">بيانات الراكب والهوية</h4>
                <OcrScanButton type="id" onExtracted={handleOcrExtracted} />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Input
                  label="اسم الراكب الكامل"
                  placeholder="كما هو مدون في البطاقة الشخصية..."
                  required
                  error={errors.passenger_name?.message}
                  {...register('passenger_name')}
                />

                <Input
                  label="رقم الهاتف للتواصل"
                  placeholder="77xxxxxxx"
                  required
                  error={errors.passenger_phone?.message}
                  {...register('passenger_phone')}
                />

                <Input
                  label="رقم البطاقة الشخصية / الهوية الوطنية"
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
                  placeholder="مثال: صنعاء / عدن / تعز..."
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
                تأكيد وحفظ الحجز وطباعة السند
              </Button>
            )}
          </div>
        </div>
      </form>
    </div>
  );
}

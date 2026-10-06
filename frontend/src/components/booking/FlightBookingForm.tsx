import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as yup from 'yup';
import { Plane, ArrowLeft, ArrowRight, CheckCircle2 } from 'lucide-react';
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

const flightSchema = yup.object({
  // Step 1: Flight details
  airline_company: yup.string().required('شركة الطيران مطلوبة'),
  flight_number: yup.string().required('رقم الرحلة مطلوب'),
  departure_airport: yup.string().required('مطار المغادرة مطلوب'),
  arrival_airport: yup.string().required('مطار الوصول مطلوب'),
  departure_date: yup.string().required('تاريخ الإقلاع مطلوب'),
  departure_time: yup.string().required('وقت الإقلاع مطلوب'),
  ticket_type: yup.string().oneOf(['oneway', 'roundtrip']).default('oneway'),
  return_date: yup.string().nullable().optional(),
  return_time: yup.string().nullable().optional(),
  allowed_weight: yup.number().nullable().transform((v) => (isNaN(v) ? null : v)).optional(),

  // Step 2: Passenger details
  passenger_name: yup.string().required('اسم المسافر مطلوب'),
  passenger_phone: yup.string().required('رقم هاتف المسافر مطلوب'),
  passport_number: yup.string().required('رقم الجواز مطلوب'),
  birth_date: yup.string().required('تاريخ الميلاد مطلوب'),
  birth_place: yup.string().required('مكان الميلاد مطلوب'),

  // Step 3: Financials
  selling_price: yup.number().positive('سعر البيع يجب أن يكون أكبر من الصفر').required('سعر البيع مطلوب'),
  paid_amount: yup.number().min(0, 'المبلغ المدفوع لا يمكن أن يكون سالباً').default(0),
  remaining_amount: yup.number().default(0),
  currency: yup.string().default('YER'),
  supplier_id: yup.string().nullable().optional(),
  cost_price: yup.number().min(0).optional(),
  notes: yup.string().nullable().optional(),
});

type FlightFormValues = yup.InferType<typeof flightSchema>;

interface FlightBookingFormProps {
  onSuccess: (bookingId: number) => void;
  onCancel: () => void;
}

const STEPS = [
  { id: 1, title: 'بيانات الرحلة', description: 'مسار ومواعيد الطيران' },
  { id: 2, title: 'بيانات المسافر', description: 'الجواز والمعلومات الشخصية' },
  { id: 3, title: 'المالية والتأكيد', description: 'الأسعار وطريقة الدفع' },
];

export function FlightBookingForm({ onSuccess, onCancel }: FlightBookingFormProps) {
  const [currentStep, setCurrentStep] = useState(1);
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const addToast = useUIStore((state) => state.addToast);

  const { role } = useAuthStore();
  const isEmployee = role === 'employee';

  const form = useForm<FlightFormValues>({
    resolver: yupResolver(flightSchema) as any,
    defaultValues: {
      ticket_type: 'oneway',
      currency: 'YER',
      paid_amount: 0,
      cost_price: 0,
    },
    mode: 'onTouched',
  });

  const { register, watch, setValue, trigger, handleSubmit, formState: { errors } } = form;
  const ticketType = watch('ticket_type');

  const handleCustomerSelect = (customer: Customer | null) => {
    setSelectedCustomer(customer);
    if (customer) {
      setValue('passenger_name', customer.name, { shouldValidate: true });
      setValue('passenger_phone', customer.phone_number, { shouldValidate: true });
      if (customer.passport_number) {
        setValue('passport_number', customer.passport_number, { shouldValidate: true });
      }
    }
  };

  const handleOcrExtracted = (data: any) => {
    if (data.passenger_name) setValue('passenger_name', data.passenger_name, { shouldValidate: true });
    if (data.passport_number) setValue('passport_number', data.passport_number, { shouldValidate: true });
    if (data.birth_date) setValue('birth_date', data.birth_date, { shouldValidate: true });
    if (data.birth_place) setValue('birth_place', data.birth_place, { shouldValidate: true });
  };

  const nextStep = async () => {
    let fieldsToValidate: (keyof FlightFormValues)[] = [];
    if (currentStep === 1) {
      fieldsToValidate = ['airline_company', 'flight_number', 'departure_airport', 'arrival_airport', 'departure_date', 'departure_time'];
      if (ticketType === 'roundtrip') fieldsToValidate.push('return_date', 'return_time');
    } else if (currentStep === 2) {
      fieldsToValidate = ['passenger_name', 'passenger_phone', 'passport_number', 'birth_date', 'birth_place'];
    }

    const isValid = await trigger(fieldsToValidate);
    if (isValid) setCurrentStep((prev) => prev + 1);
  };

  const prevStep = () => setCurrentStep((prev) => prev - 1);

  const onSubmit = async (values: FlightFormValues) => {
    setIsSubmitting(true);
    try {
      const payload = {
        type: 'flight',
        customer_id: selectedCustomer ? selectedCustomer.id : null,
        selling_price: values.selling_price,
        paid_amount: values.paid_amount || 0,
        currency: values.currency,
        supplier_id: values.supplier_id ? Number(values.supplier_id) : null,
        supplier_name: (values as any).supplier_name || null,
        ...(isEmployee ? {} : { cost_price: values.cost_price || 0 }),
        notes: values.notes || null,
        flight_details: {
          airline_company: values.airline_company,
          flight_number: values.flight_number,
          departure_airport: values.departure_airport,
          arrival_airport: values.arrival_airport,
          departure_date: values.departure_date,
          departure_time: values.departure_time,
          return_date: values.return_date || null,
          return_time: values.return_time || null,
          ticket_type: values.ticket_type,
          allowed_weight: values.allowed_weight || null,
          passenger_name: values.passenger_name,
          passenger_phone: values.passenger_phone,
          passport_number: values.passport_number,
          birth_date: values.birth_date,
          birth_place: values.birth_place,
        },
      };

      const res = await api.post('/bookings/', payload);
      addToast('تم إنشاء حجز الطيران بنجاح', 'success');
      onSuccess(res.data.id);
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'فشل حفظ حجز الطيران';
      addToast(msg, 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
      <div className="flex items-center gap-3 pb-4 mb-6 border-b border-slate-100">
        <div className="w-10 h-10 rounded-xl bg-blue-50 text-[#1e3a8a] flex items-center justify-center">
          <Plane className="w-5 h-5" />
        </div>
        <div>
          <h2 className="text-lg font-bold text-slate-900">إنشاء حجز تذكرة طيران (FL)</h2>
          <p className="text-xs text-slate-500">حجز رحلات الطيران وتأكيد بيانات المسافر والتذاكر</p>
        </div>
      </div>

      <StepperForm steps={STEPS} currentStep={currentStep} />

      <form onSubmit={handleSubmit(onSubmit)}>
        {/* Step 1: Flight details */}
        {currentStep === 1 && (
          <div className="space-y-4 animate-in fade-in duration-200">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <Input
                label="شركة الطيران"
                placeholder="الخطوط الجوية اليمنية / طيران الملكة بلقيس..."
                required
                error={errors.airline_company?.message}
                {...register('airline_company')}
              />

              <Input
                label="رقم الرحلة"
                placeholder="IY-854"
                required
                error={errors.flight_number?.message}
                {...register('flight_number')}
              />

              <Select
                label="نوع التذكرة"
                required
                error={errors.ticket_type?.message}
                {...register('ticket_type')}
              >
                <option value="oneway">ذهاب فقط</option>
                <option value="roundtrip">ذهاب وعودة</option>
              </Select>

              <Input
                label="مطار المغادرة"
                placeholder="مطار عدن الدولي (ADE) / صنعاء (SAH)"
                required
                error={errors.departure_airport?.message}
                {...register('departure_airport')}
              />

              <Input
                label="مطار الوصول"
                placeholder="مطار القاهرة الدولي (CAI) / جدة (JED)"
                required
                error={errors.arrival_airport?.message}
                {...register('arrival_airport')}
              />

              <Input
                label="الوزن المسموح (كجم)"
                type="number"
                placeholder="30"
                error={errors.allowed_weight?.message}
                {...register('allowed_weight')}
              />

              <Input
                label="تاريخ الإقلاع (ذهاب)"
                type="date"
                required
                error={errors.departure_date?.message}
                {...register('departure_date')}
              />

              <Input
                label="وقت الإقلاع"
                type="time"
                required
                error={errors.departure_time?.message}
                {...register('departure_time')}
              />

              {ticketType === 'roundtrip' && (
                <>
                  <Input
                    label="تاريخ العودة"
                    type="date"
                    required
                    error={errors.return_date?.message}
                    {...register('return_date')}
                  />
                  <Input
                    label="وقت العودة"
                    type="time"
                    required
                    error={errors.return_time?.message}
                    {...register('return_time')}
                  />
                </>
              )}
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
                <h4 className="text-sm font-bold text-slate-800">بيانات المسافر والجواز</h4>
                <OcrScanButton type="passport" onExtracted={handleOcrExtracted} />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                <Input
                  label="اسم المسافر الكامل"
                  placeholder="كما هو مدون في الجواز..."
                  required
                  error={errors.passenger_name?.message}
                  {...register('passenger_name')}
                />

                <Input
                  label="رقم هاتف المسافر / للتواصل"
                  placeholder="77xxxxxxx"
                  required
                  error={errors.passenger_phone?.message}
                  {...register('passenger_phone')}
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
                  placeholder="صنعاء / عدن..."
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
                تأكيد وحفظ الحجز وطباعة السند
              </Button>
            )}
          </div>
        </div>
      </form>
    </div>
  );
}

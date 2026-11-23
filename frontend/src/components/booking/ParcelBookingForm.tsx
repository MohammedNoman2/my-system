import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as yup from 'yup';
import { Package, ArrowLeft, ArrowRight, CheckCircle2 } from 'lucide-react';
import { useAuthStore } from '../../context/authStore';
import api from '../../services/api';
import type { Customer } from '../../types';
import { useUIStore } from '../../context/uiStore';
import { StepperForm } from './StepperForm';
import { CustomerSearch } from './CustomerSearch';
import { BookingFinancialStep } from './BookingFinancialStep';
import { Input } from '../common/Input';
import { Button } from '../common/Button';

const parcelSchema = yup.object({
  // Step 1: Parcel details (NO quantity per specification §1)
  delivery_destination: yup.string().required('وجهة تسليم الطرد مطلوبة'),
  parcel_type: yup.string().required('نوع الطرد مطلوب (كرتون / مغلف مستندات / كيس...)'),
  weight: yup.number().positive('الوزن يجب أن يكون أكبر من الصفر').required('الوزن بالكجم مطلوب'),
  shipping_date: yup.string().required('تاريخ الشحن مطلوب'),
  content_description: yup.string().nullable().optional(),

  // Step 2: Sender & Receiver details (No OCR for parcels §2.3)
  sender_name: yup.string().required('اسم المرسل مطلوب'),
  sender_phone: yup.string().required('رقم هاتف المرسل مطلوب'),
  receiver_name: yup.string().required('اسم المستلم مطلوب'),
  receiver_phone: yup.string().required('رقم هاتف المستلم مطلوب'),

  // Step 3: Financials
  selling_price: yup.number().positive('سعر الشحن يجب أن يكون أكبر من الصفر').required('سعر الشحن مطلوب'),
  paid_amount: yup.number().min(0).default(0),
  remaining_amount: yup.number().default(0),
  currency: yup.string().default('YER'),
  supplier_id: yup.string().nullable().optional(),
  cost_price: yup.number().min(0).optional(),
  notes: yup.string().nullable().optional(),
});

type ParcelFormValues = yup.InferType<typeof parcelSchema>;

interface ParcelBookingFormProps {
  onSuccess: (bookingId: number) => void;
  onCancel: () => void;
}

const STEPS = [
  { id: 1, title: 'بيانات الطرد والشحنة', description: 'الوجهة والنوع والوزن' },
  { id: 2, title: 'المرسل والمستلم', description: 'عناوين وأرقام الاتصال' },
  { id: 3, title: 'المالية والتأكيد', description: 'أجور الشحن وتأكيد البوليصة' },
];

export function ParcelBookingForm({ onSuccess, onCancel }: ParcelBookingFormProps) {
  const [currentStep, setCurrentStep] = useState(1);
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const addToast = useUIStore((state) => state.addToast);

  const { role } = useAuthStore();
  const isEmployee = role === 'employee';

  const form = useForm<ParcelFormValues>({
    resolver: yupResolver(parcelSchema) as any,
    defaultValues: {
      currency: 'YER',
      paid_amount: 0,
      cost_price: 0,
      shipping_date: new Date().toISOString().split('T')[0],
    },
    mode: 'onTouched',
  });

  const { register, setValue, trigger, handleSubmit, formState: { errors } } = form;

  const handleCustomerSelect = (customer: Customer | null) => {
    setSelectedCustomer(customer);
    if (customer) {
      setValue('sender_name', customer.name, { shouldValidate: true });
      setValue('sender_phone', customer.phone_number, { shouldValidate: true });
    }
  };

  const nextStep = async () => {
    let fieldsToValidate: (keyof ParcelFormValues)[] = [];
    if (currentStep === 1) {
      fieldsToValidate = ['delivery_destination', 'parcel_type', 'weight', 'shipping_date'];
    } else if (currentStep === 2) {
      fieldsToValidate = ['sender_name', 'sender_phone', 'receiver_name', 'receiver_phone'];
    }

    const isValid = await trigger(fieldsToValidate);
    if (isValid) setCurrentStep((prev) => prev + 1);
  };

  const prevStep = () => setCurrentStep((prev) => prev - 1);

  const onSubmit = async (values: ParcelFormValues) => {
    setIsSubmitting(true);
    try {
      const payload = {
        type: 'parcel',
        customer_id: selectedCustomer ? selectedCustomer.id : null,
        selling_price: values.selling_price,
        paid_amount: (values as any).payment_method === 'deferred' ? 0 : (values.paid_amount || 0),
        payment_method: (values as any).payment_method === 'deferred' ? 'cash' : ((values as any).payment_method || 'cash'),
        reference_number: (values as any).reference_number || null,
        currency: values.currency,
        supplier_id: values.supplier_id ? Number(values.supplier_id) : null,
        supplier_name: (values as any).supplier_name || null,
        ...(isEmployee ? {} : { cost_price: values.cost_price || 0 }),
        notes: values.notes || null,
        use_credit_balance: (values as any).use_credit_balance ?? true,
        parcel_details: {
          sender_name: values.sender_name,
          sender_phone: values.sender_phone,
          receiver_name: values.receiver_name,
          receiver_phone: values.receiver_phone,
          delivery_destination: values.delivery_destination,
          parcel_type: values.parcel_type,
          weight: values.weight,
          content_description: values.content_description || null,
          shipping_date: values.shipping_date,
        },
      };

      const res = await api.post('/bookings/', payload);
      addToast('تم إنشاء بوليصة شحن الطرد بنجاح', 'success');
      onSuccess(res.data.id);
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'فشل حفظ بوليصة الطرد';
      addToast(msg, 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
      <div className="flex items-center gap-3 pb-4 mb-6 border-b border-slate-100">
        <div className="w-10 h-10 rounded-xl bg-orange-50 text-orange-600 flex items-center justify-center">
          <Package className="w-5 h-5" />
        </div>
        <div>
          <h2 className="text-lg font-bold text-slate-900">إنشاء بوليصة شحن طرد (PR)</h2>
          <p className="text-xs text-slate-500">إرسال واستلام الطرود والشحنات الداخلية والدولية</p>
        </div>
      </div>

      <StepperForm steps={STEPS} currentStep={currentStep} />

      <form onSubmit={handleSubmit(onSubmit)}>
        {/* Step 1: Parcel details */}
        {currentStep === 1 && (
          <div className="space-y-4 animate-in fade-in duration-200">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <Input
                label="وجهة تسليم الطرد"
                placeholder="عدن / المكلا / مأرب / الرياض..."
                required
                error={errors.delivery_destination?.message}
                {...register('delivery_destination')}
              />

              <Input
                label="نوع الطرد"
                placeholder="كرتون بضائع / ظرف وثائق / حقيبة ملابس..."
                required
                error={errors.parcel_type?.message}
                {...register('parcel_type')}
              />

              <Input
                label="الوزن الإجمالي (كجم)"
                type="number"
                step="0.1"
                placeholder="5.5"
                required
                error={errors.weight?.message}
                {...register('weight')}
              />

              <Input
                label="تاريخ الشحن"
                type="date"
                required
                error={errors.shipping_date?.message}
                {...register('shipping_date')}
              />

              <div className="sm:col-span-2">
                <Input
                  label="وصف المحتويات (اختياري)"
                  placeholder="مستندات رسمية، ملابس شخصية، عينات تجارية..."
                  error={errors.content_description?.message}
                  {...register('content_description')}
                />
              </div>
            </div>
          </div>
        )}

        {/* Step 2: Sender & Receiver details (No OCR for parcels) */}
        {currentStep === 2 && (
          <div className="space-y-6 animate-in fade-in duration-200">
          <CustomerSearch
            selectedCustomer={selectedCustomer}
            onSelectCustomer={handleCustomerSelect}
            onManualNameInput={(name) => {
              setValue('sender_name', name, { shouldValidate: true });
            }}
          />

            <div className="pt-2 border-t border-slate-100">
              <h4 className="text-sm font-bold text-slate-800 mb-4">بيانات أطراف الشحنة</h4>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                {/* Sender Column */}
                <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
                  <span className="text-xs font-bold text-[#1e3a8a] bg-blue-100/70 px-2 py-0.5 rounded-md">
                    بيانات المرسل
                  </span>
                  <Input
                    label="اسم المرسل الكامل"
                    placeholder="اسم المرسل..."
                    required
                    error={errors.sender_name?.message}
                    {...register('sender_name')}
                  />
                  <Input
                    label="رقم هاتف المرسل"
                    placeholder="77xxxxxxx"
                    required
                    error={errors.sender_phone?.message}
                    {...register('sender_phone')}
                  />
                </div>

                {/* Receiver Column */}
                <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
                  <span className="text-xs font-bold text-orange-800 bg-orange-100/70 px-2 py-0.5 rounded-md">
                    بيانات المستلم
                  </span>
                  <Input
                    label="اسم المستلم الكامل"
                    placeholder="اسم المستلم في الوجهة..."
                    required
                    error={errors.receiver_name?.message}
                    {...register('receiver_name')}
                  />
                  <Input
                    label="رقم هاتف المستلم"
                    placeholder="77xxxxxxx"
                    required
                    error={errors.receiver_phone?.message}
                    {...register('receiver_phone')}
                  />
                </div>
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
                تأكيد وحفظ البوليصة وطباعة السند
              </Button>
            )}
          </div>
        </div>
      </form>
    </div>
  );
}

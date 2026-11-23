import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as yup from 'yup';
import { Bus, ArrowLeft, ArrowRight, CheckCircle2, Plus, Trash2, Baby, Users } from 'lucide-react';
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

type IdType = 'national_id' | 'passport' | 'birth_certificate';

interface InfantDraft {
  full_name: string;
  id_type: IdType;
  id_number: string;
  birth_date: string;
}

interface PassengerDraft {
  first_middle_name: string;
  last_name: string;
  passenger_phone: string;
  id_type: IdType;
  id_number: string;
  birth_date: string;
  birth_place: string;
  infants: InfantDraft[];
}

const emptyPassenger = (): PassengerDraft => ({
  first_middle_name: '',
  last_name: '',
  passenger_phone: '',
  id_type: 'national_id',
  id_number: '',
  birth_date: '',
  birth_place: '',
  infants: [],
});

const transportTripSchema = yup.object({
  transport_company: yup.string().required('شركة النقل مطلوبة'),
  departure_station: yup.string().required('محطة الانطلاق مطلوبة'),
  arrival_station: yup.string().required('محطة الوصول مطلوبة'),
  travel_datetime: yup.string().required('تاريخ ووقت السفر مطلوبان'),
  selling_price: yup.number().positive('سعر المقعد يجب أن يكون أكبر من الصفر').required('سعر البيع مطلوب'),
  paid_amount: yup.number().min(0).default(0),
  remaining_amount: yup.number().default(0),
  currency: yup.string().default('YER'),
  supplier_id: yup.string().nullable().optional(),
  cost_price: yup.number().min(0).optional(),
  notes: yup.string().nullable().optional(),
  payment_method: yup.string().default('cash'),
  reference_number: yup.string().nullable().optional(),
  use_credit_balance: yup.boolean().default(true),
});

type TransportFormValues = yup.InferType<typeof transportTripSchema>;

interface TransportBookingFormProps {
  onSuccess: (bookingId: number) => void;
  onCancel: () => void;
}

const STEPS = [
  { id: 1, title: 'بيانات الرحلة البرية', description: 'الشركة والمسار والموعد الموحد' },
  { id: 2, title: 'بيانات المسافرين والرضّع', description: 'المقاعد والهويات والمرافقون' },
  { id: 3, title: 'المالية والتأكيد', description: 'الأسعار والدفع' },
];

export function TransportBookingForm({ onSuccess, onCancel }: TransportBookingFormProps) {
  const [currentStep, setCurrentStep] = useState(1);
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [passengers, setPassengers] = useState<PassengerDraft[]>([emptyPassenger()]);
  const [passengerError, setPassengerError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const addToast = useUIStore((state) => state.addToast);

  const { role } = useAuthStore();
  const isEmployee = role === 'employee';

  const form = useForm<TransportFormValues>({
    resolver: yupResolver(transportTripSchema) as any,
    defaultValues: {
      currency: 'YER',
      paid_amount: 0,
      cost_price: 0,
    },
    mode: 'onTouched',
  });

  const { register, setValue, trigger, handleSubmit, watch, formState: { errors } } = form;
  const sellingPerSeat = Number(watch('selling_price') || 0);

  const updatePassenger = (idx: number, patch: Partial<PassengerDraft>) => {
    setPassengers((prev) => prev.map((p, i) => (i === idx ? { ...p, ...patch } : p)));
  };

  const handleCustomerSelect = (customer: Customer | null) => {
    setSelectedCustomer(customer);
    if (customer) {
      const parts = customer.name.trim().split(/\s+/);
      const fm = parts.slice(0, 3).join(' ');
      const ln = parts.slice(3).join(' ');
      updatePassenger(0, {
        first_middle_name: fm,
        last_name: ln,
        passenger_phone: customer.phone_number || '',
        id_number: customer.id_number || '',
      });
      setValue('passenger_name' as any, customer.name);
      setValue('passenger_phone' as any, customer.phone_number);
    }
  };

  const handleOcrExtracted = (data: any) => {
    updatePassenger(0, {
      ...(data.id_number || data.passport_number ? { id_number: data.id_number || data.passport_number } : {}),
      ...(data.birth_date ? { birth_date: data.birth_date } : {}),
      ...(data.birth_place ? { birth_place: data.birth_place } : {}),
    });
  };

  const validatePassengers = (): boolean => {
    for (let i = 0; i < passengers.length; i++) {
      const p = passengers[i];
      const idxLabel = `المسافر #${i + 1}`;
      const fmWords = p.first_middle_name.trim().split(/\s+/).filter(Boolean);
      if (fmWords.length !== 3) {
        setPassengerError(`${idxLabel}: الاسم الثلاثي يجب أن يتكون من 3 أسماء بالضبط`);
        return false;
      }
      if (!p.last_name.trim()) {
        setPassengerError(`${idxLabel}: اللقب مطلوب`);
        return false;
      }
      const phoneDigits = p.passenger_phone.replace(/\D/g, '');
      if (phoneDigits.length < 9) {
        setPassengerError(`${idxLabel}: رقم الهاتف يجب أن يكون 9 أرقام على الأقل`);
        return false;
      }
      const doc = p.id_number.trim();
      if (p.id_type === 'passport' && !/^[A-Za-z0-9]{8}$/.test(doc)) {
        setPassengerError(`${idxLabel}: رقم الجواز يجب أن يتكون من 8 خانات بالضبط`);
        return false;
      }
      if (p.id_type === 'national_id' && !/^\d{11}$/.test(doc)) {
        setPassengerError(`${idxLabel}: رقم البطاقة الشخصية يجب أن يتكون من 11 رقماً بالضبط`);
        return false;
      }
      if (!p.birth_date || !p.birth_place.trim()) {
        setPassengerError(`${idxLabel}: تاريخ ومكان الميلاد مطلوبان`);
        return false;
      }
      for (let j = 0; j < p.infants.length; j++) {
        const inf = p.infants[j];
        if (!inf.full_name.trim() || !inf.birth_date) {
          setPassengerError(`${idxLabel} — الرضيع #${j + 1}: الاسم الكامل وتاريخ الميلاد مطلوبان`);
          return false;
        }
        const infDoc = inf.id_number.trim();
        if (inf.id_type === 'passport' && !/^[A-Za-z0-9]{8}$/.test(infDoc)) {
          setPassengerError(`${idxLabel} — الرضيع #${j + 1}: رقم الجواز يجب أن يكون 8 خانات`);
          return false;
        }
        if (inf.id_type === 'national_id' && !/^\d{11}$/.test(infDoc)) {
          setPassengerError(`${idxLabel} — الرضيع #${j + 1}: البطاقة الشخصية يجب أن تكون 11 رقماً`);
          return false;
        }
      }
    }
    setPassengerError(null);
    return true;
  };

  const nextStep = async () => {
    if (currentStep === 1) {
      const ok = await trigger(['transport_company', 'departure_station', 'arrival_station', 'travel_datetime']);
      if (ok) setCurrentStep(2);
    } else if (currentStep === 2) {
      if (validatePassengers()) setCurrentStep(3);
    }
  };

  const prevStep = () => setCurrentStep((prev) => prev - 1);

  const onSubmit = async (values: TransportFormValues) => {
    if (!validatePassengers()) {
      setCurrentStep(2);
      return;
    }

    const [tDate, tTimeRaw] = String(values.travel_datetime).split('T');
    const tTime = (tTimeRaw || '08:00').slice(0, 5);

    const passengerPayloads = passengers.map((p) => ({
      transport_company: values.transport_company,
      departure_station: values.departure_station,
      arrival_station: values.arrival_station,
      travel_date: tDate,
      travel_time: tTime,
      first_middle_name: p.first_middle_name.trim(),
      last_name: p.last_name.trim(),
      passenger_name: `${p.first_middle_name.trim()} ${p.last_name.trim()}`,
      passenger_phone: p.passenger_phone.trim(),
      id_type: p.id_type,
      id_number: p.id_number.trim(),
      birth_date: p.birth_date,
      birth_place: p.birth_place.trim(),
      infants: p.infants.map((inf) => ({
        full_name: inf.full_name.trim(),
        id_type: inf.id_type,
        id_number: inf.id_number.trim(),
        birth_date: inf.birth_date,
      })),
    }));

    const isDeferred = (values as any).payment_method === 'deferred';
    const paidVal = isDeferred ? 0 : (values.paid_amount || 0);
    const pmVal = isDeferred ? 'cash' : ((values as any).payment_method || 'cash');

    setIsSubmitting(true);
    try {
      if (passengerPayloads.length === 1) {
        const res = await api.post('/bookings/', {
          type: 'transport',
          customer_id: selectedCustomer ? selectedCustomer.id : null,
          selling_price: values.selling_price,
          paid_amount: paidVal,
          payment_method: pmVal,
          reference_number: (values as any).reference_number || null,
          currency: values.currency,
          supplier_id: values.supplier_id ? Number(values.supplier_id) : null,
          supplier_name: (values as any).supplier_name || null,
          ...(isEmployee ? {} : { cost_price: values.cost_price || 0 }),
          notes: values.notes || null,
          use_credit_balance: (values as any).use_credit_balance ?? true,
          transport_details: passengerPayloads[0],
        });
        addToast('تم إنشاء حجز النقل البري بنجاح', 'success');
        onSuccess(res.data.id);
      } else {
        const res = await api.post('/bookings/transport-batch', {
          customer_id: selectedCustomer ? selectedCustomer.id : null,
          selling_price: values.selling_price,
          paid_amount: paidVal,
          payment_method: pmVal,
          reference_number: (values as any).reference_number || null,
          currency: values.currency,
          supplier_id: values.supplier_id ? Number(values.supplier_id) : null,
          supplier_name: (values as any).supplier_name || null,
          ...(isEmployee ? {} : { cost_price: values.cost_price || 0 }),
          notes: values.notes || null,
          use_credit_balance: (values as any).use_credit_balance ?? true,
          passengers: passengerPayloads,
        });
        const tickets = (res.data?.ticket_numbers || []).join('، ');
        addToast(`تم إصدار ${res.data?.count || passengerPayloads.length} تذاكر نقل بري: ${tickets}`, 'success');
        onSuccess(res.data.booking_ids[0]);
      }
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
          <p className="text-xs text-slate-500">يدعم المقاعد المتعددة، وتحديد نوع الهوية، وإضافة الرضع</p>
        </div>
      </div>

      <StepperForm steps={STEPS} currentStep={currentStep} />

      <form onSubmit={handleSubmit(onSubmit)}>
        {/* Step 1: Trip details */}
        {currentStep === 1 && (
          <div className="space-y-4 animate-in fade-in duration-200">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label="شركة النقل البري"
                placeholder="شركة النور / بن معمر / الأولى للنقل..."
                required
                error={errors.transport_company?.message}
                {...register('transport_company')}
              />

              <Input
                label="تاريخ ووقت السفر"
                type="datetime-local"
                required
                error={errors.travel_datetime?.message}
                {...register('travel_datetime')}
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
            </div>
          </div>
        )}

        {/* Step 2: Multiple Passengers & Infants */}
        {currentStep === 2 && (
          <div className="space-y-6 animate-in fade-in duration-200">
          <CustomerSearch
            selectedCustomer={selectedCustomer}
            onSelectCustomer={handleCustomerSelect}
            onManualNameInput={(name) => {
              const parts = name.trim().split(/\s+/).filter(Boolean);
              updatePassenger(0, {
                first_middle_name: parts.slice(0, 3).join(' '),
                last_name: parts.slice(3).join(' '),
              });
            }}
          />

            <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-slate-100">
              <h4 className="text-sm font-bold text-slate-800 flex items-center gap-2">
                <Users className="w-4 h-4 text-amber-600" />
                المسافرون ({passengers.length} {passengers.length === 1 ? 'مقعد' : 'مقاعد'})
              </h4>
              <div className="flex items-center gap-2">
                <OcrScanButton type="id" onExtracted={handleOcrExtracted} />
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setPassengers((prev) => [...prev, emptyPassenger()])}
                  icon={<Plus className="w-4 h-4" />}
                >
                  إضافة مقعد / مسافر آخر
                </Button>
              </div>
            </div>

            {passengerError && (
              <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-xs font-bold text-red-700">
                {passengerError}
              </div>
            )}

            <div className="space-y-4">
              {passengers.map((p, idx) => (
                <div key={idx} className="border border-slate-200 rounded-xl p-4 bg-slate-50/60 space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-[#1e3a8a]">المسافر #{idx + 1}</span>
                    {passengers.length > 1 && (
                      <button
                        type="button"
                        onClick={() => setPassengers((prev) => prev.filter((_, i) => i !== idx))}
                        className="text-xs text-red-600 hover:underline flex items-center gap-1"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                        حذف المسافر
                      </button>
                    )}
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    <Input
                      label="الاسم الثلاثي فقط"
                      placeholder="مثال: محمد أحمد علي"
                      required
                      value={p.first_middle_name}
                      onChange={(e) => updatePassenger(idx, { first_middle_name: e.target.value })}
                    />

                    <Input
                      label="اللقب"
                      placeholder="مثال: الصالحي"
                      required
                      value={p.last_name}
                      onChange={(e) => updatePassenger(idx, { last_name: e.target.value })}
                    />

                    <Input
                      label="رقم الهاتف للتواصل"
                      placeholder="77xxxxxxx"
                      required
                      value={p.passenger_phone}
                      onChange={(e) => updatePassenger(idx, { passenger_phone: e.target.value })}
                    />

                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1">
                        نوع الهوية <span className="text-red-500">*</span>
                      </label>
                      <select
                        value={p.id_type}
                        onChange={(e) => updatePassenger(idx, { id_type: e.target.value as IdType, id_number: '' })}
                        className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#1e3a8a]"
                      >
                        <option value="national_id">بطاقة شخصية (11 رقماً)</option>
                        <option value="passport">جواز سفر (8 خانات)</option>
                        <option value="birth_certificate">شهادة ميلاد (اختياري)</option>
                      </select>
                    </div>

                    <Input
                      label={
                        p.id_type === 'passport'
                          ? 'رقم الجواز (8 خانات)'
                          : p.id_type === 'national_id'
                          ? 'رقم البطاقة الشخصية (11 رقماً)'
                          : 'رقم شهادة الميلاد (اختياري)'
                      }
                      placeholder={
                        p.id_type === 'passport'
                          ? '8 خانات...'
                          : p.id_type === 'national_id'
                          ? '11 رقماً...'
                          : 'يمكن تركه فارغاً...'
                      }
                      required={p.id_type !== 'birth_certificate'}
                      maxLength={p.id_type === 'passport' ? 8 : p.id_type === 'national_id' ? 11 : 50}
                      value={p.id_number}
                      onChange={(e) => updatePassenger(idx, { id_number: e.target.value })}
                    />

                    <Input
                      label="تاريخ الميلاد"
                      type="date"
                      required
                      value={p.birth_date}
                      onChange={(e) => updatePassenger(idx, { birth_date: e.target.value })}
                    />

                    <Input
                      label="مكان الميلاد"
                      placeholder="صنعاء / تعز / عدن..."
                      required
                      value={p.birth_place}
                      onChange={(e) => updatePassenger(idx, { birth_place: e.target.value })}
                    />
                  </div>

                  {/* Infants sub-section */}
                  <div className="pt-2 border-t border-slate-200 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-slate-600 flex items-center gap-1">
                        <Baby className="w-3.5 h-3.5 text-pink-600" />
                        الرضّع المرافقون ({p.infants.length}) — يظهرون في التقارير فقط
                      </span>
                      <button
                        type="button"
                        onClick={() =>
                          updatePassenger(idx, {
                            infants: [
                              ...p.infants,
                              { full_name: '', id_type: 'birth_certificate', id_number: '', birth_date: '' },
                            ],
                          })
                        }
                        className="text-xs font-bold text-[#1e3a8a] hover:underline flex items-center gap-1"
                      >
                        <Plus className="w-3.5 h-3.5" />
                        إضافة رضيع
                      </button>
                    </div>

                    {p.infants.map((inf, infIdx) => (
                      <div
                        key={infIdx}
                        className="grid grid-cols-1 sm:grid-cols-4 gap-2 bg-white p-2.5 rounded-lg border border-slate-200 items-end"
                      >
                        <Input
                          label="اسم الرضيع"
                          placeholder="الاسم الكامل..."
                          value={inf.full_name}
                          onChange={(e) => {
                            const next = p.infants.map((item, j) =>
                              j === infIdx ? { ...item, full_name: e.target.value } : item
                            );
                            updatePassenger(idx, { infants: next });
                          }}
                        />
                        <div>
                          <label className="block text-xs font-medium text-slate-700 mb-1">نوع الهوية</label>
                          <select
                            value={inf.id_type}
                            onChange={(e) => {
                              const next = p.infants.map((item, j) =>
                                j === infIdx ? { ...item, id_type: e.target.value as IdType, id_number: '' } : item
                              );
                              updatePassenger(idx, { infants: next });
                            }}
                            className="w-full rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-xs"
                          >
                            <option value="birth_certificate">شهادة ميلاد</option>
                            <option value="passport">جواز سفر</option>
                            <option value="national_id">بطاقة شخصية</option>
                          </select>
                        </div>
                        <Input
                          label="رقم الهوية"
                          placeholder={inf.id_type === 'birth_certificate' ? 'اختياري...' : 'رقم الوثيقة...'}
                          value={inf.id_number}
                          onChange={(e) => {
                            const next = p.infants.map((item, j) =>
                              j === infIdx ? { ...item, id_number: e.target.value } : item
                            );
                            updatePassenger(idx, { infants: next });
                          }}
                        />
                        <div className="flex items-end gap-2">
                          <div className="flex-1">
                            <Input
                              label="تاريخ الميلاد"
                              type="date"
                              value={inf.birth_date}
                              onChange={(e) => {
                                const next = p.infants.map((item, j) =>
                                  j === infIdx ? { ...item, birth_date: e.target.value } : item
                                );
                                updatePassenger(idx, { infants: next });
                              }}
                            />
                          </div>
                          <button
                            type="button"
                            onClick={() =>
                              updatePassenger(idx, {
                                infants: p.infants.filter((_, j) => j !== infIdx),
                              })
                            }
                            className="p-2 text-red-500 hover:text-red-700"
                            title="حذف الرضيع"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Step 3: Financials */}
        {currentStep === 3 && (
          <div className="space-y-4">
            {passengers.length > 1 && (
              <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-900 flex flex-wrap items-center justify-between gap-2">
                <span>
                  أنت تُنشئ <strong>{passengers.length} تذاكر نقل بري مستقلة</strong>؛ أدخل <strong>سعر المقعد الواحد</strong> في حقل سعر البيع، والمبلغ المقبوض هو إجمالي السند الموحد الموزع بالتساوي.
                </span>
                <span className="font-bold">
                  إجمالي المقاعد: {(sellingPerSeat * passengers.length).toLocaleString()} {watch('currency') || 'YER'}
                </span>
              </div>
            )}
            <BookingFinancialStep
              form={form}
              selectedCustomer={selectedCustomer}
              passengerCount={passengers.length}
            />
          </div>
        )}

        <div className="flex items-center justify-between pt-6 mt-6 border-t border-slate-100">
          {currentStep > 1 ? (
            <Button type="button" variant="secondary" onClick={prevStep} icon={<ArrowRight className="w-4 h-4" />}>
              السابق
            </Button>
          ) : (
            <Button type="button" variant="ghost" onClick={onCancel}>
              إلغاء
            </Button>
          )}

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
              {passengers.length > 1 ? `تأكيد وإصدار ${passengers.length} تذاكر` : 'تأكيد وحفظ حجز النقل البري'}
            </Button>
          )}
        </div>
      </form>
    </div>
  );
}

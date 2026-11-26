import React, { useState, useMemo } from 'react';
import { useForm } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as yup from 'yup';
import { Plane, ArrowLeft, ArrowRight, CheckCircle2, Plus, Trash2, Users } from 'lucide-react';
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
import { Select } from '../common/Select';
import { Button } from '../common/Button';

type FlightCategory = 'adult' | 'child' | 'infant';

interface FlightPassengerDraft {
  first_middle_name: string;
  last_name: string;
  passenger_phone: string;
  passport_number: string;
  birth_date: string;
  birth_place: string;
  manual_category?: FlightCategory;
}

const emptyFlightPassenger = (): FlightPassengerDraft => ({
  first_middle_name: '',
  last_name: '',
  passenger_phone: '',
  passport_number: '',
  birth_date: '',
  birth_place: '',
});

function detectFlightCategory(birthDateStr: string, depDateStr: string): FlightCategory {
  if (!birthDateStr || !depDateStr) return 'adult';
  const b = new Date(birthDateStr);
  const d = new Date(depDateStr);
  if (isNaN(b.getTime()) || isNaN(d.getTime())) return 'adult';
  let age = d.getFullYear() - b.getFullYear();
  const mDiff = d.getMonth() - b.getMonth();
  if (mDiff < 0 || (mDiff === 0 && d.getDate() < b.getDate())) {
    age--;
  }
  if (age < 2) return 'infant';
  if (age < 12) return 'child';
  return 'adult';
}

const CATEGORY_LABELS: Record<FlightCategory, string> = {
  adult: 'بالغ (12+ سنة)',
  child: 'طفل (2 – 11 سنة)',
  infant: 'رضيع (< سنتين)',
};

const flightSchema = yup.object({
  airline_company: yup.string().required('شركة الطيران مطلوبة'),
  flight_number: yup.string().required('رقم الرحلة مطلوب'),
  departure_airport: yup.string().required('مطار المغادرة مطلوب'),
  arrival_airport: yup.string().required('مطار الوصول مطلوب'),
  departure_date: yup.string().required('تاريخ الذهاب مطلوب'),
  departure_time: yup.string().required('وقت المغادرة مطلوب'),
  ticket_type: yup.string().oneOf(['oneway', 'roundtrip']).required(),
  return_date: yup.string().nullable().optional(),
  return_time: yup.string().nullable().optional(),
  allowed_weight: yup.number().nullable().optional().transform((v) => (isNaN(v) ? null : v)),
  selling_price: yup.number().min(0).default(0),
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

type FlightFormValues = yup.InferType<typeof flightSchema>;

interface FlightBookingFormProps {
  onSuccess: (bookingIds: number | number[]) => void;
  onCancel: () => void;
}

const STEPS = [
  { id: 1, title: 'تفاصيل الرحلة', description: 'الشركة، المسار والمواعيد' },
  { id: 2, title: 'بيانات المسافرين', description: 'الاسم الثلاثي، الجواز والفئة' },
  { id: 3, title: 'المالية والتأكيد', description: 'تسعير الفئات والدفع' },
];

export function FlightBookingForm({ onSuccess, onCancel }: FlightBookingFormProps) {
  const [currentStep, setCurrentStep] = useState(1);
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [passengers, setPassengers] = useState<FlightPassengerDraft[]>([emptyFlightPassenger()]);
  const [passengerError, setPassengerError] = useState<string | null>(null);
  const [categoryPrices, setCategoryPrices] = useState<Record<FlightCategory, string>>({
    adult: '',
    child: '',
    infant: '',
  });
  const [categoryCosts, setCategoryCosts] = useState<Record<FlightCategory, string>>({
    adult: '0',
    child: '0',
    infant: '0',
  });
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
  const departureDate = watch('departure_date') || '';
  const currency = String(watch('currency') || 'YER').toUpperCase();

  const updatePassenger = (idx: number, patch: Partial<FlightPassengerDraft>) => {
    setPassengers((prev) => prev.map((p, i) => (i === idx ? { ...p, ...patch } : p)));
  };

  const resolvedCategories = useMemo(
    () => passengers.map((p) => p.manual_category || detectFlightCategory(p.birth_date, departureDate)),
    [passengers, departureDate]
  );

  const categoryCounts = useMemo(() => {
    const counts: Record<FlightCategory, number> = { adult: 0, child: 0, infant: 0 };
    for (const c of resolvedCategories) counts[c]++;
    return counts;
  }, [resolvedCategories]);

  const totalMultiSelling = useMemo(() => {
    let total = 0;
    (['adult', 'child', 'infant'] as FlightCategory[]).forEach((cat) => {
      if (categoryCounts[cat] > 0) {
        total += categoryCounts[cat] * (parseFloat(categoryPrices[cat] || '0') || 0);
      }
    });
    return Number(total.toFixed(2));
  }, [categoryCounts, categoryPrices]);

  const handleCustomerSelect = (customer: Customer | null) => {
    setSelectedCustomer(customer);
    if (customer) {
      const parts = customer.name.trim().split(/\s+/);
      updatePassenger(0, {
        first_middle_name: parts.slice(0, 3).join(' '),
        last_name: parts.slice(3).join(' '),
        passenger_phone: customer.phone_number || '',
        passport_number: customer.passport_number || '',
      });
      setValue('passenger_name' as any, customer.name);
      setValue('passenger_phone' as any, customer.phone_number);
    }
  };

  const handleOcrExtracted = (data: any) => {
    updatePassenger(0, {
      ...(data.passport_number || data.id_number ? { passport_number: data.passport_number || data.id_number } : {}),
      ...(data.birth_date ? { birth_date: data.birth_date } : {}),
      ...(data.birth_place ? { birth_place: data.birth_place } : {}),
    });
  };

  const validatePassengers = (): boolean => {
    for (let i = 0; i < passengers.length; i++) {
      const p = passengers[i];
      const lbl = `المسافر #${i + 1}`;
      if (p.first_middle_name.trim().split(/\s+/).filter(Boolean).length !== 3) {
        setPassengerError(`${lbl}: الاسم الثلاثي يجب أن يتكون من 3 أسماء بالضبط`);
        return false;
      }
      if (!p.last_name.trim()) {
        setPassengerError(`${lbl}: اللقب مطلوب`);
        return false;
      }
      if (p.passenger_phone.replace(/\D/g, '').length < 9) {
        setPassengerError(`${lbl}: رقم الهاتف يجب أن يكون 9 أرقام على الأقل`);
        return false;
      }
      if (!p.passport_number.trim() || !p.birth_date || !p.birth_place.trim()) {
        setPassengerError(`${lbl}: رقم الجواز وتاريخ ومكان الميلاد مطلوبان`);
        return false;
      }
    }
    setPassengerError(null);
    return true;
  };

  const nextStep = async () => {
    if (currentStep === 1) {
      const fields: (keyof FlightFormValues)[] = [
        'airline_company', 'flight_number', 'departure_airport', 'arrival_airport', 'departure_date', 'departure_time', 'ticket_type',
      ];
      if (ticketType === 'roundtrip') fields.push('return_date', 'return_time');
      if (await trigger(fields)) setCurrentStep(2);
    } else if (currentStep === 2) {
      if (validatePassengers()) {
        if (passengers.length > 1) {
          setValue('selling_price', totalMultiSelling > 0 ? totalMultiSelling : 1);
        }
        setCurrentStep(3);
      }
    }
  };

  const prevStep = () => setCurrentStep((prev) => prev - 1);

  const onSubmit = async (values: FlightFormValues) => {
    if (!validatePassengers()) {
      setCurrentStep(2);
      return;
    }

    const items = passengers.map((p, idx) => ({
      flight_details: {
        airline_company: values.airline_company,
        flight_number: values.flight_number,
        departure_airport: values.departure_airport,
        arrival_airport: values.arrival_airport,
        departure_date: values.departure_date,
        departure_time: values.departure_time,
        return_date: values.ticket_type === 'roundtrip' ? values.return_date : null,
        return_time: values.ticket_type === 'roundtrip' ? values.return_time : null,
        ticket_type: values.ticket_type,
        allowed_weight: values.allowed_weight || null,
        first_middle_name: p.first_middle_name.trim(),
        last_name: p.last_name.trim(),
        passenger_name: `${p.first_middle_name.trim()} ${p.last_name.trim()}`,
        passenger_category: resolvedCategories[idx],
        passenger_phone: p.passenger_phone.trim(),
        passport_number: p.passport_number.trim(),
        birth_date: p.birth_date,
        birth_place: p.birth_place.trim(),
      },
    }));

    const isDeferred = values.payment_method === 'deferred';
    const paidVal = isDeferred ? 0 : (values.paid_amount || 0);
    const pmVal = isDeferred ? 'cash' : (values.payment_method || 'cash');

    if (passengers.length > 1) {
      for (const cat of ['adult', 'child', 'infant'] as FlightCategory[]) {
        if (categoryCounts[cat] > 0 && !(parseFloat(categoryPrices[cat] || '0') > 0)) {
          addToast(`يرجى تحديد سعر البيع لفئة ${CATEGORY_LABELS[cat]}`, 'error');
          return;
        }
      }
    } else if (!(Number(values.selling_price) > 0)) {
      addToast('سعر البيع يجب أن يكون أكبر من الصفر', 'error');
      return;
    }

    setIsSubmitting(true);
    try {
      if (items.length === 1) {
        const res = await api.post('/bookings/', {
          type: 'flight',
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
          flight_details: items[0].flight_details,
        });
        addToast('تم إنشاء حجز الطيران بنجاح', 'success');
        onSuccess(res.data.id);
      } else {
        const catPricesPayload: Record<string, number> = {};
        const catCostsPayload: Record<string, number> = {};
        (['adult', 'child', 'infant'] as FlightCategory[]).forEach((cat) => {
          if (categoryCounts[cat] > 0) {
            catPricesPayload[cat] = parseFloat(categoryPrices[cat] || '0');
            if (!isEmployee) catCostsPayload[cat] = parseFloat(categoryCosts[cat] || '0') || 0;
          }
        });

        const res = await api.post('/bookings/batch', {
          type: 'flight',
          customer_id: selectedCustomer ? selectedCustomer.id : null,
          category_prices: catPricesPayload,
          ...(isEmployee ? {} : { category_costs: catCostsPayload }),
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
        addToast(`تم إصدار ${res.data.count} تذاكر طيران بنجاح: ${(res.data.ticket_numbers || []).join('، ')}`, 'success');
        onSuccess(res.data.booking_ids || []);
      }
    } catch (err: any) {
      addToast(err.response?.data?.detail || 'فشل حفظ حجز الطيران', 'error');
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
          <h2 className="text-lg font-bold text-slate-900">إنشاء حجز طيران جديد (FL)</h2>
          <p className="text-xs text-slate-500">يدعم تعدد المسافرين، التصنيف التلقائي (بالغ/طفل/رضيع)، وتسعير كل فئة</p>
        </div>
      </div>

      <StepperForm steps={STEPS} currentStep={currentStep} />

      <form onSubmit={handleSubmit(onSubmit)}>
        {currentStep === 1 && (
          <div className="space-y-4 animate-in fade-in duration-200">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <Input label="شركة الطيران" placeholder="طيران اليمنية..." required error={errors.airline_company?.message} {...register('airline_company')} />
              <Input label="رقم الرحلة" placeholder="IY 512" required error={errors.flight_number?.message} {...register('flight_number')} />
              <Select label="نوع التذكرة" required error={errors.ticket_type?.message} {...register('ticket_type')} options={[{ value: 'oneway', label: 'ذهاب فقط (One-way)' }, { value: 'roundtrip', label: 'ذهاب وعودة (Round-trip)' }]} />
              <Input label="مطار المغادرة" placeholder="SAH / ADE" required error={errors.departure_airport?.message} {...register('departure_airport')} />
              <Input label="مطار الوصول" placeholder="JED / CAI" required error={errors.arrival_airport?.message} {...register('arrival_airport')} />
              <Input label="الوزن المسموح (كجم)" type="number" placeholder="30" error={errors.allowed_weight?.message} {...register('allowed_weight')} />
              <Input label="تاريخ الذهاب" type="date" required error={errors.departure_date?.message} {...register('departure_date')} />
              <Input label="وقت المغادرة" type="time" required error={errors.departure_time?.message} {...register('departure_time')} />
              {ticketType === 'roundtrip' && (
                <>
                  <Input label="تاريخ العودة" type="date" required error={errors.return_date?.message} {...register('return_date')} />
                  <Input label="وقت العودة" type="time" required error={errors.return_time?.message} {...register('return_time')} />
                </>
              )}
            </div>
          </div>
        )}

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
                <Users className="w-4 h-4 text-[#1e3a8a]" />
                المسافرون ({passengers.length})
              </h4>
              <div className="flex items-center gap-2">
                <OcrScanButton type="passport" onExtracted={handleOcrExtracted} />
                <Button type="button" variant="secondary" onClick={() => setPassengers((prev) => [...prev, emptyFlightPassenger()])} icon={<Plus className="w-4 h-4" />}>
                  إضافة مسافر آخر
                </Button>
              </div>
            </div>

            {passengerError && (
              <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-xs font-bold text-red-700">{passengerError}</div>
            )}

            <div className="space-y-4">
              {passengers.map((p, idx) => {
                const cat = resolvedCategories[idx];
                return (
                  <div key={idx} className="border border-slate-200 rounded-xl p-4 bg-slate-50/60 space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-[#1e3a8a]">المسافر #{idx + 1}</span>
                        <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-blue-100 text-blue-800">
                          {CATEGORY_LABELS[cat]}
                        </span>
                      </div>
                      {passengers.length > 1 && (
                        <button type="button" onClick={() => setPassengers((prev) => prev.filter((_, i) => i !== idx))} className="text-xs text-red-600 hover:underline flex items-center gap-1">
                          <Trash2 className="w-3.5 h-3.5" /> حذف
                        </button>
                      )}
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                      <PassengerNameAutocomplete
                        label="الاسم الثلاثي فقط"
                        placeholder="مثال: محمد أحمد علي"
                        required
                        value={p.first_middle_name}
                        onChange={(val) => {
                          if (idx === 0) setSelectedCustomer(null);
                          updatePassenger(idx, { first_middle_name: val });
                        }}
                        onSelectCustomer={(c) => {
                          const parts = c.name.trim().split(/\s+/);
                          updatePassenger(idx, {
                            first_middle_name: parts.slice(0, 3).join(' '),
                            last_name: parts.slice(3).join(' '),
                            passenger_phone: c.phone_number || '',
                            passport_number: c.passport_number || '',
                          });
                          if (idx === 0) {
                            setSelectedCustomer(c);
                            setValue('passenger_name' as any, c.name);
                            setValue('passenger_phone' as any, c.phone_number);
                          }
                        }}
                      />
                      <PassengerNameAutocomplete
                        label="اللقب"
                        placeholder="مثال: الصالحي"
                        required
                        value={p.last_name}
                        onChange={(val) => {
                          if (idx === 0) setSelectedCustomer(null);
                          updatePassenger(idx, { last_name: val });
                        }}
                        onSelectCustomer={(c) => {
                          const parts = c.name.trim().split(/\s+/);
                          updatePassenger(idx, {
                            first_middle_name: parts.slice(0, 3).join(' '),
                            last_name: parts.slice(3).join(' '),
                            passenger_phone: c.phone_number || '',
                            passport_number: c.passport_number || '',
                          });
                          if (idx === 0) {
                            setSelectedCustomer(c);
                            setValue('passenger_name' as any, c.name);
                            setValue('passenger_phone' as any, c.phone_number);
                          }
                        }}
                      />
                      <Input label="رقم الهاتف" placeholder="77xxxxxxx" required value={p.passenger_phone} onChange={(e) => updatePassenger(idx, { passenger_phone: e.target.value })} />
                      <Input label="رقم الجواز" placeholder="P1234567" required value={p.passport_number} onChange={(e) => updatePassenger(idx, { passport_number: e.target.value })} />
                      <Input label="تاريخ الميلاد" type="date" required value={p.birth_date} onChange={(e) => updatePassenger(idx, { birth_date: e.target.value, manual_category: undefined })} />
                      <Input label="مكان الميلاد" placeholder="صنعاء / عدن..." required value={p.birth_place} onChange={(e) => updatePassenger(idx, { birth_place: e.target.value })} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {currentStep === 3 && (
          <div className="space-y-4">
            {passengers.length > 1 && (
              <div className="p-4 rounded-xl bg-blue-50 border border-blue-200 space-y-3">
                <div className="text-xs font-bold text-blue-900">
                  توزيع الفئات التلقائي: بالغين ({categoryCounts.adult}) | أطفال ({categoryCounts.child}) | رضّع ({categoryCounts.infant}) — الإجمالي المحسوب: {totalMultiSelling.toLocaleString()} {currency}
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  {(['adult', 'child', 'infant'] as FlightCategory[]).map((cat) =>
                    categoryCounts[cat] > 0 ? (
                      <div key={cat} className="bg-white p-3 rounded-lg border border-blue-100 space-y-2">
                        <div className="text-xs font-bold text-slate-800">{CATEGORY_LABELS[cat]} × {categoryCounts[cat]}</div>
                        <Input
                          label={`سعر بيع التذكرة (${currency})`}
                          type="number"
                          step="0.01"
                          value={categoryPrices[cat]}
                          onChange={(e) => {
                            const next = { ...categoryPrices, [cat]: e.target.value };
                            setCategoryPrices(next);
                            const sum = (['adult', 'child', 'infant'] as FlightCategory[]).reduce(
                              (acc, k) => acc + categoryCounts[k] * (parseFloat(next[k] || '0') || 0), 0
                            );
                            setValue('selling_price', Number(sum.toFixed(2)));
                          }}
                        />
                        {!isEmployee && (
                          <Input
                            label={`التكلفة (${currency})`}
                            type="number"
                            step="0.01"
                            value={categoryCosts[cat]}
                            onChange={(e) => {
                              const next = { ...categoryCosts, [cat]: e.target.value };
                              setCategoryCosts(next);
                              const sumCost = (['adult', 'child', 'infant'] as FlightCategory[]).reduce(
                                (acc, k) => acc + categoryCounts[k] * (parseFloat(next[k] || '0') || 0),
                                0
                              );
                              setValue('cost_price', Number(sumCost.toFixed(2)));
                            }}
                          />
                        )}
                      </div>
                    ) : null
                  )}
                </div>
              </div>
            )}
            <BookingFinancialStep form={form} selectedCustomer={selectedCustomer} />
          </div>
        )}

        <div className="flex items-center justify-between pt-6 mt-6 border-t border-slate-100">
          {currentStep > 1 ? (
            <Button type="button" variant="secondary" onClick={prevStep} icon={<ArrowRight className="w-4 h-4" />}>السابق</Button>
          ) : (
            <Button type="button" variant="ghost" onClick={onCancel}>إلغاء</Button>
          )}
          {currentStep < 3 ? (
            <Button type="button" variant="primary" onClick={nextStep} icon={<ArrowLeft className="w-4 h-4" />}>التالي</Button>
          ) : (
            <Button type="submit" variant="primary" isLoading={isSubmitting} icon={<CheckCircle2 className="w-4 h-4" />} className="bg-[#1e3a8a] hover:bg-[#1e3a8a]/90">
              {passengers.length > 1 ? `تأكيد وإصدار ${passengers.length} تذاكر` : 'تأكيد وحفظ الحجز'}
            </Button>
          )}
        </div>
      </form>
    </div>
  );
}

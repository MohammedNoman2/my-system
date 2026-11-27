import React, { useState, useEffect, useCallback, useTransition } from 'react';
import {
  Search,
  RefreshCw,
  Printer,
  Eye,
  Calendar,
  Compass,
  XCircle,
  MoreVertical,
  Filter,
  CheckCircle2,
  Clock,
  Ban,
  Plane,
  Bus,
  Stamp,
  BookOpen,
  Package,
  User,
  Phone,
  CreditCard,
  Building,
  ArrowRight,
  BookMarked,
  Layers,
  AlertCircle,
} from 'lucide-react';
import api from '../../services/api';
import { useAuthStore } from '../../context/authStore';
import { useUIStore } from '../../context/uiStore';
import type { BookingStatus, BookingType, TicketSearchItem, TicketSearchResponse } from '../../types';
import { Card, CardContent } from '../../components/common/Card';
import { Modal } from '../../components/common/Modal';
import { Button } from '../../components/common/Button';
import { Input } from '../../components/common/Input';
import { Spinner } from '../../components/common/Spinner';
import { EmptyState } from '../../components/common/EmptyState';
import { BookingPrintModal } from '../../components/booking/BookingPrintModal';
import { BookingCancelModal } from '../../components/booking/BookingCancelModal';

const TYPE_ICONS: Record<BookingType, React.ReactNode> = {
  flight: <Plane className="w-4 h-4 text-blue-600" />,
  transport: <Bus className="w-4 h-4 text-amber-600" />,
  visa: <Stamp className="w-4 h-4 text-emerald-600" />,
  passport: <BookOpen className="w-4 h-4 text-purple-600" />,
  parcel: <Package className="w-4 h-4 text-orange-600" />,
};

const TYPE_LABELS: Record<BookingType, string> = {
  flight: 'طيران (FL)',
  transport: 'نقل بري (TR)',
  visa: 'تأشيرة (VI)',
  passport: 'جوازات (PA)',
  parcel: 'طرود (PR)',
};

const STATUS_BADGES: Record<BookingStatus, { label: string; className: string; icon: React.ReactNode }> = {
  confirmed: {
    label: 'مؤكد',
    className: 'bg-emerald-50 text-emerald-700 border border-emerald-200',
    icon: <CheckCircle2 className="w-3.5 h-3.5" />,
  },
  pending: {
    label: 'معلق',
    className: 'bg-amber-50 text-amber-700 border border-amber-200',
    icon: <Clock className="w-3.5 h-3.5" />,
  },
  cancelled: {
    label: 'ملغي',
    className: 'bg-red-50 text-red-700 border border-red-200',
    icon: <Ban className="w-3.5 h-3.5" />,
  },
};

export function TicketSearchPage() {
  const { role } = useAuthStore();
  const addToast = useUIStore((state) => state.addToast);

  // Search & Filter State
  const [qName, setQName] = useState('');
  const [qNumber, setQNumber] = useState('');
  const [qTicket, setQTicket] = useState('');
  const [selectedType, setSelectedType] = useState<string>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [page, setPage] = useState(1);

  // Data State
  const [items, setItems] = useState<TicketSearchItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [isLoading, setIsLoading] = useState(false);

  // Modals State
  const [detailsTicket, setDetailsTicket] = useState<TicketSearchItem | null>(null);
  const [detailsJournal, setDetailsJournal] = useState<any | null>(null);
  const [isLoadingJournal, setIsLoadingJournal] = useState(false);

  const [printId, setPrintId] = useState<number | null>(null);
  const [cancellingBooking, setCancellingBooking] = useState<{ id: number; ticket_number: string; paid_amount: number; currency?: string; credit_applied?: number } | null>(null);

  const [postponeTicket, setPostponeTicket] = useState<TicketSearchItem | null>(null);
  const [postponeDate, setPostponeDate] = useState('');
  const [postponeTime, setPostponeTime] = useState('');
  const [postponeReason, setPostponeReason] = useState('');
  const [isSubmittingPostpone, setIsSubmittingPostpone] = useState(false);

  const [rerouteTicket, setRerouteTicket] = useState<TicketSearchItem | null>(null);
  const [newDestination, setNewDestination] = useState('');
  const [newDeparture, setNewDeparture] = useState('');
  const [priceDifference, setPriceDifference] = useState<number>(0);
  const [rerouteReason, setRerouteReason] = useState('');
  const [isSubmittingReroute, setIsSubmittingReroute] = useState(false);

  // Dropdown menu state
  const [activeDropdownId, setActiveDropdownId] = useState<number | null>(null);

  // Voucher Search State
  const [voucherItems, setVoucherItems] = useState<any[]>([]);
  const [isVoucherMode, setIsVoucherMode] = useState(false);

  const fetchTickets = useCallback(async () => {
    // If all fields are empty, don't fetch and clear results
    if (!qName.trim() && !qNumber.trim() && !qTicket.trim() && selectedType === 'all' && selectedStatus === 'all') {
      setItems([]);
      setVoucherItems([]);
      setTotalCount(0);
      setIsVoucherMode(false);
      return;
    }

    // Auto-detect voucher search mode: RC- or PY- prefix in ticket/number field
    const rawQ = qTicket.trim() || qNumber.trim();
    const isVoucher = /^(RC|PY)-/i.test(rawQ) || /^(RC|PY)$/i.test(rawQ.substring(0, 2));

    setIsLoading(true);
    try {
      if (isVoucher && rawQ.length >= 2) {
        setIsVoucherMode(true);
        const res = await api.get('/finance/search', { params: { q: rawQ } });
        setVoucherItems(res.data.items || []);
        setItems([]);
        setTotalCount(res.data.total || 0);
      } else {
        setIsVoucherMode(false);
        const params: any = { page, limit: 50 };
        if (qName.trim()) params.q_name = qName.trim();
        if (qNumber.trim()) params.q_number = qNumber.trim();
        if (qTicket.trim()) params.q_ticket = qTicket.trim();
        if (selectedType !== 'all') params.booking_type = selectedType;
        if (selectedStatus !== 'all') params.status = selectedStatus;

        const res = await api.get<TicketSearchResponse>('/bookings/search', { params });
        setItems(res.data.items);
        setVoucherItems([]);
        setTotalCount(res.data.total);
      }
    } catch (err: any) {
      console.error('Failed to load search results', err);
      addToast('فشل تحميل نتائج البحث', 'error');
    } finally {
      setIsLoading(false);
    }
  }, [qName, qNumber, qTicket, selectedType, selectedStatus, page, addToast]);

  // Fetch Journal Details for Selected Ticket
  const openDetailsModal = async (ticket: TicketSearchItem) => {
    setDetailsTicket(ticket);
    setDetailsJournal(null);
    setIsLoadingJournal(true);
    try {
      const res = await api.get(`/bookings/${ticket.id}/journal`);
      setDetailsJournal(res.data);
    } catch (err) {
      console.error('Failed to load journal lines for booking', err);
    } finally {
      setIsLoadingJournal(false);
    }
  };

  // Handle Postpone Submit
  const handlePostponeSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!postponeTicket || !postponeDate) {
      addToast('يرجى تحديد تاريخ السفر الجديد', 'error');
      return;
    }
    setIsSubmittingPostpone(true);
    try {
      await api.post(`/bookings/${postponeTicket.id}/postpone`, {
        new_travel_date: postponeDate,
        new_travel_time: postponeTime || null,
        reason: postponeReason.trim() || null,
      });
      addToast('تم تأجيل موعد الرحلة وتحديث السجل بنجاح', 'success');
      setPostponeTicket(null);
      fetchTickets();
    } catch (err: any) {
      addToast(err.response?.data?.detail || 'فشل تأجيل موعد الرحلة', 'error');
    } finally {
      setIsSubmittingPostpone(false);
    }
  };

  // Handle Reroute Submit
  const handleRerouteSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rerouteTicket || !newDestination.trim()) {
      addToast('يرجى كتابة محطة/مطار الوصول الجديد', 'error');
      return;
    }
    setIsSubmittingReroute(true);
    try {
      await api.post(`/bookings/${rerouteTicket.id}/reroute`, {
        new_destination: newDestination.trim(),
        new_departure_station: newDeparture.trim() || null,
        price_difference: Number(priceDifference) || 0,
        reason: rerouteReason.trim() || null,
      });
      addToast('تم تغيير مسار الرحلة وتسجيل قيد الفارق المالي بنجاح', 'success');
      setRerouteTicket(null);
      fetchTickets();
    } catch (err: any) {
      addToast(err.response?.data?.detail || 'فشل تغيير مسار الرحلة', 'error');
    } finally {
      setIsSubmittingReroute(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 flex items-center gap-2">
            <span>البحث الموحد عن التذاكر والحجوزات</span>
          </h1>
          <p className="text-sm text-slate-500">
            محرك بحث متقدم بالرقم، الهاتف، الهوية، أو الاسم مع كشف قيود الأستاذ العام وتعديل الرحلات
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={fetchTickets}
            icon={<RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />}
          >
            تحديث
          </Button>
        </div>
      </div>

      {/* Filter & Search Bar */}
      <div className="p-4 bg-white rounded-2xl border border-slate-200 shadow-2xs space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
          {/* Search Inputs */}
          <div className="md:col-span-12 grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="relative" dir="rtl">
              <input
                type="text"
                value={qName}
                onChange={(e) => setQName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && fetchTickets()}
                placeholder="البحث بالاسم (الاسم الكامل / اسم المسافر)"
                className="w-full rounded-xl border border-slate-300 bg-slate-50/70 pr-10 pl-4 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:bg-white focus:ring-2 focus:ring-[#1e3a8a] focus:border-transparent transition-all"
              />
              <User className="w-5 h-5 text-slate-400 absolute inset-y-0 right-3 my-auto pointer-events-none" />
            </div>
            
            <div className="relative" dir="rtl">
              <input
                type="text"
                value={qNumber}
                onChange={(e) => setQNumber(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && fetchTickets()}
                placeholder="البحث بالرقم (الهاتف / الوثيقة / الوطني)"
                className="w-full rounded-xl border border-slate-300 bg-slate-50/70 pr-10 pl-4 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:bg-white focus:ring-2 focus:ring-[#1e3a8a] focus:border-transparent transition-all"
              />
              <Phone className="w-5 h-5 text-slate-400 absolute inset-y-0 right-3 my-auto pointer-events-none" />
            </div>
            
            <div className="relative" dir="rtl">
              <input
                type="text"
                value={qTicket}
                onChange={(e) => setQTicket(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && fetchTickets()}
                placeholder="البحث برقم التذكرة (مثل: FL-0004)"
                className="w-full rounded-xl border border-slate-300 bg-slate-50/70 pr-10 pl-4 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:bg-white focus:ring-2 focus:ring-[#1e3a8a] focus:border-transparent transition-all"
              />
              <BookMarked className="w-5 h-5 text-slate-400 absolute inset-y-0 right-3 my-auto pointer-events-none" />
            </div>
          </div>
          
          <div className="md:col-span-12 flex items-center justify-end">
             <Button type="button" onClick={fetchTickets} icon={<Search className="w-4 h-4" />}>
               بحث الآن
             </Button>
          </div>

          {/* Type Filter */}
          <div className="md:col-span-3">
            <select
              value={selectedType}
              onChange={(e) => {
                setSelectedType(e.target.value);
                setPage(1);
              }}
              className="w-full rounded-xl border border-slate-300 bg-slate-50/70 px-3 py-2.5 text-sm text-slate-800 font-medium focus:outline-none focus:bg-white focus:ring-2 focus:ring-[#1e3a8a]"
            >
              <option value="all">جميع أنواع الخدمات</option>
              <option value="flight">طيران (FL)</option>
              <option value="transport">نقل بري (TR)</option>
              <option value="visa">تأشيرة (VI)</option>
              <option value="passport">جوازات (PA)</option>
              <option value="parcel">طرود (PR)</option>
            </select>
          </div>

          {/* Status Filter */}
          <div className="md:col-span-3">
            <select
              value={selectedStatus}
              onChange={(e) => {
                setSelectedStatus(e.target.value);
                setPage(1);
              }}
              className="w-full rounded-xl border border-slate-300 bg-slate-50/70 px-3 py-2.5 text-sm text-slate-800 font-medium focus:outline-none focus:bg-white focus:ring-2 focus:ring-[#1e3a8a]"
            >
              <option value="all">جميع الحالات</option>
              <option value="confirmed">مؤكد</option>
              <option value="pending">معلق</option>
              <option value="cancelled">ملغي</option>
            </select>
          </div>
        </div>
      </div>

      {/* Results Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-2xs overflow-hidden">
        {isLoading ? (
          <div className="py-20 flex flex-col items-center justify-center gap-3">
            <Spinner size="lg" />
            <p className="text-sm font-semibold text-slate-600">جارٍ فحص ومطابقة البيانات...</p>
          </div>
        ) : isVoucherMode ? (
          /* ─── Voucher Results Table ─── */
          voucherItems.length === 0 ? (
            <EmptyState
              title="لم يتم العثور على أي سند مطابق"
              description="تأكد من إدخال رقم السند بالصيغة الصحيحة: RC-XXXX أو PY-XXXX"
            />
          ) : (
            <div>
              <div className="px-4 py-3 bg-blue-50 border-b border-blue-200 flex items-center gap-2">
                <CreditCard className="w-4 h-4 text-blue-700" />
                <span className="text-sm font-bold text-blue-800">نتائج البحث في السندات المالية ({voucherItems.length} سند)</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-right text-xs sm:text-sm">
                  <thead className="bg-slate-50 text-slate-700 border-b border-slate-200 font-bold">
                    <tr>
                      <th className="px-3 py-3 text-center w-28">الإجراءات</th>
                      <th className="px-3 py-3">رقم السند</th>
                      <th className="px-3 py-3">النوع</th>
                      <th className="px-3 py-3">الطرف المعني</th>
                      <th className="px-3 py-3">المبلغ / العملة</th>
                      <th className="px-3 py-3">طريقة الدفع</th>
                      <th className="px-3 py-3">البيان</th>
                      <th className="px-3 py-3">التاريخ</th>
                      <th className="px-3 py-3">الحالة</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {voucherItems.map((v: any) => (
                      <tr key={v.id} className={`hover:bg-slate-50/80 ${v.is_void ? 'opacity-60 bg-red-50/30' : ''}`}>
                        <td className="px-3 py-2.5 text-center">
                          <button
                            onClick={() => {
                              window.open(`/api/finance/voucher/${v.id}/print?mode=thermal`, '_blank');
                            }}
                            className="flex items-center gap-1 px-2.5 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-lg transition-colors"
                            title="طباعة السند"
                          >
                            <Printer className="w-3.5 h-3.5" />
                            طباعة
                          </button>
                        </td>
                        <td className="px-3 py-2.5 font-mono font-bold text-blue-700">{v.transaction_id}</td>
                        <td className="px-3 py-2.5">
                          <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${
                            v.type === 'payment_in' ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'
                          }`}>
                            {v.type === 'payment_in' ? 'سند قبض (RC)' : 'سند صرف (PY)'}
                          </span>
                        </td>
                        <td className="px-3 py-2.5">
                          <div className="font-bold text-slate-800">{v.entity_name || '--'}</div>
                          <div className="text-slate-500 font-mono text-xs">{v.entity_phone || ''}</div>
                        </td>
                        <td className="px-3 py-2.5 font-bold text-slate-900">
                          {Number(v.amount).toLocaleString()} <span className="text-xs font-normal text-slate-500">{v.currency}</span>
                        </td>
                        <td className="px-3 py-2.5 text-slate-600">
                          {({ cash: 'نقداً', bank_transfer: 'حوالة', check: 'شيك مصرفي', cheque: 'شيك', credit: 'آجل' } as Record<string, string>)[v.payment_method] || v.payment_method}
                        </td>
                        <td className="px-3 py-2.5 text-slate-500 max-w-32 truncate">{v.notes || '--'}</td>
                        <td className="px-3 py-2.5 text-slate-500 whitespace-nowrap">{v.transaction_date ? new Date(v.transaction_date).toLocaleDateString('ar-EG') : '--'}</td>
                        <td className="px-3 py-2.5">
                          {v.is_void ? (
                            <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-red-100 text-red-800">ملغي</span>
                          ) : (
                            <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800">نشط</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )
        ) : items.length === 0 ? (
          <EmptyState
            title="لم يتم العثور على تذاكر"
            description="حاول تعديل شروط البحث أو استخدام كلمات مفتاحية مختلفة"
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-right text-xs sm:text-sm">
              <thead className="bg-slate-50 text-slate-700 border-b border-slate-200 font-bold">
                <tr>
                  {/* Action Column on Leftmost in RTL table */}
                  <th className="px-3 py-3.5 text-center w-28">الإجراءات</th>
                  {/* 10 RTL Columns */}
                  <th className="px-3 py-3.5">1. رقم التذكرة</th>
                  <th className="px-3 py-3.5">2. الاسم والمسافر</th>
                  <th className="px-3 py-3.5">3. رقم الهاتف</th>
                  <th className="px-3 py-3.5">4. نوع الحجز</th>
                  <th className="px-3 py-3.5">5. الشركة / المزود</th>
                  <th className="px-3 py-3.5">6. تاريخ الحجز</th>
                  <th className="px-3 py-3.5">7. مسار الرحلة</th>
                  <th className="px-3 py-3.5">8. موعد الرحلة</th>
                  <th className="px-3 py-3.5">9. الموظف المنفذ</th>
                  <th className="px-3 py-3.5">10. الحالة</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {items.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-50/80 transition-colors">
                    {/* Leftmost Actions Column */}
                    <td className="px-3 py-3 text-center">
                      <div className="flex items-center justify-center gap-1">
                        {/* Details Modal Trigger */}
                        <button
                          type="button"
                          onClick={() => openDetailsModal(item)}
                          title="تفاصيل التذكرة والأثر المحاسبي"
                          className="p-1.5 rounded-lg text-slate-500 hover:text-blue-700 hover:bg-blue-50 transition-colors"
                        >
                          <Eye className="w-4 h-4" />
                        </button>

                        {/* Print Voucher Modal Trigger */}
                        <button
                          type="button"
                          onClick={() => setPrintId(item.id)}
                          title="طباعة السند الرسمي"
                          className="p-1.5 rounded-lg text-slate-500 hover:text-[#1e3a8a] hover:bg-blue-50 transition-colors"
                        >
                          <Printer className="w-4 h-4" />
                        </button>

                        {/* Operations Actions Dropdown */}
                        <div className="relative inline-block text-right">
                          <button
                            type="button"
                            onClick={() =>
                              setActiveDropdownId(activeDropdownId === item.id ? null : item.id)
                            }
                            title="عمليات إضافية"
                            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
                          >
                            <MoreVertical className="w-4 h-4" />
                          </button>

                          {activeDropdownId === item.id && (
                            <>
                              <div
                                className="fixed inset-0 z-30"
                                onClick={() => setActiveDropdownId(null)}
                              />
                              <div className="absolute left-0 mt-1 w-44 rounded-xl bg-white shadow-xl border border-slate-100 py-1.5 z-40 text-xs font-semibold text-slate-700 animate-in fade-in">
                                {/* Postpone */}
                                <button
                                  type="button"
                                  onClick={() => {
                                    setActiveDropdownId(null);
                                    setPostponeTicket(item);
                                    setPostponeDate(item.travel_date || '');
                                    setPostponeTime(item.travel_time || '');
                                    setPostponeReason('');
                                  }}
                                  disabled={item.status === 'cancelled'}
                                  className="w-full text-right px-3 py-2 hover:bg-slate-50 flex items-center gap-2 text-slate-700 disabled:opacity-40"
                                >
                                  <Calendar className="w-3.5 h-3.5 text-amber-500" />
                                  <span>تأجيل موعد الرحلة</span>
                                </button>

                                {/* Reroute */}
                                <button
                                  type="button"
                                  onClick={() => {
                                    setActiveDropdownId(null);
                                    setRerouteTicket(item);
                                    setNewDestination('');
                                    setNewDeparture('');
                                    setPriceDifference(0);
                                    setRerouteReason('');
                                  }}
                                  disabled={item.status === 'cancelled'}
                                  className="w-full text-right px-3 py-2 hover:bg-slate-50 flex items-center gap-2 text-slate-700 disabled:opacity-40"
                                >
                                  <Compass className="w-3.5 h-3.5 text-blue-500" />
                                  <span>تغيير مسار الرحلة</span>
                                </button>

                                {/* Cancel with Refund */}
                                <button
                                  type="button"
                                  onClick={() => {
                                    setActiveDropdownId(null);
                                    setCancellingBooking({
                                      id: item.id,
                                      ticket_number: item.ticket_number,
                                      paid_amount: item.paid_amount,
                                      currency: item.currency,
                                      credit_applied: Number((item as any).credit_applied || 0),
                                    });
                                  }}
                                  disabled={item.status === 'cancelled'}
                                  className="w-full text-right px-3 py-2 hover:bg-red-50 flex items-center gap-2 text-red-600 disabled:opacity-40"
                                >
                                  <XCircle className="w-3.5 h-3.5 text-red-500" />
                                  <span>إلغاء التذكرة والمحاسبة</span>
                                </button>
                              </div>
                            </>
                          )}
                        </div>
                      </div>
                    </td>

                    {/* Column 1: Ticket Number */}
                    <td className="px-3 py-3 font-mono font-bold text-[#1e3a8a] whitespace-nowrap">
                      {item.ticket_number}
                    </td>

                    {/* Column 2: Passenger Name */}
                    <td className="px-3 py-3">
                      <p className="font-bold text-slate-800">{item.passenger_name}</p>
                      {item.identity_number && (
                        <p className="text-[11px] text-slate-400 font-mono">
                          هوية/جواز: {item.identity_number}
                        </p>
                      )}
                    </td>

                    {/* Column 3: Passenger Phone */}
                    <td className="px-3 py-3 text-slate-700 font-mono whitespace-nowrap">
                      {item.passenger_phone || '--'}
                    </td>

                    {/* Column 4: Booking Type */}
                    <td className="px-3 py-3 whitespace-nowrap">
                      <div className="flex items-center gap-1.5 font-medium">
                        {TYPE_ICONS[item.type]}
                        <span>{TYPE_LABELS[item.type]}</span>
                      </div>
                    </td>

                    {/* Column 5: Company Name */}
                    <td className="px-3 py-3 text-slate-700 font-medium">
                      {item.company_name || 'عالم النقل'}
                    </td>

                    {/* Column 6: Booking Date */}
                    <td className="px-3 py-3 text-slate-500 whitespace-nowrap font-mono text-xs">
                      {item.booking_date ? new Date(item.booking_date).toLocaleDateString('ar-EG') : '--'}
                    </td>

                    {/* Column 7: Route */}
                    <td className="px-3 py-3 text-slate-800 font-medium max-w-[160px] truncate" title={item.route}>
                      {item.route || '--'}
                    </td>

                    {/* Column 8: Travel Date & Time */}
                    <td className="px-3 py-3 text-slate-600 whitespace-nowrap text-xs font-mono">
                      {item.travel_date || '--'} {item.travel_time ? `(${item.travel_time})` : ''}
                    </td>

                    {/* Column 9: Employee Name */}
                    <td className="px-3 py-3 text-slate-700 whitespace-nowrap">
                      <span className="inline-flex items-center gap-1 text-xs">
                        <User className="w-3.5 h-3.5 text-slate-400" />
                        {item.employee_name || 'مدير النظام'}
                      </span>
                    </td>

                    {/* Column 10: Status */}
                    <td className="px-3 py-3 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center gap-1 text-[11px] font-bold px-2.5 py-0.5 rounded-full ${
                          STATUS_BADGES[item.status]?.className || 'bg-slate-100 text-slate-700'
                        }`}
                      >
                        {STATUS_BADGES[item.status]?.icon}
                        {STATUS_BADGES[item.status]?.label || item.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Details & Accounting Modal */}
      {detailsTicket && (
        <Modal
          isOpen={!!detailsTicket}
          onClose={() => setDetailsTicket(null)}
          title={`تفاصيل التذكرة والأثر المحاسبي (${detailsTicket.ticket_number})`}
          description="بيانات الحجز وسندات القيد المزدوج المرتبطة ورصيد العميل اللحظي"
          size="xl"
        >
          <div className="space-y-6 text-sm">
            {/* Ticket Overview Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200">
                <p className="text-xs text-slate-500 font-semibold mb-1">المسافر والعميل</p>
                <p className="font-bold text-slate-800 text-base">{detailsTicket.passenger_name}</p>
                <p className="text-xs text-slate-600 mt-1 font-mono">
                  الهاتف: {detailsTicket.passenger_phone || '--'}
                </p>
                {detailsTicket.identity_number && (
                  <p className="text-xs text-slate-500 font-mono mt-0.5">
                    الوثيقة: {detailsTicket.identity_number}
                  </p>
                )}
              </div>

              <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200">
                <p className="text-xs text-slate-500 font-semibold mb-1">الرحلة والخدمة</p>
                <p className="font-bold text-slate-800">{detailsTicket.company_name}</p>
                <p className="text-xs text-slate-700 mt-1 font-medium">{detailsTicket.route}</p>
                <p className="text-xs text-slate-500 mt-0.5">
                  الموعد: {detailsTicket.travel_date || '--'} {detailsTicket.travel_time || ''}
                </p>
              </div>

              <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200">
                <p className="text-xs text-slate-500 font-semibold mb-1">البيانات المالية والرصيد</p>
                <div className="flex justify-between text-xs py-0.5">
                  <span className="text-slate-500">سعر البيع:</span>
                  <span className="font-bold text-slate-800">
                    {Number(detailsTicket.selling_price).toLocaleString()} {detailsTicket.currency}
                  </span>
                </div>
                <div className="flex justify-between text-xs py-0.5">
                  <span className="text-slate-500">المدفوع:</span>
                  <span className="font-bold text-emerald-600">
                    {Number(detailsTicket.paid_amount).toLocaleString()} {detailsTicket.currency}
                  </span>
                </div>
                <div className="flex justify-between text-xs py-0.5 border-t border-slate-200 mt-1 pt-1">
                  <span className="text-slate-500 font-semibold">رصيد العميل الحالي:</span>
                  <span
                    className={`font-black ${
                      (detailsJournal?.customer_balance || 0) > 0
                        ? 'text-red-600'
                        : (detailsJournal?.customer_balance || 0) < 0
                        ? 'text-emerald-600'
                        : 'text-slate-700'
                    }`}
                  >
                    {Number(detailsJournal?.customer_balance ?? detailsTicket.customer_balance ?? 0).toLocaleString()}{' '}
                    {detailsTicket.currency}
                  </span>
                </div>
              </div>
            </div>

            {/* General Ledger Journal Entries Section */}
            <div className="space-y-3">
              <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                <h4 className="text-sm font-bold text-slate-800 flex items-center gap-2">
                  <Layers className="w-4 h-4 text-[#1e3a8a]" />
                  <span>قيود اليومية العامة (General Ledger Double-Entry)</span>
                </h4>
                <span className="text-xs text-slate-500">
                  {detailsJournal?.journal_entries?.length || 0} قيد محاسبي مرتبط
                </span>
              </div>

              {isLoadingJournal ? (
                <div className="py-8 text-center text-slate-500 text-xs">
                  جارٍ استرجاع قيود الأستاذ العام...
                </div>
              ) : !detailsJournal?.journal_entries || detailsJournal.journal_entries.length === 0 ? (
                <div className="p-4 bg-slate-50 rounded-xl text-center text-xs text-slate-500">
                  لا توجد قيود يومية مسجلة مباشرة لهذا الحجز.
                </div>
              ) : (
                <div className="space-y-4 max-h-[300px] overflow-y-auto pr-1">
                  {detailsJournal.journal_entries.map((je: any) => (
                    <div
                      key={je.id}
                      className="p-3 bg-white rounded-xl border border-slate-200 shadow-2xs space-y-2"
                    >
                      <div className="flex items-center justify-between text-xs text-slate-600">
                        <span className="font-mono font-bold text-[#1e3a8a]">
                          قيد رقم: {je.entry_number} ({je.reference_type})
                        </span>
                        <span>{new Date(je.date).toLocaleString('ar-EG')}</span>
                      </div>
                      <p className="text-xs text-slate-700 font-medium">{je.description}</p>

                      <div className="overflow-x-auto">
                        <table className="w-full text-xs text-right mt-1 border-t border-slate-100">
                          <thead className="bg-slate-50 text-slate-500 font-semibold">
                            <tr>
                              <th className="py-1 px-2">كود الحساب</th>
                              <th className="py-1 px-2">اسم الحساب</th>
                              <th className="py-1 px-2 text-left">مدين (Debit)</th>
                              <th className="py-1 px-2 text-left">دائن (Credit)</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100">
                            {je.lines.map((line: any) => (
                              <tr key={line.id}>
                                <td className="py-1 px-2 font-mono text-slate-600">
                                  {line.account_code}
                                </td>
                                <td className="py-1 px-2 font-medium text-slate-800">
                                  {line.account_name}
                                </td>
                                <td className="py-1 px-2 text-left font-mono font-bold text-slate-900">
                                  {line.debit > 0 ? Number(line.debit).toLocaleString() : '-'}
                                </td>
                                <td className="py-1 px-2 text-left font-mono font-bold text-slate-900">
                                  {line.credit > 0 ? Number(line.credit).toLocaleString() : '-'}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Footer Buttons */}
            <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => {
                  setPrintId(detailsTicket.id);
                  setDetailsTicket(null);
                }}
                icon={<Printer className="w-4 h-4" />}
              >
                طباعة السند
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setDetailsTicket(null)}
              >
                إغلاق
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Postpone Modal */}
      {postponeTicket && (
        <Modal
          isOpen={!!postponeTicket}
          onClose={() => setPostponeTicket(null)}
          title={`تأجيل موعد الرحلة (${postponeTicket.ticket_number})`}
          description="تعديل تاريخ ووقت السفر مع توثيق التغيير في سجل التدقيق"
          size="md"
        >
          <form onSubmit={handlePostponeSubmit} className="space-y-4">
            <div className="p-3 bg-blue-50 text-blue-800 rounded-xl text-xs flex items-start gap-2">
              <Calendar className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
              <span>
                الموعد الحالي المسجل للتذكرة هو ({postponeTicket.travel_date || '--'} / {postponeTicket.travel_time || '--'}).
              </span>
            </div>

            <Input
              label="تاريخ السفر الجديد"
              type="date"
              required
              value={postponeDate}
              onChange={(e) => setPostponeDate(e.target.value)}
            />

            <Input
              label="وقت السفر الجديد (اختياري)"
              type="time"
              value={postponeTime}
              onChange={(e) => setPostponeTime(e.target.value)}
            />

            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1">
                سبب التأجيل
              </label>
              <textarea
                rows={2}
                value={postponeReason}
                onChange={(e) => setPostponeReason(e.target.value)}
                placeholder="مثال: طلب العميل تأجيل السفر بسبب ظروف طارئة..."
                className="w-full rounded-lg border border-slate-300 p-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1e3a8a]"
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setPostponeTicket(null)}
              >
                تراجع
              </Button>
              <Button
                type="submit"
                variant="primary"
                isLoading={isSubmittingPostpone}
              >
                تأكيد التأجيل
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {/* Reroute Modal */}
      {rerouteTicket && (
        <Modal
          isOpen={!!rerouteTicket}
          onClose={() => setRerouteTicket(null)}
          title={`تعديل مسار الرحلة (${rerouteTicket.ticket_number})`}
          description="تعديل المحطة/المطار المستهدف وتسجيل قيد الفارق المالي آلياً"
          size="md"
        >
          <form onSubmit={handleRerouteSubmit} className="space-y-4">
            <div className="p-3 bg-amber-50 text-amber-800 rounded-xl text-xs flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              <span>
                المسار الحالي: <strong>{rerouteTicket.route}</strong>. في حال وجود فارق سعر إيجابي أو سلبي، سيتم توليد قيد تسوية محاسبي فوري في الأستاذ العام وتحديث رصيد العميل.
              </span>
            </div>

            <Input
              label="محطة / مطار الوصول الجديد"
              placeholder="مثال: جدة (JED) / مكة / الرياض..."
              required
              value={newDestination}
              onChange={(e) => setNewDestination(e.target.value)}
            />

            <Input
              label="محطة / مطار المغادرة الجديد (اختياري)"
              placeholder="اتركه فارغاً إذا لم يتغير مطار الإقلاع"
              value={newDeparture}
              onChange={(e) => setNewDeparture(e.target.value)}
            />

            <Input
              label={`فارق السعر (${rerouteTicket.currency})`}
              type="number"
              step="0.01"
              placeholder="0.00"
              value={priceDifference}
              onChange={(e) => setPriceDifference(Number(e.target.value))}
              helperText="أدخل قيمة موجبة إذا زاد السعر على العميل، أو قيمة سالبة إذا خُفض السعر"
            />

            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1">
                سبب تغيير المسار
              </label>
              <textarea
                rows={2}
                value={rerouteReason}
                onChange={(e) => setRerouteReason(e.target.value)}
                placeholder="مثال: رغبة الراكب في النزول بمحطة أخرى..."
                className="w-full rounded-lg border border-slate-300 p-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1e3a8a]"
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setRerouteTicket(null)}
              >
                تراجع
              </Button>
              <Button
                type="submit"
                variant="primary"
                isLoading={isSubmittingReroute}
              >
                تأكيد التعديل والأثر المالي
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {/* Print Modal */}
      <BookingPrintModal
        bookingId={printId}
        isOpen={!!printId}
        onClose={() => setPrintId(null)}
      />

      {/* Cancel Modal */}
      <BookingCancelModal
        booking={cancellingBooking}
        isOpen={!!cancellingBooking}
        onClose={() => setCancellingBooking(null)}
        onSuccess={fetchTickets}
      />
    </div>
  );
}

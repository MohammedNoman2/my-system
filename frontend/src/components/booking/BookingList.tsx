import React, { useState, useEffect } from 'react';
import {
  Printer,
  XCircle,
  Search,
  Filter,
  RefreshCw,
  Plane,
  Bus,
  Stamp,
  BookOpen,
  Package,
} from 'lucide-react';
import api from '../../services/api';
import { useAuthStore } from '../../context/authStore';
import type { Booking, BookingType } from '../../types';
import { Spinner } from '../common/Spinner';
import { EmptyState } from '../common/EmptyState';
import { BookingPrintModal } from './BookingPrintModal';
import { BookingCancelModal } from './BookingCancelModal';

const TYPE_ICONS: Record<BookingType, React.ReactNode> = {
  flight: <Plane className="w-4 h-4 text-blue-600" />,
  transport: <Bus className="w-4 h-4 text-amber-600" />,
  visa: <Stamp className="w-4 h-4 text-emerald-600" />,
  passport: <BookOpen className="w-4 h-4 text-purple-600" />,
  parcel: <Package className="w-4 h-4 text-orange-600" />,
};

const TYPE_LABELS: Record<BookingType, string> = {
  flight: 'طيران',
  transport: 'نقل بري',
  visa: 'تأشيرة',
  passport: 'جوازات',
  parcel: 'طرود',
};

export function BookingList() {
  const { role } = useAuthStore();
  const isEmployee = role === 'employee';

  const [bookings, setBookings] = useState<Booking[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState<string>('all');

  const [selectedPrintId, setSelectedPrintId] = useState<number | null>(null);
  const [cancellingBooking, setCancellingBooking] = useState<Booking | null>(null);

  const fetchBookings = async () => {
    setIsLoading(true);
    try {
      const params: any = { limit: 100 };
      if (typeFilter !== 'all') params.booking_type = typeFilter;
      if (searchQuery.trim()) params.search = searchQuery.trim();

      const res = await api.get('/bookings/', { params });
      setBookings(res.data);
    } catch (err) {
      console.error('Failed to load bookings', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchBookings();
  }, [typeFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchBookings();
  };

  const statusBadges: Record<string, { label: string; className: string }> = {
    pending: { label: 'معلق', className: 'bg-amber-100 text-amber-800' },
    confirmed: { label: 'مؤكد', className: 'bg-emerald-100 text-emerald-800' },
    cancelled: { label: 'ملغي', className: 'bg-red-100 text-red-800' },
  };

  const getPaymentBadge = (b: Booking) => {
    if (b.status === 'cancelled') return { label: 'ملغي', className: 'bg-slate-100 text-slate-500' };
    if (Number(b.remaining_amount) <= 0 && Number(b.paid_amount) > 0) {
      return { label: 'مدفوع بالكامل', className: 'bg-emerald-50 text-emerald-700 border border-emerald-200' };
    }
    if (Number(b.paid_amount) > 0) {
      return { label: 'مدفوع جزئياً', className: 'bg-sky-50 text-sky-700 border border-sky-200' };
    }
    return { label: 'غير مدفوع (آجل)', className: 'bg-amber-50 text-amber-700 border border-amber-200' };
  };

  return (
    <div className="space-y-4">
      {/* Filters & Search Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 bg-white rounded-2xl border border-slate-200 shadow-2xs">
        <form onSubmit={handleSearchSubmit} className="relative flex-1 max-w-md">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="بحث برقم التذكرة، اسم العميل، الهاتف..."
            className="w-full rounded-xl border border-slate-200 bg-slate-50 pr-9 pl-4 py-2 text-xs sm:text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:bg-white focus:ring-2 focus:ring-[#1e3a8a]"
          />
          <button
            type="submit"
            className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600"
          >
            <Search className="w-4 h-4" />
          </button>
        </form>

        <div className="flex items-center gap-2 overflow-x-auto pb-1 sm:pb-0">
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs sm:text-sm font-medium text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#1e3a8a]"
          >
            <option value="all">جميع أنواع الخدمات</option>
            <option value="flight">طيران (FL)</option>
            <option value="transport">نقل بري (TR)</option>
            <option value="visa">تأشيرات (VI)</option>
            <option value="passport">جوازات (PA)</option>
            <option value="parcel">طرود (PR)</option>
          </select>

          <button
            onClick={fetchBookings}
            className="p-2 rounded-xl border border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100 transition-colors"
            title="تحديث البيانات"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Bookings Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-2xs overflow-hidden">
        {isLoading ? (
          <div className="py-16">
            <Spinner size="lg" label="جارٍ تحميل سجل الحجوزات..." />
          </div>
        ) : bookings.length === 0 ? (
          <EmptyState
            title="لا توجد حجوزات مطابقة"
            description="لم يتم العثور على أي حجز مسجل حسب معايير البحث الحالية."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-right text-xs sm:text-sm">
              <thead className="bg-slate-50 text-slate-600 border-b border-slate-200 font-semibold">
                <tr>
                  <th className="px-4 py-3">رقم التذكرة</th>
                  <th className="px-4 py-3">النوع</th>
                  <th className="px-4 py-3">العميل / المسافر</th>
                  <th className="px-4 py-3">التاريخ</th>
                  <th className="px-4 py-3">سعر البيع</th>
                  <th className="px-4 py-3">المدفوع</th>
                  <th className="px-4 py-3">المتبقي</th>
                  {/* cost_price STRICTLY absent from DOM for employee */}
                  {!isEmployee && <th className="px-4 py-3">التكلفة</th>}
                  <th className="px-4 py-3">الحالة</th>
                  <th className="px-4 py-3 text-center">الإجراءات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {bookings.map((b) => (
                  <tr key={b.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="px-4 py-3 font-mono font-bold text-[#1e3a8a]">
                      {b.ticket_number}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5 font-medium">
                        {TYPE_ICONS[b.type]}
                        <span>{TYPE_LABELS[b.type]}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <p className="font-semibold text-slate-800">
                        {b.customer?.name || 'عميل'}
                      </p>
                      <p className="text-[11px] text-slate-400">
                        {b.customer?.phone_number || '--'}
                      </p>
                    </td>
                    <td className="px-4 py-3 text-slate-500 whitespace-nowrap">
                      {b.booking_date ? new Date(b.booking_date).toLocaleDateString('ar-EG') : '--'}
                    </td>
                    <td className="px-4 py-3 font-semibold text-slate-800">
                      {Number(b.selling_price).toLocaleString()} {b.currency}
                    </td>
                    <td className="px-4 py-3 text-emerald-600 font-semibold">
                      {Number(b.paid_amount).toLocaleString()} {b.currency}
                    </td>
                    <td className="px-4 py-3 font-semibold text-slate-700">
                      {Number(b.remaining_amount).toLocaleString()} {b.currency}
                    </td>
                    {/* Cost Price: only for admin / accountant */}
                    {!isEmployee && (
                      <td className="px-4 py-3 text-slate-500">
                        {Number(b.cost_price || 0).toLocaleString()} {b.currency}
                      </td>
                    )}
                    <td className="px-4 py-3">
                      <div className="flex flex-col items-start gap-1">
                        <span
                          className={`inline-block text-[11px] font-bold px-2 py-0.5 rounded-full ${
                            statusBadges[b.status]?.className || 'bg-slate-100 text-slate-700'
                          }`}
                        >
                          {statusBadges[b.status]?.label || b.status}
                        </span>
                        <span
                          className={`inline-block text-[10px] font-semibold px-2 py-0.5 rounded-md ${
                            getPaymentBadge(b).className
                          }`}
                        >
                          {getPaymentBadge(b).label}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex items-center justify-center gap-1.5">
                        <button
                          onClick={() => setSelectedPrintId(b.id)}
                          title="طباعة السند"
                          className="p-1.5 rounded-lg text-slate-500 hover:text-[#1e3a8a] hover:bg-blue-50 transition-colors"
                        >
                          <Printer className="w-4 h-4" />
                        </button>
                        {b.status !== 'cancelled' && (
                          <button
                            onClick={() => setCancellingBooking(b)}
                            title="إلغاء الحجز"
                            className="p-1.5 rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                          >
                            <XCircle className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Print Modal */}
      <BookingPrintModal
        bookingId={selectedPrintId}
        isOpen={!!selectedPrintId}
        onClose={() => setSelectedPrintId(null)}
      />

      {/* Cancel Modal */}
      <BookingCancelModal
        booking={cancellingBooking}
        isOpen={!!cancellingBooking}
        onClose={() => setCancellingBooking(null)}
        onSuccess={fetchBookings}
      />
    </div>
  );
}

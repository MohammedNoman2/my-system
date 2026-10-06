import React, { useState } from 'react';
import {
  LayoutDashboard,
  PlusCircle,
  Plane,
  Bus,
  Stamp,
  BookOpen,
  Package,
} from 'lucide-react';
import { BookingDashboard } from '../../components/booking/BookingDashboard';
import { FlightBookingForm } from '../../components/booking/FlightBookingForm';
import { TransportBookingForm } from '../../components/booking/TransportBookingForm';
import { VisaBookingForm } from '../../components/booking/VisaBookingForm';
import { PassportBookingForm } from '../../components/booking/PassportBookingForm';
import { ParcelBookingForm } from '../../components/booking/ParcelBookingForm';
import { BookingPrintModal } from '../../components/booking/BookingPrintModal';

type TabType = 'list' | 'flight' | 'transport' | 'visa' | 'passport' | 'parcel';

export function BookingsPage() {
  const [activeTab, setActiveTab] = useState<TabType>('list');
  const [autoPrintId, setAutoPrintId] = useState<number | null>(null);

  const handleBookingSuccess = (newBookingId: number) => {
    // Open voucher print modal automatically per §4.5
    setAutoPrintId(newBookingId);
    setActiveTab('list');
  };

  const tabs: { id: TabType; label: string; icon: React.ReactNode }[] = [
    { id: 'list', label: 'الملخص اليومي', icon: <LayoutDashboard className="w-4 h-4" /> },
    { id: 'flight', label: 'حجز طيران (FL)', icon: <Plane className="w-4 h-4" /> },
    { id: 'transport', label: 'نقل بري (TR)', icon: <Bus className="w-4 h-4" /> },
    { id: 'visa', label: 'معاملة تأشيرة (VI)', icon: <Stamp className="w-4 h-4" /> },
    { id: 'passport', label: 'معاملة جواز (PA)', icon: <BookOpen className="w-4 h-4" /> },
    { id: 'parcel', label: 'بوليصة طرد (PR)', icon: <Package className="w-4 h-4" /> },
  ];

  return (
    <div className="space-y-6">
      {/* Navigation Tabs Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900">محرك وإدارة الحجوزات</h1>
          <p className="text-sm text-slate-500">
            إنشاء وإصدار التذاكر وسندات الحجز للخدمات الخمس الرسمية
          </p>
        </div>

        {/* Tab switcher buttons */}
        <div className="flex items-center gap-1.5 p-1 bg-slate-200/80 rounded-2xl overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs sm:text-sm font-bold transition-all whitespace-nowrap ${
                activeTab === tab.id
                  ? 'bg-white text-[#1e3a8a] shadow-sm'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-white/40'
              }`}
            >
              {tab.icon}
              <span>{tab.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      <div className="mt-4">
        {activeTab === 'list' && <BookingDashboard />}
        {activeTab === 'flight' && (
          <FlightBookingForm
            onSuccess={handleBookingSuccess}
            onCancel={() => setActiveTab('list')}
          />
        )}
        {activeTab === 'transport' && (
          <TransportBookingForm
            onSuccess={handleBookingSuccess}
            onCancel={() => setActiveTab('list')}
          />
        )}
        {activeTab === 'visa' && (
          <VisaBookingForm
            onSuccess={handleBookingSuccess}
            onCancel={() => setActiveTab('list')}
          />
        )}
        {activeTab === 'passport' && (
          <PassportBookingForm
            onSuccess={handleBookingSuccess}
            onCancel={() => setActiveTab('list')}
          />
        )}
        {activeTab === 'parcel' && (
          <ParcelBookingForm
            onSuccess={handleBookingSuccess}
            onCancel={() => setActiveTab('list')}
          />
        )}
      </div>

      {/* Auto-print modal after successful booking */}
      <BookingPrintModal
        bookingId={autoPrintId}
        isOpen={!!autoPrintId}
        onClose={() => setAutoPrintId(null)}
      />
    </div>
  );
}

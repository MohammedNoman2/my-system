import React, { useEffect, useState } from 'react';
import { Plane, Bus, Stamp, BookOpen, Package, DollarSign, AlertTriangle } from 'lucide-react';
import api from '../../services/api';

export function BookingDashboard() {
  const [stats, setStats] = useState({
    today_sales: {} as Record<string, number>,
    counts: { flight: 0, transport: 0, visa: 0, passport: 0, parcel: 0 },
    late_debts: [] as any[],
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchStats() {
      try {
        const res = await api.get('/bookings/?limit=200'); // Fetch recent bookings
        const bookings = res.data;
        
        let sales: Record<string, number> = {};
        let counts = { flight: 0, transport: 0, visa: 0, passport: 0, parcel: 0 };
        let late_debts: any[] = [];
        
        const todayStr = new Date().toISOString().split('T')[0];

        bookings.forEach((b: any) => {
          const curr = b.currency || 'YER';
          // Check if booked today
          const bDate = b.booking_date?.split('T')[0];
          if (bDate === todayStr) {
            sales[curr] = (sales[curr] || 0) + (b.selling_price || 0);
            if (counts[b.type as keyof typeof counts] !== undefined) {
              counts[b.type as keyof typeof counts]++;
            }
          }
          
          if (b.remaining_amount > 0) {
            late_debts.push(b);
          }
        });

        setStats({ today_sales: sales, counts, late_debts });
      } catch (err) {
        console.error('Failed to load stats', err);
      } finally {
        setLoading(false);
      }
    }
    fetchStats();
  }, []);

  if (loading) return <div className="p-8 text-center text-slate-500 font-medium">جاري تحميل الملخص اليومي...</div>;

  return (
    <div className="space-y-6">
      {/* Overview Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-center">
          <div className="flex items-center gap-2 mb-2">
            <DollarSign className="w-5 h-5 text-emerald-600" />
            <span className="text-sm font-bold text-slate-700">مبيعات اليوم</span>
          </div>
          {Object.keys(stats.today_sales).length === 0 ? (
            <p className="text-2xl font-black text-slate-900">0</p>
          ) : (
            <div className="space-y-1">
              {Object.entries(stats.today_sales).map(([curr, amount]) => (
                <p key={curr} className="text-xl font-black text-slate-900">
                  {amount.toLocaleString()} <span className="text-sm font-normal text-slate-500">{curr}</span>
                </p>
              ))}
            </div>
          )}
        </div>
      </div>
      
      {/* Types Breakdown */}
      <h3 className="text-lg font-bold text-slate-800">حجوزات اليوم حسب النوع</h3>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
        {[
          { label: 'طيران', icon: Plane, color: 'blue', key: 'flight' },
          { label: 'نقل بري', icon: Bus, color: 'amber', key: 'transport' },
          { label: 'تأشيرات', icon: Stamp, color: 'purple', key: 'visa' },
          { label: 'جوازات', icon: BookOpen, color: 'emerald', key: 'passport' },
          { label: 'طرود', icon: Package, color: 'orange', key: 'parcel' },
        ].map((item, idx) => (
          <div key={idx} className={`bg-${item.color}-50 border border-${item.color}-100 p-4 rounded-xl flex flex-col items-center justify-center`}>
            <item.icon className={`w-6 h-6 text-${item.color}-600 mb-2`} />
            <span className={`text-sm font-bold text-${item.color}-900`}>{item.label}</span>
            <span className={`text-xl font-black text-${item.color}-700 mt-1`}>{stats.counts[item.key as keyof typeof stats.counts]}</span>
          </div>
        ))}
      </div>

      {/* Alerts */}
      <div className="bg-red-50 border border-red-200 p-4 rounded-xl">
         <h4 className="text-sm font-bold text-red-800 flex items-center gap-2 mb-2">
            <AlertTriangle className="w-4 h-4" />
            تنبيهات المتابعة والمديونيات المتأخرة
         </h4>
         {stats.late_debts.length > 0 ? (
           <div className="space-y-2 mt-3">
             {stats.late_debts.slice(0, 5).map((d: any) => (
               <div key={d.id} className="flex justify-between items-center text-xs bg-white/60 p-2 rounded-lg border border-red-100">
                 <span className="font-medium text-slate-800">{d.customer?.name || d.ticket_number}</span>
                 <span className="text-red-600 font-bold">متبقي: {d.remaining_amount.toLocaleString()} {d.currency || 'YER'}</span>
               </div>
             ))}
             {stats.late_debts.length > 5 && <div className="text-xs text-red-500 mt-2">وأكثر من {stats.late_debts.length - 5} مديونيات أخرى...</div>}
           </div>
         ) : (
           <p className="text-xs text-red-600">لا توجد مديونيات حرجة لليوم.</p>
         )}
      </div>
    </div>
  );
}

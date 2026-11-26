import React, { useEffect, useState } from 'react';
import {
  CalendarCheck,
  TrendingUp,
  CreditCard,
  Users,
  AlertTriangle,
  Clock,
  ArrowUpRight,
  ArrowDownRight,
  Receipt,
  PlusCircle,
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';
import { Link } from 'react-router-dom';
import api from '../../services/api';
import { useAuthStore } from '../../context/authStore';
import { Card, CardHeader, CardTitle, CardContent } from '../../components/common/Card';
import { Spinner } from '../../components/common/Spinner';

const SERVICE_COLORS = ['#1e3a8a', '#0284c7', '#10b981', '#f59e0b', '#8b5cf6'];

export function DashboardPage() {
  const { user, role } = useAuthStore();
  const [summary, setSummary] = useState<any>(null);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function loadDashboardData() {
      try {
        const [sumRes, alertRes] = await Promise.all([
          api.get('/dashboard/summary'),
          api.get('/dashboard/alerts'),
        ]);
        setSummary(sumRes.data);
        setAlerts(alertRes.data);
      } catch (err) {
        console.error('Failed to load dashboard data', err);
      } finally {
        setIsLoading(false);
      }
    }
    loadDashboardData();
  }, []);

  if (isLoading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <Spinner size="lg" label="جارٍ تحميل مؤشرات لوحة التحكم..." />
      </div>
    );
  }

  const monthlyChartData = summary?.monthly_series || [];
  const servicesDistribution = summary?.services_distribution || [];

  const isEmployee = role === 'employee';

  return (
    <div className="space-y-6">
      {/* Top Welcome & Quick Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900">لوحة التحكم والمؤشرات</h1>
          <p className="text-sm text-slate-500">
            مرحباً {user?.full_name} ({role === 'admin' ? 'مدير عام' : role === 'accountant' ? 'محاسب' : 'موظف حجز'}) — ملخص الأعمال اليومية والمؤشرات المالية
          </p>
        </div>

        <div className="flex items-center gap-2">
          {(role === 'admin' || role === 'employee') && (
            <Link
              to="/bookings"
              className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs sm:text-sm font-semibold text-white bg-[#1e3a8a] rounded-lg shadow-sm hover:bg-[#1e40af] transition-colors"
            >
              <PlusCircle className="w-4 h-4" />
              حجز جديد
            </Link>
          )}
          {(role === 'admin' || role === 'accountant') && (
            <Link
              to="/finance"
              className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs sm:text-sm font-semibold text-white bg-[#d97706] rounded-lg shadow-sm hover:bg-[#b45309] transition-colors"
            >
              <Receipt className="w-4 h-4" />
              سند جديد
            </Link>
          )}
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Today Bookings */}
        <Card className="border-r-4 border-r-[#1e3a8a]">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-xs font-semibold text-slate-500">
                حجوزات اليوم
              </CardTitle>
              <CalendarCheck className="w-4 h-4 text-[#1e3a8a]" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-black text-slate-900">
              {summary?.today_bookings_count || 0}
            </div>
            <p className="text-xs text-slate-500 mt-1">
              مبيعات اليوم: <span className="font-semibold text-slate-800">{Number(summary?.today_sales || 0).toLocaleString()} YER</span>
            </p>
          </CardContent>
        </Card>

        {/* Card 2: Month Bookings / Sales */}
        <Card className="border-r-4 border-r-sky-500">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-xs font-semibold text-slate-500">
                حجوزات الشهر الحالي
              </CardTitle>
              <TrendingUp className="w-4 h-4 text-sky-500" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-black text-slate-900">
              {summary?.month_bookings_count || 0}
            </div>
            <p className="text-xs text-slate-500 mt-1">
              إجمالي مبيعات الشهر: <span className="font-semibold text-slate-800">{Number(summary?.month_sales || summary?.total_sales || 0).toLocaleString()} YER</span>
            </p>
          </CardContent>
        </Card>

        {/* Card 3: Total Bookings (or Gross Profit for Admin/Accountant) */}
        {!isEmployee ? (
          <Card className="border-r-4 border-r-emerald-500">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-xs font-semibold text-slate-500">
                  إجمالي الربح الإجمالي
                </CardTitle>
                <ArrowUpRight className="w-4 h-4 text-emerald-600" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-black text-emerald-600">
                {Number(summary?.gross_profit || 0).toLocaleString()} YER
              </div>
              <p className="text-xs text-slate-500 mt-1">
                صافي الربح: <span className="font-semibold text-slate-800">{Number(summary?.net_profit || 0).toLocaleString()} YER</span>
              </p>
            </CardContent>
          </Card>
        ) : (
          <Card className="border-r-4 border-r-emerald-500">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-xs font-semibold text-slate-500">
                  إجمالي حجوزاتي
                </CardTitle>
                <CalendarCheck className="w-4 h-4 text-emerald-600" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-black text-slate-900">
                {summary?.total_bookings_count || 0}
              </div>
              <p className="text-xs text-slate-500 mt-1">العمليات المعتمدة المنفذة</p>
            </CardContent>
          </Card>
        )}

        {/* Card 4: Expenses / Customers */}
        {!isEmployee ? (
          <Card className="border-r-4 border-r-rose-500">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-xs font-semibold text-slate-500">
                  إجمالي المصروفات
                </CardTitle>
                <ArrowDownRight className="w-4 h-4 text-rose-500" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-black text-rose-600">
                {Number(summary?.total_expenses || 0).toLocaleString()} YER
              </div>
              <p className="text-xs text-slate-500 mt-1">
                العملاء المسجلون: <span className="font-semibold text-slate-800">{summary?.customers_count || 0}</span>
              </p>
            </CardContent>
          </Card>
        ) : (
          <Card className="border-r-4 border-r-amber-500">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-xs font-semibold text-slate-500">
                  إجمالي المبيعات
                </CardTitle>
                <CreditCard className="w-4 h-4 text-amber-500" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-black text-slate-900">
                {Number(summary?.total_sales || summary?.month_sales || 0).toLocaleString()} YER
              </div>
              <p className="text-xs text-slate-500 mt-1">قيمة الحجوزات الصادرة</p>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Alerts Section */}
      {alerts.length > 0 && (
        <div className="p-4 rounded-xl bg-amber-50/80 border border-amber-200">
          <div className="flex items-center gap-2 text-amber-900 font-bold text-sm mb-2">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
            <span>تنبيهات هامة تستوجب المتابعة ({alerts.length})</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-2">
            {alerts.slice(0, 6).map((alert, idx) => (
              <div
                key={idx}
                className="p-3 bg-white rounded-lg border border-amber-100 shadow-2xs flex items-start justify-between gap-2 text-xs"
              >
                <div>
                  <p className="font-bold text-slate-800">{alert.title}</p>
                  <p className="text-slate-500 mt-0.5">{alert.description}</p>
                  {alert.whatsapp_url && (
                    <a
                      href={alert.whatsapp_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 mt-1.5 px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200 font-semibold hover:bg-emerald-100 transition-colors"
                    >
                      تذكير واتساب
                    </a>
                  )}
                </div>
                <span className="px-2 py-0.5 rounded-full font-semibold bg-amber-100 text-amber-800 shrink-0 mr-2">
                  {alert.type === 'debt' ? 'مديونية' : alert.type === 'departure' ? 'رحلة قريبة' : 'جواز'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Charts Section (Admin & Accountant get Sales/Expenses, Employee gets volume trends) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base font-bold text-slate-800">
              {isEmployee ? 'حجم المبيعات الشهرية' : 'مقارنة المبيعات والمصروفات'}
            </CardTitle>
          </CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={monthlyChartData} margin={{ top: 10, right: 10, left: 10, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} tickLine={false} />
                <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} tickFormatter={(v) => `${v / 1000}k`} />
                <Tooltip
                  formatter={(value: any) => [`${Number(value).toLocaleString()} YER`, '']}
                  contentStyle={{ backgroundColor: '#ffffff', borderRadius: '8px', border: '1px solid #e2e8f0' }}
                />
                <Bar dataKey="sales" name="المبيعات" fill="#1e3a8a" radius={[4, 4, 0, 0]} />
                {!isEmployee && (
                  <Bar dataKey="expenses" name="المصروفات" fill="#dc2626" radius={[4, 4, 0, 0]} />
                )}
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base font-bold text-slate-800">
              توزيع الحجوزات حسب الخدمة
            </CardTitle>
          </CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={servicesDistribution}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {servicesDistribution.map((entry: any, index: number) => (
                    <Cell key={`cell-${index}`} fill={SERVICE_COLORS[index % SERVICE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(value: any) => [`${value} حجز`, 'العدد الفعلي']} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

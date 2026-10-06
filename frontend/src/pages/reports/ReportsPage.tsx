import React, { useState, useEffect } from 'react';
import {
  BarChart3,
  FileSpreadsheet,
  FileText,
  Filter,
  Calendar,
  Download,
  TrendingUp,
  CreditCard,
  Building,
  Users,
  DollarSign,
  PieChart,
} from 'lucide-react';
import api from '../../services/api';
import { useAuthStore } from '../../context/authStore';
import { useUIStore } from '../../context/uiStore';
import type { ReportFilter, ReportSummary, BookingType } from '../../types';
import { Card, CardHeader, CardTitle, CardContent } from '../../components/common/Card';
import { Spinner } from '../../components/common/Spinner';
import { EmptyState } from '../../components/common/EmptyState';
import { Button } from '../../components/common/Button';

interface ReportTab {
  id: ReportFilter['report_type'];
  title: string;
  description: string;
  icon: React.ReactNode;
}

const ALL_REPORTS: ReportTab[] = [
  {
    id: 'bookings_detailed',
    title: 'تقرير الحجوزات التفصيلي',
    description: 'كشف مفصل بجميع عمليات الحجز والمسافرين والأسعار',
    icon: <BarChart3 className="w-4 h-4 text-blue-600" />,
  },
  {
    id: 'revenue',
    title: 'تقرير الإيرادات والمبيعات',
    description: 'تحليل المبيعات الإجمالية والمحصلة حسب الفترة',
    icon: <TrendingUp className="w-4 h-4 text-emerald-600" />,
  },
  {
    id: 'expenses',
    title: 'تقرير المصروفات والنفقات',
    description: 'تفاصيل وبنود المصروفات الإدارية والتشغيلية',
    icon: <CreditCard className="w-4 h-4 text-rose-600" />,
  },
  {
    id: 'profit_loss',
    title: 'تقرير الأرباح والخسائر',
    description: 'مقارنة المبيعات والتكاليف والمصروفات وصافي الربح',
    icon: <DollarSign className="w-4 h-4 text-amber-600" />,
  },
  {
    id: 'debts',
    title: 'تقرير المديونيات والمستحقات',
    description: 'أرصدة العملاء المدينة والموردين الدائنة',
    icon: <Building className="w-4 h-4 text-purple-600" />,
  },
  {
    id: 'employee_performance',
    title: 'تقرير أداء الموظفين',
    description: 'إحصائيات المبيعات وحجم الحجوزات المنجزة لكل موظف',
    icon: <Users className="w-4 h-4 text-sky-600" />,
  },
  {
    id: 'cash_flow',
    title: 'تقرير التدفق النقدي',
    description: 'حركة المقبوضات والمدفوعات وصافي التدفق النقدي',
    icon: <PieChart className="w-4 h-4 text-indigo-600" />,
  },
];

export function ReportsPage() {
  const { role, user } = useAuthStore();
  const addToast = useUIStore((state) => state.addToast);
  const isEmployee = role === 'employee';

  // Available reports based on role (§3: employee only gets bookings_detailed)
  const availableReports = isEmployee
    ? ALL_REPORTS.filter((r) => r.id === 'bookings_detailed')
    : ALL_REPORTS;

  const [activeReport, setActiveReport] = useState<ReportFilter['report_type']>('bookings_detailed');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [serviceType, setServiceType] = useState<string>('all');

  const [reportData, setReportData] = useState<ReportSummary | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isExportingExcel, setIsExportingExcel] = useState(false);
  const [isExportingPdf, setIsExportingPdf] = useState(false);

  const generateReport = async () => {
    setIsLoading(true);
    try {
      const payload: ReportFilter = {
        report_type: activeReport,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        service_type: serviceType !== 'all' ? (serviceType as BookingType) : undefined,
      };

      const res = await api.post('/reports/generate', payload);
      setReportData(res.data);
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'فشل توليد التقرير';
      addToast(msg, 'error');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    generateReport();
  }, [activeReport, serviceType]);

  const handleExport = async (format: 'excel' | 'pdf') => {
    if (format === 'excel') setIsExportingExcel(true);
    else setIsExportingPdf(true);

    try {
      const payload: ReportFilter = {
        report_type: activeReport,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        service_type: serviceType !== 'all' ? (serviceType as BookingType) : undefined,
      };

      const endpoint = format === 'excel' ? '/reports/export/excel' : '/reports/export/pdf';
      const res = await api.post(endpoint, payload, { responseType: 'blob' });

      const blob = new Blob([res.data]);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute(
        'download',
        `report-${activeReport}-${new Date().toISOString().split('T')[0]}.${
          format === 'excel' ? 'xlsx' : 'pdf'
        }`
      );
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      addToast(`تم تحميل التقرير بصيغة ${format.toUpperCase()} بنجاح`, 'success');
    } catch (err: any) {
      addToast('فشل تصدير التقرير', 'error');
    } finally {
      if (format === 'excel') setIsExportingExcel(false);
      else setIsExportingPdf(false);
    }
  };

  const rows = reportData?.rows || [];
  const columns = rows.length > 0 ? Object.keys(rows[0]) : [];

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900">التقارير التحليلية والمالية</h1>
          <p className="text-sm text-slate-500">
            {isEmployee
              ? 'تقرير الحجوزات الخاص بك مع إمكانية التصدير والفرز'
              : 'كشوفات تفصيلية شاملة مع خيارات التصدير إلى Excel و PDF'}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleExport('excel')}
            isLoading={isExportingExcel}
            icon={<FileSpreadsheet className="w-4 h-4 text-emerald-600" />}
          >
            تصدير Excel
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleExport('pdf')}
            isLoading={isExportingPdf}
            icon={<FileText className="w-4 h-4 text-rose-600" />}
          >
            تصدير PDF
          </Button>
        </div>
      </div>

      {/* Reports Selection Tabs */}
      {!isEmployee && (
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2">
          {availableReports.map((r) => (
            <button
              key={r.id}
              onClick={() => setActiveReport(r.id)}
              className={`p-3 rounded-xl border text-right transition-all flex flex-col justify-between ${
                activeReport === r.id
                  ? 'border-[#1e3a8a] bg-blue-50/70 shadow-xs'
                  : 'border-slate-200 bg-white hover:bg-slate-50'
              }`}
            >
              <div className="mb-2">{r.icon}</div>
              <p
                className={`text-xs font-bold leading-tight ${
                  activeReport === r.id ? 'text-[#1e3a8a]' : 'text-slate-800'
                }`}
              >
                {r.title}
              </p>
            </button>
          ))}
        </div>
      )}

      {/* Filter Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-4 bg-white rounded-2xl border border-slate-200 shadow-2xs">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">من تاريخ:</span>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="rounded-xl border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#1e3a8a]"
            />
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">إلى تاريخ:</span>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="rounded-xl border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#1e3a8a]"
            />
          </div>

          {activeReport === 'bookings_detailed' && (
            <select
              value={serviceType}
              onChange={(e) => setServiceType(e.target.value)}
              className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#1e3a8a]"
            >
              <option value="all">جميع الخدمات</option>
              <option value="flight">طيران (FL)</option>
              <option value="transport">نقل بري (TR)</option>
              <option value="visa">تأشيرات (VI)</option>
              <option value="passport">جوازات (PA)</option>
              <option value="parcel">طرود (PR)</option>
            </select>
          )}

          <Button variant="primary" size="sm" onClick={generateReport}>
            عرض التقرير
          </Button>
        </div>
      </div>

      {/* Report Summary Cards */}
      {reportData && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Card className="border-r-4 border-r-[#1e3a8a]">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-semibold text-slate-500">الفترة الزمنية</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-base font-bold text-slate-800">{reportData.period}</p>
            </CardContent>
          </Card>

          <Card className="border-r-4 border-r-emerald-600">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-semibold text-slate-500">عدد العمليات</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-black text-slate-900">{reportData.total_count}</p>
            </CardContent>
          </Card>

          <Card className="border-r-4 border-r-amber-500">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-semibold text-slate-500">المبلغ الإجمالي</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-black text-emerald-700">
                {Number(reportData.total_amount).toLocaleString()} YER
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Report Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-2xs overflow-hidden">
        {isLoading ? (
          <div className="py-16">
            <Spinner size="lg" label="جارٍ تجهيز بيانات التقرير..." />
          </div>
        ) : rows.length === 0 ? (
          <EmptyState
            title="لا توجد بيانات لهذا التقرير"
            description="جرّب تعديل نطاق التاريخ أو فلاتر البحث للحصول على نتائج."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-right text-xs sm:text-sm">
              <thead className="bg-slate-50 text-slate-600 border-b border-slate-200 font-semibold">
                <tr>
                  {columns.map((col) => (
                    <th key={col} className="px-4 py-3 whitespace-nowrap">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((row, idx) => (
                  <tr key={idx} className="hover:bg-slate-50/80 transition-colors">
                    {columns.map((col) => (
                      <td key={col} className="px-4 py-3 whitespace-nowrap text-slate-700">
                        {typeof row[col] === 'number'
                          ? row[col].toLocaleString()
                          : String(row[col] || '--')}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

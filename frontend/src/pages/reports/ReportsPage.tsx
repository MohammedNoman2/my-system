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
  BookOpen
} from 'lucide-react';
import api from '../../services/api';
import { useAuthStore } from '../../context/authStore';
import { useUIStore } from '../../context/uiStore';
import type { ReportFilter, ReportSummary, BookingType } from '../../types';
import { Card, CardHeader, CardTitle, CardContent } from '../../components/common/Card';
import { Spinner } from '../../components/common/Spinner';
import { EmptyState } from '../../components/common/EmptyState';
import { Button } from '../../components/common/Button';
import { Input } from '../../components/common/Input';

interface ReportTab {
  id: any;
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
  {
    id: 'ledger',
    title: 'كشف حساب',
    description: 'كشف حساب مالي تفصيلي للعملاء والموردين متعدد العملات',
    icon: <BookOpen className="w-4 h-4 text-slate-600" />,
  }
];

export function ReportsPage() {
  const { role, user } = useAuthStore();
  const addToast = useUIStore((state) => state.addToast);
  const isEmployee = role === 'employee';

  const availableReports = isEmployee
    ? ALL_REPORTS.filter((r) => r.id === 'bookings_detailed')
    : ALL_REPORTS;

  const [activeReport, setActiveReport] = useState<any>('bookings_detailed');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [serviceType, setServiceType] = useState<string>('all');

  const [reportData, setReportData] = useState<ReportSummary | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isExportingExcel, setIsExportingExcel] = useState(false);
  const [isExportingPdf, setIsExportingPdf] = useState(false);

  // Ledger specific state
  const [ledgerEntityType, setLedgerEntityType] = useState<'customer'|'supplier'>('customer');
  const [ledgerEntities, setLedgerEntities] = useState<any[]>([]);
  const [selectedEntityId, setSelectedEntityId] = useState<number | null>(null);
  const [ledgerData, setLedgerData] = useState<any>(null);
  const [isLedgerLoading, setIsLedgerLoading] = useState(false);
  const [ledgerSelectedCurrency, setLedgerSelectedCurrency] = useState<string>('all');

  useEffect(() => {
    if (activeReport === 'ledger') {
      const fetchEntities = async () => {
        try {
          const res = await api.get(`/${ledgerEntityType}s/`);
          setLedgerEntities(res.data);
          if (res.data.length > 0) {
              setSelectedEntityId(res.data[0].id);
          } else {
              setSelectedEntityId(null);
          }
        } catch (err) {
          console.error(err);
        }
      };
      fetchEntities();
    }
  }, [activeReport, ledgerEntityType]);

  const generateReport = async () => {
    if (activeReport === 'ledger') {
        if (!selectedEntityId) {
            addToast('الرجاء اختيار الطرف', 'error');
            return;
        }
        setIsLedgerLoading(true);
        try {
            const endpoint = `/finance/ledger/v3/${ledgerEntityType}/${selectedEntityId}`;
            const params = new URLSearchParams();
            if (startDate) params.append('from_date', startDate);
            if (endDate) params.append('to_date', endDate);
            
            const res = await api.get(`${endpoint}?${params.toString()}`);
            setLedgerData(res.data);
        } catch (err: any) {
            addToast('فشل تحميل كشف الحساب', 'error');
        } finally {
            setIsLedgerLoading(false);
        }
        return;
    }

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
    if (activeReport !== 'ledger') {
        generateReport();
    } else {
        setLedgerData(null);
    }
  }, [activeReport, serviceType]);

  const handleExport = async (format: 'excel' | 'pdf') => {
    if (format === 'excel') setIsExportingExcel(true);
    else setIsExportingPdf(true);

    if (activeReport === 'ledger') {
        if (!selectedEntityId) {
            addToast('الرجاء اختيار الطرف أولاً', 'error');
            if (format === 'excel') setIsExportingExcel(false);
            else setIsExportingPdf(false);
            return;
        }
        try {
            const endpoint = `/finance/ledger/v3/${ledgerEntityType}/${selectedEntityId}/export`;
            const params = new URLSearchParams({ format });
            if (startDate) params.append('from_date', startDate);
            if (endDate) params.append('to_date', endDate);
            
            const res = await api.get(`${endpoint}?${params.toString()}`, { responseType: 'blob' });
            
            const contentType = String(res.headers['content-type'] || "");
            if (contentType.includes("text/html")) {
                const text = await res.data.text();
                const printWindow = window.open("", "_blank");
                if (printWindow) {
                    printWindow.document.write(text);
                    printWindow.document.close();
                    printWindow.focus();
                }
            } else {
                const disposition = res.headers['content-disposition'];
                let filename = `ledger-${ledgerEntityType}-${selectedEntityId}.${format === 'excel' ? 'xlsx' : 'pdf'}`;
                if (disposition && disposition.indexOf('filename=') !== -1) {
                    filename = disposition.split('filename=')[1].replace(/["']/g, "");
                }
                const url = window.URL.createObjectURL(new Blob([res.data]));
                const link = document.createElement('a');
                link.href = url;
                link.setAttribute('download', filename);
                document.body.appendChild(link);
                link.click();
                link.remove();
                window.URL.revokeObjectURL(url);
                addToast(`تم تصدير كشف الحساب بنجاح`, 'success');
            }
        } catch (err: any) {
            console.error('Export failed', err);
            let errorMsg = err?.response?.status === 403 ? 'عذراً، لا تملك الصلاحية' : 'فشل تصدير الكشف';
            if (err?.response?.data instanceof Blob) {
                try {
                    const text = await err.response.data.text();
                    const json = JSON.parse(text);
                    if (json.detail) errorMsg = json.detail;
                } catch(e) {}
            }
            addToast(errorMsg, 'error');
        } finally {
            if (format === 'excel') setIsExportingExcel(false);
            else setIsExportingPdf(false);
        }
        return;
    }

    try {
      const payload: ReportFilter = {
        report_type: activeReport,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        service_type: serviceType !== 'all' ? (serviceType as BookingType) : undefined,
      };

      const endpoint = format === 'excel' ? '/reports/export/excel' : '/reports/export/pdf';
      const res = await api.post(endpoint, payload, { responseType: 'blob' });

      const contentType = String(res.headers['content-type'] || "");
      if (contentType.includes("text/html")) {
          const text = await res.data.text();
          const printWindow = window.open("", "_blank");
          if (printWindow) {
              printWindow.document.write(text);
              printWindow.document.close();
              printWindow.focus();
          }
      } else {
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
      }
    } catch (err: any) {
      console.error('Export failed', err);
      let errorMsg = err?.response?.status === 403 ? 'عذراً، لا تملك الصلاحية' : 'فشل تصدير التقرير';
      if (err?.response?.data instanceof Blob) {
          try {
              const text = await err.response.data.text();
              const json = JSON.parse(text);
              if (json.detail) errorMsg = json.detail;
          } catch(e) {}
      }
      addToast(errorMsg, 'error');
    } finally {
      if (format === 'excel') setIsExportingExcel(false);
      else setIsExportingPdf(false);
    }
  };

  const rows = reportData?.rows || [];
  const columns = rows.length > 0 ? Object.keys(rows[0]) : [];

  const renderLedgerTable = (curr: string, ledger: any) => (
    <div key={curr} className="mb-6 border border-slate-200 rounded-xl overflow-hidden bg-white shadow-2xs">
        <div className="p-3 bg-slate-50 border-b border-slate-200 flex flex-wrap gap-2 justify-between items-center">
            <h3 className="font-bold text-slate-800">كشف حساب ({curr})</h3>
            <div className="flex gap-4 text-xs font-semibold">
                <span>افتتاحي: {Number(ledger.opening_balance).toLocaleString()}</span>
                <span className="text-red-600">مدين: {Number(ledger.total_debit).toLocaleString()}</span>
                <span className="text-emerald-600">دائن: {Number(ledger.total_credit).toLocaleString()}</span>
                <span className="text-blue-700">ختامي: {Number(ledger.closing_balance).toLocaleString()}</span>
            </div>
        </div>
        {ledger.entries.length === 0 ? (
            <div className="p-4 text-center text-slate-500">لا توجد حركات في هذه الفترة</div>
        ) : (
            <div className="overflow-x-auto max-h-[40vh]">
              <table className="w-full text-right text-xs sm:text-sm">
                <thead className="bg-slate-50 text-slate-600 border-b border-slate-200 font-semibold sticky top-0">
                  <tr>
                    <th className="px-3.5 py-3">التاريخ</th>
                    <th className="px-3.5 py-3">رقم المرجع</th>
                    <th className="px-3.5 py-3">البيان / الوصف</th>
                    <th className="px-3.5 py-3 text-red-700">مدين (+)</th>
                    <th className="px-3.5 py-3 text-emerald-700">دائن (-)</th>
                    <th className="px-3.5 py-3 font-bold">الرصيد التراكمي</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {ledger.entries.map((item: any, idx: number) => (
                    <tr key={idx} className="hover:bg-slate-50/80 transition-colors">
                      <td className="px-3.5 py-2.5 text-slate-600 whitespace-nowrap">
                        {item.date}
                      </td>
                      <td className="px-3.5 py-2.5 font-mono font-bold text-[#1e3a8a]">
                        {item.reference_id || '--'}
                      </td>
                      <td className="px-3.5 py-2.5 font-medium text-slate-800">
                        {item.description}
                      </td>
                      <td className="px-3.5 py-2.5 font-semibold text-red-600">
                        {Number(item.debit) > 0 ? Number(item.debit).toLocaleString() : '--'}
                      </td>
                      <td className="px-3.5 py-2.5 font-semibold text-emerald-600">
                        {Number(item.credit) > 0 ? Number(item.credit).toLocaleString() : '--'}
                      </td>
                      <td className="px-3.5 py-2.5 font-bold font-mono text-slate-900">
                        {Number(item.balance).toLocaleString()} {curr}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
        )}
    </div>
  );

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
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2">
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
          
          {activeReport === 'ledger' && (
             <select
               value={ledgerEntityType}
               onChange={(e) => setLedgerEntityType(e.target.value as 'customer'|'supplier')}
               className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#1e3a8a]"
             >
               <option value="customer">عميل</option>
               <option value="supplier">مورد</option>
             </select>
          )}

          {activeReport === 'ledger' && (
             <select
               value={selectedEntityId || ''}
               onChange={(e) => setSelectedEntityId(Number(e.target.value))}
               className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#1e3a8a]"
             >
               {ledgerEntities.map(ent => (
                   <option key={ent.id} value={ent.id}>{ent.name}</option>
               ))}
             </select>
          )}

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

      {activeReport === 'ledger' ? (
          <div>
            {isLedgerLoading ? (
                <div className="py-16 bg-white rounded-2xl border border-slate-200 shadow-2xs">
                  <Spinner size="lg" label="جارٍ تجهيز كشف الحساب..." />
                </div>
            ) : ledgerData ? (
                <div className="space-y-4">
                    {/* Closing Balances Cards */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {['YER', 'SAR', 'USD'].map(curr => (
                            <div key={curr} className="p-4 bg-white border border-slate-200 rounded-lg shadow-sm text-center">
                                <p className="text-sm text-slate-500">الرصيد الختامي ({curr})</p>
                                <p className={`text-xl font-bold ${Number(ledgerData.ledgers[curr]?.closing_balance) > 0 ? 'text-red-600' : Number(ledgerData.ledgers[curr]?.closing_balance) < 0 ? 'text-emerald-600' : 'text-slate-800'}`}>
                                    {ledgerData.ledgers[curr] ? Number(ledgerData.ledgers[curr].closing_balance).toLocaleString() : '0.00'}
                                </p>
                            </div>
                        ))}
                    </div>
                    
                    {/* Currency Tabs */}
                    <div className="flex border-b border-slate-200 gap-2 mb-4 bg-white p-2 rounded-t-lg">
                        <button
                            onClick={() => setLedgerSelectedCurrency('all')}
                            className={`py-2 px-4 text-sm font-bold border-b-2 transition-colors ${
                              ledgerSelectedCurrency === 'all' ? 'border-blue-600 text-blue-700 bg-blue-50/50' : 'border-transparent text-slate-500 hover:text-slate-700 hover:bg-slate-50'
                            }`}
                        >
                            الكل
                        </button>
                        {Object.keys(ledgerData.ledgers).filter(c => ledgerData.ledgers[c].entries.length > 0 || ledgerData.ledgers[c].opening_balance !== 0).map((curr) => (
                          <button
                            key={curr}
                            onClick={() => setLedgerSelectedCurrency(curr)}
                            className={`py-2 px-4 text-sm font-bold border-b-2 transition-colors ${
                              ledgerSelectedCurrency === curr ? 'border-blue-600 text-blue-700 bg-blue-50/50' : 'border-transparent text-slate-500 hover:text-slate-700 hover:bg-slate-50'
                            }`}
                          >
                            {curr}
                          </button>
                        ))}
                    </div>
                    
                    {/* Ledger Tables */}
                    {ledgerSelectedCurrency === 'all' ? (
                        Object.keys(ledgerData.ledgers).filter(c => ledgerData.ledgers[c].entries.length > 0 || ledgerData.ledgers[c].opening_balance !== 0).length > 0 ? Object.keys(ledgerData.ledgers).filter(c => ledgerData.ledgers[c].entries.length > 0 || ledgerData.ledgers[c].opening_balance !== 0).map(curr => renderLedgerTable(curr, ledgerData.ledgers[curr])) : (
                            <EmptyState title="لا توجد حركات" description="لا توجد عمليات مالية مسجلة" />
                        )
                    ) : (
                        ledgerData.ledgers[ledgerSelectedCurrency] ? renderLedgerTable(ledgerSelectedCurrency, ledgerData.ledgers[ledgerSelectedCurrency]) : (
                            <EmptyState title="لا توجد حركات" description={`لا توجد عمليات مسجلة بعملة ${ledgerSelectedCurrency}`} />
                        )
                    )}
                </div>
            ) : (
                <EmptyState title="كشف الحساب" description="الرجاء اختيار الطرف والضغط على عرض التقرير" />
            )}
          </div>
      ) : (
          <>
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
          </>
      )}
    </div>
  );
}

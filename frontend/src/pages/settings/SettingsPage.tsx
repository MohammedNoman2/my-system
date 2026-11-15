import React, { useState, useEffect, useRef } from 'react';
import {
  Building2,
  DollarSign,
  Users,
  ShieldCheck,
  Save,
  PlusCircle,
  RefreshCw,
  CheckCircle2,
  Lock,
  Upload,
  Image as ImageIcon,
  Pencil,
  Power,
  KeyRound,
} from 'lucide-react';
import api from '../../services/api';
import { useSettingsStore } from '../../context/settingsStore';
import { useUIStore } from '../../context/uiStore';
import type { OfficeSettings, ExchangeRate, User } from '../../types';
import { Card, CardHeader, CardTitle, CardContent } from '../../components/common/Card';
import { Spinner } from '../../components/common/Spinner';
import { Modal } from '../../components/common/Modal';
import { Input } from '../../components/common/Input';
import { Select } from '../../components/common/Select';
import { Button } from '../../components/common/Button';

type SettingsTab = 'office' | 'rates' | 'users' | 'audit';

export function SettingsPage() {
  const [activeTab, setActiveTab] = useState<SettingsTab>('office');
  const { office, fetchOfficeSettings, updateOfficeSettings, uploadLogo } = useSettingsStore();
  const addToast = useUIStore((state) => state.addToast);
  const logoInputRef = useRef<HTMLInputElement>(null);
  const [isUploadingLogo, setIsUploadingLogo] = useState(false);

  // Office form state
  const [officeForm, setOfficeForm] = useState<Partial<OfficeSettings>>({});
  const [isSavingOffice, setIsSavingOffice] = useState(false);

  // Exchange rates state
  const [rates, setRates] = useState<ExchangeRate[]>([]);
  const [isLoadingRates, setIsLoadingRates] = useState(false);
  const [isRateModalOpen, setIsRateModalOpen] = useState(false);
  const [rateForm, setRateForm] = useState({ from_currency: 'USD', to_currency: 'YER', rate: 530 });

  // Users state
  const [users, setUsers] = useState<User[]>([]);
  const [isLoadingUsers, setIsLoadingUsers] = useState(false);
  const [isUserModalOpen, setIsUserModalOpen] = useState(false);
  const [userForm, setUserForm] = useState({
    username: '',
    password: '',
    full_name: '',
    role: 'employee' as 'admin' | 'employee' | 'accountant',
    email: '',
    phone_number: '',
    is_active: true,
  });

  // User Edit/Actions state
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editForm, setEditForm] = useState({ full_name: '', phone_number: '', role: 'employee' as 'admin' | 'employee' | 'accountant' });
  const [isResetModalOpen, setIsResetModalOpen] = useState(false);
  const [resetUserId, setResetUserId] = useState<number | null>(null);
  const [resetUsername, setResetUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isSubmittingAction, setIsSubmittingAction] = useState(false);

  // Audit logs state
  const [logs, setLogs] = useState<any[]>([]);
  const [isLoadingLogs, setIsLoadingLogs] = useState(false);

  useEffect(() => {
    fetchOfficeSettings();
  }, [fetchOfficeSettings]);

  useEffect(() => {
    if (office) {
      setOfficeForm({
        office_name: office.office_name,
        tagline: office.tagline,
        address: office.address,
        phone_numbers: office.phone_numbers,
        email: office.email,
        website: office.website,
        default_currency: office.default_currency,
        footer_text: office.footer_text,
      });
    }
  }, [office]);

  // Load Tab-specific data
  useEffect(() => {
    if (activeTab === 'rates') {
      fetchRates();
    } else if (activeTab === 'users') {
      fetchUsers();
    } else if (activeTab === 'audit') {
      fetchAuditLogs();
    }
  }, [activeTab]);

  const fetchRates = async () => {
    setIsLoadingRates(true);
    try {
      const res = await api.get('/settings/exchange-rates');
      setRates(res.data);
    } catch (err) {
      console.error('Failed to load rates', err);
    } finally {
      setIsLoadingRates(false);
    }
  };

  const fetchUsers = async () => {
    setIsLoadingUsers(true);
    try {
      const res = await api.get('/settings/users');
      setUsers(res.data);
    } catch (err) {
      console.error('Failed to load users', err);
    } finally {
      setIsLoadingUsers(false);
    }
  };

  const fetchAuditLogs = async () => {
    setIsLoadingLogs(true);
    try {
      const res = await api.get('/settings/audit-logs');
      setLogs(res.data);
    } catch (err) {
      console.error('Failed to load audit logs', err);
    } finally {
      setIsLoadingLogs(false);
    }
  };

  const handleLogoChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsUploadingLogo(true);
    try {
      await uploadLogo(file);
      addToast('تم رفع وتحديث شعار المكتب بنجاح', 'success');
    } catch (err: any) {
      addToast(err.message || 'فشل رفع الشعار', 'error');
    } finally {
      setIsUploadingLogo(false);
      if (logoInputRef.current) logoInputRef.current.value = '';
    }
  };

  const handleSaveOffice = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSavingOffice(true);
    try {
      await updateOfficeSettings(officeForm);
      addToast('تم حفظ وتحديث بيانات المكتب بنجاح', 'success');
    } catch (err: any) {
      addToast(err.message || 'فشل تحديث بيانات المكتب', 'error');
    } finally {
      setIsSavingOffice(false);
    }
  };

  const handleSaveRate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post('/settings/exchange-rates', rateForm);
      addToast('تم تحديث سعر الصرف بنجاح', 'success');
      setIsRateModalOpen(false);
      fetchRates();
    } catch (err: any) {
      addToast(err.response?.data?.detail || 'فشل تحديث سعر الصرف', 'error');
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post('/settings/users', userForm);
      addToast('تم إنشاء المستخدم بنجاح', 'success');
      setIsUserModalOpen(false);
      setUserForm({ username: '', password: '', full_name: '', role: 'employee', email: '', phone_number: '', is_active: true });
      fetchUsers();
    } catch (err: any) {
      addToast(err.response?.data?.detail || 'فشل إضافة المستخدم', 'error');
    }
  };

  const handleEditUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingUser) return;
    setIsSubmittingAction(true);
    try {
      await api.put(`/settings/users/${editingUser.id}`, editForm);
      addToast('تم تحديث بيانات المستخدم بنجاح', 'success');
      setIsEditModalOpen(false);
      fetchUsers();
    } catch (err: any) {
      addToast(err.response?.data?.detail || 'فشل تعديل بيانات المستخدم', 'error');
    } finally {
      setIsSubmittingAction(false);
    }
  };

  const handleToggleStatus = async (user: User) => {
    setIsSubmittingAction(true);
    try {
      const res = await api.patch(`/settings/users/${user.id}/status`);
      addToast(res.data.message, 'success');
      fetchUsers();
    } catch (err: any) {
      addToast(err.response?.data?.detail || 'فشل تغيير الحالة', 'error');
    } finally {
      setIsSubmittingAction(false);
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPassword || newPassword !== confirmPassword) {
      addToast('كلمتا المرور غير متطابقتين', 'error');
      return;
    }
    setIsSubmittingAction(true);
    try {
      await api.post(`/settings/users/${resetUserId}/reset-password`, { new_password: newPassword });
      addToast('تم إعادة تعيين كلمة المرور بنجاح', 'success');
      setIsResetModalOpen(false);
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: any) {
      addToast(err.response?.data?.detail || 'فشل إعادة التعيين', 'error');
    } finally {
      setIsSubmittingAction(false);
    }
  };

  const tabs = [
    { id: 'office', label: 'بيانات وهوية المكتب', icon: <Building2 className="w-4 h-4" /> },
    { id: 'rates', label: 'أسعار الصرف', icon: <DollarSign className="w-4 h-4" /> },
    { id: 'users', label: 'إدارة المستخدمين', icon: <Users className="w-4 h-4" /> },
    { id: 'audit', label: 'سجلات التدقيق والأمان', icon: <ShieldCheck className="w-4 h-4" /> },
  ];

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-black text-slate-900">إعدادات النظام والتحكم</h1>
          <p className="text-sm text-slate-500">
            تكوين بيانات وهوية المكتب، أسعار الصرف، والمستخدمين وسجلات النظام
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200 overflow-x-auto pb-1">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as SettingsTab)}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs sm:text-sm font-bold border-b-2 transition-all whitespace-nowrap ${
              activeTab === tab.id
                ? 'border-[#1e3a8a] text-[#1e3a8a]'
                : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            {tab.icon}
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Tab 1: Office Settings */}
      {activeTab === 'office' && (
        <div className="space-y-6">
          {/* Logo Branding Card */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <ImageIcon className="w-5 h-5 text-blue-600" />
                شعار المكتب والهوية البصرية الرسمية
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col sm:flex-row items-center gap-6 p-4 bg-slate-50 rounded-2xl border border-slate-200">
                <div className="w-24 h-24 rounded-2xl bg-gradient-to-tr from-[#1e3a8a] to-blue-600 flex items-center justify-center text-white font-black text-2xl shadow-md overflow-hidden shrink-0 border-2 border-white">
                  {office?.logo_data || office?.logo_image_url ? (
                    <img
                      src={office.logo_data || office.logo_image_url || ''}
                      alt="شعار المكتب"
                      className="w-full h-full object-contain p-1 bg-white/10"
                    />
                  ) : (
                    <span>ARP</span>
                  )}
                </div>

                <div className="flex-1 space-y-2 text-center sm:text-right">
                  <h4 className="text-sm font-bold text-slate-800">
                    شعار المنظومة والمطبوعات
                  </h4>
                  <p className="text-xs text-slate-500 max-w-xl">
                    يتم تضمين الشعار تلقائياً في واجهة الدخول، الشريط الجانبي للنظام، وسندات الحجز المطبوعة (A4 والحراري) بإطار عالي التباين ووضوح فائق.
                  </p>
                  <div className="pt-2 space-y-1.5">
                    <input
                      type="file"
                      ref={logoInputRef}
                      onChange={handleLogoChange}
                      accept="image/png,image/jpeg,image/webp"
                      className="hidden"
                    />
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      isLoading={isUploadingLogo}
                      onClick={() => logoInputRef.current?.click()}
                      icon={<Upload className="w-4 h-4" />}
                    >
                      رفع وتحديث الشعار
                    </Button>
                    <p className="text-[11px] text-slate-400">
                      الصيغ المسموحة: PNG, JPG, WEBP فقط (بحد أقصى 2 ميجابايت)
                    </p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Office Details Card */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">البيانات التعريفية للمكتب والترويسة</CardTitle>
            </CardHeader>
            <CardContent>
            <form onSubmit={handleSaveOffice} className="space-y-5">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Input
                  label="اسم المكتب الرسمي"
                  value={officeForm.office_name || ''}
                  onChange={(e) => setOfficeForm({ ...officeForm, office_name: e.target.value })}
                  required
                />

                <Input
                  label="الشعار الترويجي (Tagline)"
                  placeholder="للسفريات والسياحة والنقل البري والتخليص"
                  value={officeForm.tagline || ''}
                  onChange={(e) => setOfficeForm({ ...officeForm, tagline: e.target.value })}
                />

                <Input
                  label="العنوان والمقر الرئيسي"
                  value={officeForm.address || ''}
                  onChange={(e) => setOfficeForm({ ...officeForm, address: e.target.value })}
                />

                <Input
                  label="أرقام الهواتف والتواصل"
                  placeholder="778699440 - 771609217"
                  value={officeForm.phone_numbers || ''}
                  onChange={(e) => setOfficeForm({ ...officeForm, phone_numbers: e.target.value })}
                />

                <Input
                  label="البريد الإلكتروني الرسمي"
                  type="email"
                  value={officeForm.email || ''}
                  onChange={(e) => setOfficeForm({ ...officeForm, email: e.target.value })}
                />

                <Input
                  label="الموقع الإلكتروني"
                  value={officeForm.website || ''}
                  onChange={(e) => setOfficeForm({ ...officeForm, website: e.target.value })}
                />

                <Select
                  label="العملة الافتراضية للنظام"
                  value={officeForm.default_currency || 'YER'}
                  onChange={(e) => setOfficeForm({ ...officeForm, default_currency: e.target.value })}
                >
                  <option value="YER">ريال يمني (YER)</option>
                  <option value="SAR">ريال سعودي (SAR)</option>
                  <option value="USD">دولار أمريكي (USD)</option>
                </Select>

                <Input
                  label="نص التذييل للسندات المطبوعة"
                  value={officeForm.footer_text || ''}
                  onChange={(e) => setOfficeForm({ ...officeForm, footer_text: e.target.value })}
                />
              </div>

              <div className="flex justify-end pt-4 border-t border-slate-100">
                <Button
                  type="submit"
                  variant="primary"
                  isLoading={isSavingOffice}
                  icon={<Save className="w-4 h-4" />}
                >
                  حفظ التعديلات
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
      )}

      {/* Tab 2: Exchange Rates */}
      {activeTab === 'rates' && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">جدول أسعار صرف العملات المعتمدة</CardTitle>
            <Button
              variant="primary"
              size="sm"
              onClick={() => setIsRateModalOpen(true)}
              icon={<PlusCircle className="w-4 h-4" />}
            >
              تحديث / إضافة سعر صرف
            </Button>
          </CardHeader>
          <CardContent>
            {isLoadingRates ? (
              <div className="py-8"><Spinner size="md" /></div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-right text-xs sm:text-sm">
                  <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
                    <tr>
                      <th className="px-4 py-3">من عملة</th>
                      <th className="px-4 py-3">إلى عملة</th>
                      <th className="px-4 py-3">سعر التحويل المعتمد</th>
                      <th className="px-4 py-3">تاريخ آخر تحديث</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {rates.map((r) => (
                      <tr key={r.id}>
                        <td className="px-4 py-3 font-bold text-slate-800">{r.from_currency}</td>
                        <td className="px-4 py-3 font-bold text-slate-800">{r.to_currency}</td>
                        <td className="px-4 py-3 font-mono font-bold text-emerald-700">
                          {Number(r.rate).toLocaleString()}
                        </td>
                        <td className="px-4 py-3 text-slate-500">
                          {r.updated_at ? new Date(r.updated_at).toLocaleString('ar-EG') : 'تلقائي'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Tab 3: Users Management */}
      {activeTab === 'users' && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">المستخدمون وحسابات الموظفين</CardTitle>
            <Button
              variant="primary"
              size="sm"
              onClick={() => setIsUserModalOpen(true)}
              icon={<PlusCircle className="w-4 h-4" />}
            >
              إضافة مستخدم جديد
            </Button>
          </CardHeader>
          <CardContent>
            {isLoadingUsers ? (
              <div className="py-8"><Spinner size="md" /></div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-right text-xs sm:text-sm">
                  <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
                    <tr>
                      <th className="px-4 py-3">الاسم الكامل</th>
                      <th className="px-4 py-3">اسم المستخدم</th>
                      <th className="px-4 py-3">الدور والصلاحية</th>
                      <th className="px-4 py-3">رقم الهاتف</th>
                      <th className="px-4 py-3">الحالة</th>
                      <th className="px-4 py-3 text-center">الإجراءات</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {users.map((u) => (
                      <tr key={u.id} className="hover:bg-slate-50/60 transition-colors">
                        <td className="px-4 py-3 font-bold text-slate-800">{u.full_name}</td>
                        <td className="px-4 py-3 font-mono text-slate-600">{u.username}</td>
                        <td className="px-4 py-3">
                          <span
                            className={`px-2.5 py-0.5 rounded-full text-xs font-bold ${
                              u.role === 'admin'
                                ? 'bg-red-100 text-red-800'
                                : u.role === 'accountant'
                                ? 'bg-amber-100 text-amber-800'
                                : 'bg-blue-100 text-blue-800'
                            }`}
                          >
                            {u.role === 'admin' ? 'مدير نظام' : u.role === 'accountant' ? 'محاسب' : 'موظف حجز'}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-slate-600 font-mono">{u.phone_number || '--'}</td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-bold ${
                            u.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'
                          }`}>
                            <span className={`w-1.5 h-1.5 rounded-full ${u.is_active ? 'bg-emerald-500' : 'bg-slate-400'}`} />
                            {u.is_active ? 'نشط' : 'معطل'}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-1 justify-center">
                            <button
                              onClick={() => {
                                setEditingUser(u);
                                setEditForm({ full_name: u.full_name, phone_number: u.phone_number || '', role: u.role as any });
                                setIsEditModalOpen(true);
                              }}
                              className="p-1.5 rounded-lg text-blue-600 hover:bg-blue-50"
                              title="تعديل"
                            >
                              <Pencil className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={() => handleToggleStatus(u)}
                              className={`p-1.5 rounded-lg ${ u.is_active ? 'text-amber-600 hover:bg-amber-50' : 'text-emerald-600 hover:bg-emerald-50' }`}
                              title={u.is_active ? 'تعطيل' : 'تفعيل'}
                            >
                              <Power className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={() => { setResetUserId(u.id); setResetUsername(u.full_name); setNewPassword(''); setConfirmPassword(''); setIsResetModalOpen(true); }}
                              className="p-1.5 rounded-lg text-slate-600 hover:bg-slate-100"
                              title="إعادة كلمة المرور"
                            >
                              <KeyRound className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Tab 4: Audit Logs */}
      {activeTab === 'audit' && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">سجلات الرقابة والتدقيق الأمني (Audit Logs)</CardTitle>
            <button
              onClick={fetchAuditLogs}
              className="p-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-100"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </CardHeader>
          <CardContent>
            {isLoadingLogs ? (
              <div className="py-8"><Spinner size="md" /></div>
            ) : (
              <div className="overflow-x-auto max-h-[60vh]">
                <table className="w-full text-right text-xs sm:text-sm">
                  <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200 sticky top-0">
                    <tr>
                      <th className="px-4 py-3">التوقيت</th>
                      <th className="px-4 py-3">المستخدم</th>
                      <th className="px-4 py-3">نوع الإجراء</th>
                      <th className="px-4 py-3">الجدول / الكيان</th>
                      <th className="px-4 py-3">عنوان IP</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {logs.map((log) => (
                      <tr key={log.id} className="hover:bg-slate-50/80">
                        <td className="px-4 py-2.5 font-mono text-slate-500 whitespace-nowrap">
                          {log.timestamp ? new Date(log.timestamp).toLocaleString('ar-EG') : '--'}
                        </td>
                        <td className="px-4 py-2.5 font-semibold text-slate-800">
                          {log.username || 'النظام'}
                        </td>
                        <td className="px-4 py-2.5 font-bold text-[#1e3a8a]">{log.action}</td>
                        <td className="px-4 py-2.5 text-slate-600 font-mono">{log.table_name}</td>
                        <td className="px-4 py-2.5 font-mono text-slate-400">{log.ip_address || '--'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Upsert Rate Modal */}
      <Modal
        isOpen={isRateModalOpen}
        onClose={() => setIsRateModalOpen(false)}
        title="تحديث سعر الصرف"
        description="تحديد سعر صرف العملات الأجنبية مقابل العملة المحلية"
        size="sm"
      >
        <form onSubmit={handleSaveRate} className="space-y-4">
          <Select
            label="من عملة"
            value={rateForm.from_currency}
            onChange={(e) => setRateForm({ ...rateForm, from_currency: e.target.value })}
          >
            <option value="USD">دولار أمريكي (USD)</option>
            <option value="SAR">ريال سعودي (SAR)</option>
          </Select>

          <Select
            label="إلى عملة"
            value={rateForm.to_currency}
            onChange={(e) => setRateForm({ ...rateForm, to_currency: e.target.value })}
          >
            <option value="YER">ريال يمني (YER)</option>
            <option value="SAR">ريال سعودي (SAR)</option>
          </Select>

          <Input
            label="السعر"
            type="number"
            step="0.0001"
            value={rateForm.rate}
            onChange={(e) => setRateForm({ ...rateForm, rate: Number(e.target.value) })}
            required
          />

          <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
            <Button type="button" variant="ghost" onClick={() => setIsRateModalOpen(false)}>
              إلغاء
            </Button>
            <Button type="submit" variant="primary">
              حفظ السعر
            </Button>
          </div>
        </form>
      </Modal>

      {/* Add User Modal */}
      <Modal
        isOpen={isUserModalOpen}
        onClose={() => setIsUserModalOpen(false)}
        title="إضافة مستخدم جديد للنظام"
        description="إنشاء حساب لموظف أو محاسب مع تحديد صلاحيات الدور"
        size="md"
      >
        <form onSubmit={handleCreateUser} className="space-y-4">
          <Input
            label="الاسم الكامل"
            placeholder="الاسم الرباعي..."
            required
            value={userForm.full_name}
            onChange={(e) => setUserForm({ ...userForm, full_name: e.target.value })}
          />

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label="اسم المستخدم (لتسجيل الدخول)"
              placeholder="username"
              required
              value={userForm.username}
              onChange={(e) => setUserForm({ ...userForm, username: e.target.value })}
            />

            <Input
              label="كلمة المرور"
              type="password"
              placeholder="••••••••"
              required
              value={userForm.password}
              onChange={(e) => setUserForm({ ...userForm, password: e.target.value })}
            />

            <Select
              label="الدور والصلاحية"
              value={userForm.role}
              onChange={(e) => setUserForm({ ...userForm, role: e.target.value as any })}
            >
              <option value="employee">موظف حجوزات (Employee)</option>
              <option value="accountant">محاسب مالي (Accountant)</option>
              <option value="admin">مدير نظام كامل (Admin)</option>
            </Select>

            <Input
              label="رقم الهاتف"
              value={userForm.phone_number}
              onChange={(e) => setUserForm({ ...userForm, phone_number: e.target.value })}
            />
          </div>

          <Input
            label="البريد الإلكتروني"
            type="email"
            value={userForm.email}
            onChange={(e) => setUserForm({ ...userForm, email: e.target.value })}
          />

          <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
            <Button type="button" variant="ghost" onClick={() => setIsUserModalOpen(false)}>
              إلغاء
            </Button>
            <Button type="submit" variant="primary">
              إنشاء الحساب
            </Button>
          </div>
        </form>
      </Modal>

      {/* Edit User Modal */}
      <Modal
        isOpen={isEditModalOpen}
        onClose={() => setIsEditModalOpen(false)}
        title={`تعديل بيانات: ${editingUser?.full_name || ''}`}
        description="تعديل الاسم الكامل والدور وبيانات التواصل"
        size="sm"
      >
        <form onSubmit={handleEditUser} className="space-y-4">
          <Input
            label="الاسم الكامل"
            required
            value={editForm.full_name}
            onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })}
          />
          <Select
            label="الدور والصلاحية"
            value={editForm.role}
            onChange={(e) => setEditForm({ ...editForm, role: e.target.value as any })}
          >
            <option value="employee">موظف حجوزات (Employee)</option>
            <option value="accountant">محاسب مالي (Accountant)</option>
            <option value="admin">مدير نظام كامل (Admin)</option>
          </Select>
          <Input
            label="رقم الهاتف"
            value={editForm.phone_number}
            onChange={(e) => setEditForm({ ...editForm, phone_number: e.target.value })}
          />
          <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
            <Button type="button" variant="ghost" onClick={() => setIsEditModalOpen(false)}>إلغاء</Button>
            <Button type="submit" variant="primary" isLoading={isSubmittingAction}>حفظ التعديلات</Button>
          </div>
        </form>
      </Modal>

      {/* Reset Password Modal */}
      <Modal
        isOpen={isResetModalOpen}
        onClose={() => setIsResetModalOpen(false)}
        title={`إعادة تعيين كلمة مرور: ${resetUsername}`}
        description="أدخل كلمة المرور الجديدة وتأكيدها"
        size="sm"
      >
        <form onSubmit={handleResetPassword} className="space-y-4">
          <Input
            label="كلمة المرور الجديدة"
            type="password"
            placeholder="••••••••"
            required
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
          />
          <Input
            label="تأكيد كلمة المرور"
            type="password"
            placeholder="••••••••"
            required
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
          />
          {confirmPassword && newPassword !== confirmPassword && (
            <p className="text-xs text-red-600 font-bold">⚠️ كلمتا المرور غير متطابقتين</p>
          )}
          <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
            <Button type="button" variant="ghost" onClick={() => setIsResetModalOpen(false)}>إلغاء</Button>
            <Button type="submit" variant="primary" isLoading={isSubmittingAction}>تعيين كلمة المرور</Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

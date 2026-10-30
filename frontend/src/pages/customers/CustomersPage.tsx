import React, { useState, useEffect } from 'react';
import {
  Users,
  UserPlus,
  Search,
  RefreshCw,
  FileText,
  ArrowDownLeft,
  BookOpen,
  Edit3,
} from 'lucide-react';
import api from '../../services/api';
import type { Customer } from '../../types';
import { useUIStore } from '../../context/uiStore';
import { Spinner } from '../../components/common/Spinner';
import { EmptyState } from '../../components/common/EmptyState';
import { Modal } from '../../components/common/Modal';
import { Input } from '../../components/common/Input';
import { Button } from '../../components/common/Button';
import { LedgerModal } from '../../components/finance/LedgerModal';
import { ReceiptVoucherModal } from '../../components/finance/ReceiptVoucherModal';

export function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  // Add customer modal
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [newCustomer, setNewCustomer] = useState({
    name: '',
    phone_number: '',
    email: '',
    passport_number: '',
    id_number: '',
    nationality: 'يمني',
    address: '',
    notes: '',
  });
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Edit customer modal
  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null);
  const [editCustomerForm, setEditCustomerForm] = useState({
    name: '',
    phone_number: '',
    email: '',
    passport_number: '',
    id_number: '',
    nationality: 'يمني',
    address: '',
    notes: '',
  });

  // Details / Ledger modal
  const [ledgerCustomerId, setLedgerCustomerId] = useState<number | null>(null);
  const [ledgerCustomerName, setLedgerCustomerName] = useState<string>('');

  // Quick receipt modal
  const [receiptCustomerId, setReceiptCustomerId] = useState<number | null>(null);

  const addToast = useUIStore((state) => state.addToast);

  const fetchCustomers = async () => {
    setIsLoading(true);
    try {
      const params: any = { limit: 100 };
      if (searchQuery.trim()) params.search = searchQuery.trim();
      const res = await api.get('/customers/', { params });
      setCustomers(res.data);
    } catch (err) {
      console.error('Failed to load customers', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchCustomers();
  }, []);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchCustomers();
  };

  const handleAddCustomer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCustomer.name || !newCustomer.phone_number) {
      addToast('الاسم ورقم الهاتف مطلوبان', 'error');
      return;
    }

    setIsSubmitting(true);
    try {
      await api.post('/customers/', {
        name: newCustomer.name,
        phone_number: newCustomer.phone_number,
        email: newCustomer.email || null,
        passport_number: newCustomer.passport_number || null,
        id_number: newCustomer.id_number || null,
        nationality: newCustomer.nationality || null,
        address: newCustomer.address || null,
        notes: newCustomer.notes || null,
      });
      addToast('تمت إضافة العميل بنجاح', 'success');
      setIsAddModalOpen(false);
      setNewCustomer({
        name: '',
        phone_number: '',
        email: '',
        passport_number: '',
        id_number: '',
        nationality: 'يمني',
        address: '',
        notes: '',
      });
      fetchCustomers();
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'فشل حفظ بيانات العميل';
      addToast(msg, 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  const openEditCustomer = (c: Customer) => {
    setEditingCustomer(c);
    setEditCustomerForm({
      name: c.name || '',
      phone_number: c.phone_number || '',
      email: c.email || '',
      passport_number: c.passport_number || '',
      id_number: c.id_number || '',
      nationality: c.nationality || 'يمني',
      address: c.address || '',
      notes: c.notes || '',
    });
  };

  const handleEditCustomer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingCustomer) return;
    if (!editCustomerForm.name || !editCustomerForm.phone_number) {
      addToast('الاسم ورقم الهاتف مطلوبان', 'error');
      return;
    }

    setIsSubmitting(true);
    try {
      await api.put(`/customers/${editingCustomer.id}`, {
        name: editCustomerForm.name,
        phone_number: editCustomerForm.phone_number,
        email: editCustomerForm.email || null,
        passport_number: editCustomerForm.passport_number || null,
        id_number: editCustomerForm.id_number || null,
        nationality: editCustomerForm.nationality || null,
        address: editCustomerForm.address || null,
        notes: editCustomerForm.notes || null,
      });
      addToast('تم تحديث بيانات العميل بنجاح', 'success');
      setEditingCustomer(null);
      fetchCustomers();
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'فشل تحديث بيانات العميل';
      addToast(msg, 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  const openLedger = (c: Customer) => {
    setLedgerCustomerId(c.id);
    setLedgerCustomerName(c.name);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900">سجل ودليل العملاء</h1>
          <p className="text-sm text-slate-500">
            إدارة بيانات العملاء، متابعة المديونيات، واستعراض كشوفات الحساب
          </p>
        </div>

        <button
          onClick={() => setIsAddModalOpen(true)}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-bold text-white bg-[#1e3a8a] hover:bg-[#1e40af] rounded-xl shadow-xs transition-colors"
        >
          <UserPlus className="w-4 h-4" />
          إضافة عميل جديد
        </button>
      </div>

      {/* Search Toolbar */}
      <div className="flex items-center justify-between gap-3 p-4 bg-white rounded-2xl border border-slate-200 shadow-2xs">
        <form onSubmit={handleSearchSubmit} className="relative flex-1 max-w-md">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="بحث بالاسم، رقم الهاتف، رقم الجواز أو الهوية..."
            className="w-full rounded-xl border border-slate-200 bg-slate-50 pr-9 pl-4 py-2 text-xs sm:text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:bg-white focus:ring-2 focus:ring-[#1e3a8a]"
          />
          <button
            type="submit"
            className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600"
          >
            <Search className="w-4 h-4" />
          </button>
        </form>

        <button
          onClick={fetchCustomers}
          className="p-2 rounded-xl border border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100 transition-colors"
          title="تحديث البيانات"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Customers Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-2xs overflow-hidden">
        {isLoading ? (
          <div className="py-16">
            <Spinner size="lg" label="جارٍ تحميل سجل العملاء..." />
          </div>
        ) : customers.length === 0 ? (
          <EmptyState
            icon={<Users className="w-8 h-8 text-slate-400" />}
            title="لا يوجد عملاء مسجلون"
            description="لم يتم العثور على أي عميل يطابق معايير البحث."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-right text-xs sm:text-sm">
              <thead className="bg-slate-50 text-slate-600 border-b border-slate-200 font-semibold">
                <tr>
                  <th className="px-4 py-3">الاسم</th>
                  <th className="px-4 py-3">رقم الهاتف</th>
                  <th className="px-4 py-3">رقم الجواز</th>
                  <th className="px-4 py-3">رقم الهوية</th>
                  <th className="px-4 py-3">الجنسية</th>
                  <th className="px-4 py-3">الرصيد المستحق</th>
                  <th className="px-4 py-3 text-center">الإجراءات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {customers.map((c) => (
                  <tr key={c.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="px-4 py-3 font-bold text-slate-900">{c.name}</td>
                    <td className="px-4 py-3 text-slate-600 font-mono">{c.phone_number}</td>
                    <td className="px-4 py-3 font-mono text-slate-500">{c.passport_number || '--'}</td>
                    <td className="px-4 py-3 font-mono text-slate-500">{c.id_number || '--'}</td>
                    <td className="px-4 py-3 text-slate-600">{c.nationality || 'يمني'}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`font-bold ${
                          Number(c.balance) > 0
                            ? 'text-red-600'
                            : Number(c.balance) < 0
                            ? 'text-emerald-600'
                            : 'text-slate-700'
                        }`}
                      >
                        {Number(c.balance).toLocaleString()} YER
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex items-center justify-center gap-1.5">
                        <button
                          onClick={() => openLedger(c)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-blue-50 text-[#1e3a8a] hover:bg-blue-100 transition-colors"
                          title="عرض كشف الحساب وسجل الأستاذ"
                        >
                          <BookOpen className="w-3.5 h-3.5" />
                          <span>كشف حساب</span>
                        </button>
                        <button
                          onClick={() => setReceiptCustomerId(c.id)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-emerald-50 text-emerald-800 hover:bg-emerald-100 transition-colors"
                          title="قبض سند مالي من هذا العميل"
                        >
                          <ArrowDownLeft className="w-3.5 h-3.5" />
                          <span>سند قبض</span>
                        </button>
                        <button
                          onClick={() => openEditCustomer(c)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-slate-100 text-slate-700 hover:bg-slate-200 transition-colors"
                          title="تعديل بيانات العميل"
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                          <span>تعديل</span>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Add Customer Modal */}
      <Modal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        title="إضافة عميل جديد للنظام"
        description="تسجيل بيانات العميل الشخصية للتواصل والحجوزات"
        size="md"
      >
        <form onSubmit={handleAddCustomer} className="space-y-4">
          <Input
            label="اسم العميل الكامل"
            placeholder="الاسم الثلاثي أو الرباعي..."
            required
            value={newCustomer.name}
            onChange={(e) => setNewCustomer({ ...newCustomer, name: e.target.value })}
          />

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label="رقم الهاتف"
              placeholder="77xxxxxxx"
              required
              value={newCustomer.phone_number}
              onChange={(e) => setNewCustomer({ ...newCustomer, phone_number: e.target.value })}
            />

            <Input
              label="البريد الإلكتروني (اختياري)"
              type="email"
              placeholder="client@example.com"
              value={newCustomer.email}
              onChange={(e) => setNewCustomer({ ...newCustomer, email: e.target.value })}
            />

            <Input
              label="رقم الجواز"
              placeholder="08xxxxxx"
              value={newCustomer.passport_number}
              onChange={(e) => setNewCustomer({ ...newCustomer, passport_number: e.target.value })}
            />

            <Input
              label="رقم البطاقة الشخصية"
              placeholder="0101xxxxxxxx"
              value={newCustomer.id_number}
              onChange={(e) => setNewCustomer({ ...newCustomer, id_number: e.target.value })}
            />

            <Input
              label="الجنسية"
              value={newCustomer.nationality}
              onChange={(e) => setNewCustomer({ ...newCustomer, nationality: e.target.value })}
            />

            <Input
              label="العنوان / المدينة"
              placeholder="صنعاء / عدن..."
              value={newCustomer.address}
              onChange={(e) => setNewCustomer({ ...newCustomer, address: e.target.value })}
            />
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
            <Button type="button" variant="ghost" onClick={() => setIsAddModalOpen(false)}>
              إلغاء
            </Button>
            <Button type="submit" variant="primary" isLoading={isSubmitting}>
              حفظ العميل
            </Button>
          </div>
        </form>
      </Modal>

      {/* Edit Customer Modal */}
      <Modal
        isOpen={!!editingCustomer}
        onClose={() => setEditingCustomer(null)}
        title="تعديل بيانات العميل"
        description="تحديث البيانات الشخصية ومعلومات التواصل للعميل"
        size="md"
      >
        <form onSubmit={handleEditCustomer} className="space-y-4">
          <Input
            label="اسم العميل الكامل"
            required
            value={editCustomerForm.name}
            onChange={(e) => setEditCustomerForm({ ...editCustomerForm, name: e.target.value })}
          />

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label="رقم الهاتف"
              required
              value={editCustomerForm.phone_number}
              onChange={(e) => setEditCustomerForm({ ...editCustomerForm, phone_number: e.target.value })}
            />

            <Input
              label="البريد الإلكتروني (اختياري)"
              type="email"
              value={editCustomerForm.email}
              onChange={(e) => setEditCustomerForm({ ...editCustomerForm, email: e.target.value })}
            />

            <Input
              label="رقم الجواز"
              value={editCustomerForm.passport_number}
              onChange={(e) => setEditCustomerForm({ ...editCustomerForm, passport_number: e.target.value })}
            />

            <Input
              label="رقم البطاقة الشخصية"
              value={editCustomerForm.id_number}
              onChange={(e) => setEditCustomerForm({ ...editCustomerForm, id_number: e.target.value })}
            />

            <Input
              label="الجنسية"
              value={editCustomerForm.nationality}
              onChange={(e) => setEditCustomerForm({ ...editCustomerForm, nationality: e.target.value })}
            />

            <Input
              label="العنوان / المدينة"
              value={editCustomerForm.address}
              onChange={(e) => setEditCustomerForm({ ...editCustomerForm, address: e.target.value })}
            />
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
            <Button type="button" variant="ghost" onClick={() => setEditingCustomer(null)}>
              إلغاء
            </Button>
            <Button type="submit" variant="primary" isLoading={isSubmitting}>
              حفظ التعديلات
            </Button>
          </div>
        </form>
      </Modal>

      {/* Ledger Modal */}
      <LedgerModal
        isOpen={!!ledgerCustomerId}
        onClose={() => setLedgerCustomerId(null)}
        entityType="customer"
        entityId={ledgerCustomerId}
        entityName={ledgerCustomerName}
      />

      {/* Quick Receipt Modal */}
      <ReceiptVoucherModal
        isOpen={!!receiptCustomerId}
        onClose={() => setReceiptCustomerId(null)}
        onSuccess={fetchCustomers}
        initialCustomerId={receiptCustomerId || undefined}
      />
    </div>
  );
}

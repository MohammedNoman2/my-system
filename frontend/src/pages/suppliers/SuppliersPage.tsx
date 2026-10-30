import React, { useState, useEffect } from 'react';
import {
  Building2,
  PlusCircle,
  RefreshCw,
  ArrowUpRight,
  BookOpen,
  Search,
  Edit3,
} from 'lucide-react';
import api from '../../services/api';
import type { Supplier } from '../../types';
import { useUIStore } from '../../context/uiStore';
import { Spinner } from '../../components/common/Spinner';
import { EmptyState } from '../../components/common/EmptyState';
import { Modal } from '../../components/common/Modal';
import { Input } from '../../components/common/Input';
import { Button } from '../../components/common/Button';
import { LedgerModal } from '../../components/finance/LedgerModal';
import { PaymentVoucherModal } from '../../components/finance/PaymentVoucherModal';

export function SuppliersPage() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  // Add modal
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [newSupplier, setNewSupplier] = useState({
    name: '',
    phone_number: '',
    service_type: 'طيران',
    address: '',
  });
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Edit modal
  const [editingSupplier, setEditingSupplier] = useState<Supplier | null>(null);
  const [editSupplierForm, setEditSupplierForm] = useState({
    name: '',
    phone_number: '',
    service_type: 'طيران',
    address: '',
  });

  // Ledger modal
  const [ledgerSupplierId, setLedgerSupplierId] = useState<number | null>(null);
  const [ledgerSupplierName, setLedgerSupplierName] = useState<string>('');

  // Quick payment modal
  const [paymentSupplierId, setPaymentSupplierId] = useState<number | null>(null);

  const addToast = useUIStore((state) => state.addToast);

  const fetchSuppliers = async () => {
    setIsLoading(true);
    try {
      const params: any = { limit: 100 };
      if (searchQuery.trim()) params.search = searchQuery.trim();
      const res = await api.get('/suppliers/', { params });
      setSuppliers(res.data);
    } catch (err) {
      console.error('Failed to load suppliers', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchSuppliers();
  };

  const openEditSupplier = (s: Supplier) => {
    setEditingSupplier(s);
    setEditSupplierForm({
      name: s.name || '',
      phone_number: s.phone_number || '',
      service_type: s.service_type || 'طيران',
      address: s.address || '',
    });
  };

  const handleEditSupplier = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingSupplier) return;
    if (!editSupplierForm.name) {
      addToast('اسم المورد مطلوب', 'error');
      return;
    }

    setIsSubmitting(true);
    try {
      await api.put(`/suppliers/${editingSupplier.id}`, {
        name: editSupplierForm.name,
        phone_number: editSupplierForm.phone_number || null,
        service_type: editSupplierForm.service_type || null,
        address: editSupplierForm.address || null,
      });
      addToast('تم تحديث بيانات المورد بنجاح', 'success');
      setEditingSupplier(null);
      fetchSuppliers();
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'فشل تحديث بيانات المورد';
      addToast(msg, 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  useEffect(() => {
    fetchSuppliers();
  }, []);

  const handleAddSupplier = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSupplier.name) {
      addToast('اسم المورد مطلوب', 'error');
      return;
    }

    setIsSubmitting(true);
    try {
      await api.post('/suppliers/', {
        name: newSupplier.name,
        phone_number: newSupplier.phone_number || null,
        service_type: newSupplier.service_type || null,
        address: newSupplier.address || null,
      });
      addToast('تمت إضافة المورد بنجاح', 'success');
      setIsAddModalOpen(false);
      setNewSupplier({ name: '', phone_number: '', service_type: 'طيران', address: '' });
      fetchSuppliers();
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'فشل حفظ بيانات المورد';
      addToast(msg, 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  const openLedger = (s: Supplier) => {
    setLedgerSupplierId(s.id);
    setLedgerSupplierName(s.name);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900">الموردون وشركات الطيران والنقل</h1>
          <p className="text-sm text-slate-500">
            إدارة حسابات الموردين، شركات النقل، وكالات التأشيرات، وسجلات الأستاذ
          </p>
        </div>

        <button
          onClick={() => setIsAddModalOpen(true)}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-bold text-white bg-[#1e3a8a] hover:bg-[#1e40af] rounded-xl shadow-xs transition-colors"
        >
          <PlusCircle className="w-4 h-4" />
          إضافة مورد جديد
        </button>
      </div>

      {/* Search Toolbar */}
      <div className="flex items-center justify-between gap-3 p-4 bg-white rounded-2xl border border-slate-200 shadow-2xs">
        <form onSubmit={handleSearchSubmit} className="relative flex-1 max-w-md">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="بحث باسم المورد، نوع الخدمة، أو رقم الهاتف..."
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
          onClick={fetchSuppliers}
          className="p-2 rounded-xl border border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100 transition-colors"
          title="تحديث البيانات"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Suppliers Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-2xs overflow-hidden">
        {isLoading ? (
          <div className="py-16">
            <Spinner size="lg" label="جارٍ تحميل قائمة الموردين..." />
          </div>
        ) : suppliers.length === 0 ? (
          <EmptyState
            icon={<Building2 className="w-8 h-8 text-slate-400" />}
            title="لا يوجد موردون مسجلون"
            description="يمكنك إضافة شركات الطيران والنقل والوكالات الشريكة لبدء ربط الحجوزات بهم."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-right text-xs sm:text-sm">
              <thead className="bg-slate-50 text-slate-600 border-b border-slate-200 font-semibold">
                <tr>
                  <th className="px-4 py-3">اسم المورد / الشركة</th>
                  <th className="px-4 py-3">نوع الخدمة</th>
                  <th className="px-4 py-3">رقم الهاتف</th>
                  <th className="px-4 py-3">العنوان</th>
                  <th className="px-4 py-3">الرصيد المستحق له</th>
                  <th className="px-4 py-3 text-center">الإجراءات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {suppliers.map((s) => (
                  <tr key={s.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="px-4 py-3 font-bold text-slate-900">{s.name}</td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 rounded-md text-xs font-semibold bg-slate-100 text-slate-700">
                        {s.service_type || 'عام'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-600 font-mono">{s.phone_number || '--'}</td>
                    <td className="px-4 py-3 text-slate-600">{s.address || '--'}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`font-bold ${
                          Number(s.balance) > 0
                            ? 'text-amber-700'
                            : Number(s.balance) < 0
                            ? 'text-emerald-700'
                            : 'text-slate-700'
                        }`}
                      >
                        {Number(s.balance).toLocaleString()} YER
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex items-center justify-center gap-1.5">
                        <button
                          onClick={() => openLedger(s)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-blue-50 text-[#1e3a8a] hover:bg-blue-100 transition-colors"
                          title="عرض كشف الحساب وسجل الأستاذ"
                        >
                          <BookOpen className="w-3.5 h-3.5" />
                          <span>كشف حساب</span>
                        </button>
                        <button
                          onClick={() => setPaymentSupplierId(s.id)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-amber-50 text-amber-800 hover:bg-amber-100 transition-colors"
                          title="صرف دفعة أو سداد لهذا المورد"
                        >
                          <ArrowUpRight className="w-3.5 h-3.5" />
                          <span>سند صرف</span>
                        </button>
                        <button
                          onClick={() => openEditSupplier(s)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-slate-100 text-slate-700 hover:bg-slate-200 transition-colors"
                          title="تعديل بيانات المورد"
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

      {/* Add Supplier Modal */}
      <Modal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        title="إضافة مورد أو شركة جديدة"
        description="تسجيل بيانات شركات الطيران والنقل والمؤسسات المعتمدة"
        size="md"
      >
        <form onSubmit={handleAddSupplier} className="space-y-4">
          <Input
            label="اسم المورد أو الشركة"
            placeholder="مثال: الخطوط الجوية اليمنية / شركة الأولى للنقل..."
            required
            value={newSupplier.name}
            onChange={(e) => setNewSupplier({ ...newSupplier, name: e.target.value })}
          />

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label="نوع الخدمة الرئيسية"
              placeholder="طيران / نقل بري / تأشيرات..."
              value={newSupplier.service_type}
              onChange={(e) => setNewSupplier({ ...newSupplier, service_type: e.target.value })}
            />

            <Input
              label="رقم الهاتف"
              placeholder="01xxxxxx / 77xxxxxxx"
              value={newSupplier.phone_number}
              onChange={(e) => setNewSupplier({ ...newSupplier, phone_number: e.target.value })}
            />
          </div>

          <Input
            label="العنوان والمقر"
            placeholder="صنعاء - شارع الزبيري..."
            value={newSupplier.address}
            onChange={(e) => setNewSupplier({ ...newSupplier, address: e.target.value })}
          />

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
            <Button type="button" variant="ghost" onClick={() => setIsAddModalOpen(false)}>
              إلغاء
            </Button>
            <Button type="submit" variant="primary" isLoading={isSubmitting}>
              حفظ المورد
            </Button>
          </div>
        </form>
      </Modal>

      {/* Edit Supplier Modal */}
      <Modal
        isOpen={!!editingSupplier}
        onClose={() => setEditingSupplier(null)}
        title="تعديل بيانات المورد"
        description="تحديث بيانات شركة الطيران أو النقل أو الوكالة الشريكة"
        size="md"
      >
        <form onSubmit={handleEditSupplier} className="space-y-4">
          <Input
            label="اسم المورد أو الشركة"
            required
            value={editSupplierForm.name}
            onChange={(e) => setEditSupplierForm({ ...editSupplierForm, name: e.target.value })}
          />

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label="نوع الخدمة الرئيسية"
              value={editSupplierForm.service_type}
              onChange={(e) => setEditSupplierForm({ ...editSupplierForm, service_type: e.target.value })}
            />

            <Input
              label="رقم الهاتف"
              value={editSupplierForm.phone_number}
              onChange={(e) => setEditSupplierForm({ ...editSupplierForm, phone_number: e.target.value })}
            />
          </div>

          <Input
            label="العنوان والمقر"
            value={editSupplierForm.address}
            onChange={(e) => setEditSupplierForm({ ...editSupplierForm, address: e.target.value })}
          />

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
            <Button type="button" variant="ghost" onClick={() => setEditingSupplier(null)}>
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
        isOpen={!!ledgerSupplierId}
        onClose={() => setLedgerSupplierId(null)}
        entityType="supplier"
        entityId={ledgerSupplierId}
        entityName={ledgerSupplierName}
      />

      {/* Quick Payment Modal */}
      <PaymentVoucherModal
        isOpen={!!paymentSupplierId}
        onClose={() => setPaymentSupplierId(null)}
        onSuccess={fetchSuppliers}
        initialSupplierId={paymentSupplierId || undefined}
      />
    </div>
  );
}

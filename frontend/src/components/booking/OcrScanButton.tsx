import React, { useState, useRef } from 'react';
import { Scan, Loader2, Sparkles } from 'lucide-react';
import api from '../../services/api';
import { useUIStore } from '../../context/uiStore';

interface OcrScanButtonProps {
  type: 'passport' | 'id';
  onExtracted: (data: {
    passenger_name?: string;
    passport_number?: string;
    id_number?: string;
    birth_date?: string;
    birth_place?: string;
  }) => void;
}

export function OcrScanButton({ type, onExtracted }: OcrScanButtonProps) {
  const [isLoading, setIsLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const addToast = useUIStore((state) => state.addToast);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
      addToast('يرجى اختيار ملف صورة صالح (JPEG/PNG)', 'error');
      return;
    }

    const formData = new FormData();
    formData.append('file', file);

    setIsLoading(true);
    try {
      const endpoint = type === 'passport' ? '/ocr/extract-passport' : '/ocr/extract-id';
      const res = await api.post(endpoint, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      const data = res.data;
      onExtracted({
        passenger_name: data.passenger_name || undefined,
        passport_number: data.passport_number || undefined,
        id_number: data.id_number || undefined,
        birth_date: data.birth_date ? String(data.birth_date) : undefined,
        birth_place: data.birth_place || undefined,
      });

      addToast('تم استخراج وقراءة بيانات الوثيقة بالذكاء الاصطناعي بنجاح', 'success');
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'فشلت معالجة الصورة ضوئياً';
      addToast(msg, 'error');
    } finally {
      setIsLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  return (
    <div>
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        accept="image/*"
        className="hidden"
      />
      <button
        type="button"
        disabled={isLoading}
        onClick={() => fileInputRef.current?.click()}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg border border-purple-200 bg-purple-50 text-purple-800 hover:bg-purple-100 transition-colors shadow-2xs disabled:opacity-50 cursor-pointer"
        title={type === 'passport' ? 'مسح وقراءة الجواز بالـ OCR' : 'مسح وقراءة الهوية بالـ OCR'}
      >
        {isLoading ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin text-purple-600" />
        ) : (
          <Sparkles className="w-3.5 h-3.5 text-purple-600" />
        )}
        <span>مسح ضوئي بالـ OCR</span>
      </button>
    </div>
  );
}

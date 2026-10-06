import React, { useState, useRef, useEffect } from 'react';
import { Printer, Download, Loader2 } from 'lucide-react';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';
import api from '../../services/api';

interface BookingPrintModalProps {
  bookingId: number | null;
  isOpen: boolean;
  onClose: () => void;
}

export function BookingPrintModal({ bookingId, isOpen, onClose }: BookingPrintModalProps) {
  const [printMode, setPrintMode] = useState<'thermal' | 'a4'>('thermal');
  const [htmlContent, setHtmlContent] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  // Fetch voucher HTML via Axios (carries auth cookies automatically)
  useEffect(() => {
    if (!bookingId || !isOpen) return;

    setIsLoading(true);
    setError(null);
    setHtmlContent('');

    api
      .get(`/bookings/${bookingId}/print?mode=${printMode}&format=html`)
      .then((res) => {
        setHtmlContent(res.data);
      })
      .catch((err) => {
        const msg =
          err.response?.data?.detail ||
          `فشل تحميل السند (${err.response?.status || 'خطأ شبكة'})`;
        setError(msg);
      })
      .finally(() => setIsLoading(false));
  }, [bookingId, isOpen, printMode]);

  if (!bookingId) return null;

  const pdfDownloadUrl = `/api/bookings/${bookingId}/print?mode=${printMode}&format=pdf`;

  const handlePrint = () => {
    if (iframeRef.current?.contentWindow) {
      iframeRef.current.contentWindow.focus();
      iframeRef.current.contentWindow.print();
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="معاينة وطباعة سند الحجز الرسمي"
      description="اختر صيغة الطباعة المناسبة (سند حراري 80mm أو قياس A4 رسمي)"
      size="xl"
    >
      <div className="space-y-4">
        {/* Toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-3 p-3 bg-slate-50 rounded-xl border border-slate-200">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-slate-700">نوع السند:</span>
            <button
              type="button"
              onClick={() => setPrintMode('thermal')}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                printMode === 'thermal'
                  ? 'bg-[#1e3a8a] text-white shadow-sm'
                  : 'bg-white text-slate-700 hover:bg-slate-100 border border-slate-200'
              }`}
            >
              حراري (80mm Thermal)
            </button>
            <button
              type="button"
              onClick={() => setPrintMode('a4')}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                printMode === 'a4'
                  ? 'bg-[#1e3a8a] text-white shadow-sm'
                  : 'bg-white text-slate-700 hover:bg-slate-100 border border-slate-200'
              }`}
            >
              ورق رسمي (A4 Standard)
            </button>
          </div>

          <div className="flex items-center gap-2">
            <a
              href={pdfDownloadUrl}
              download={`voucher-${bookingId}.pdf`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
            >
              <Download className="w-3.5 h-3.5 text-slate-500" />
              تنزيل PDF
            </a>
            <Button
              type="button"
              variant="primary"
              size="sm"
              onClick={handlePrint}
              disabled={isLoading || !!error || !htmlContent}
              icon={<Printer className="w-4 h-4" />}
            >
              طباعة الآن
            </Button>
          </div>
        </div>

        {/* Preview Area */}
        <div className="border border-slate-200 rounded-xl overflow-hidden bg-slate-100 h-[500px] flex items-center justify-center">
          {isLoading && (
            <div className="flex flex-col items-center gap-3 text-slate-500">
              <Loader2 className="w-8 h-8 animate-spin" />
              <span className="text-sm">جاري تحميل السند...</span>
            </div>
          )}

          {error && !isLoading && (
            <div className="flex flex-col items-center gap-3 text-red-600 p-6 text-center">
              <div className="w-12 h-12 rounded-full bg-red-50 flex items-center justify-center">
                <span className="text-2xl">⚠️</span>
              </div>
              <p className="text-sm font-semibold">فشل تحميل السند</p>
              <p className="text-xs text-red-500">{error}</p>
            </div>
          )}

          {!isLoading && !error && htmlContent && (
            <iframe
              ref={iframeRef}
              srcDoc={htmlContent}
              title="سند الحجز"
              className={`h-full bg-white shadow-sm transition-all duration-300 ${
                printMode === 'thermal' ? 'w-[380px]' : 'w-full'
              }`}
            />
          )}
        </div>
      </div>
    </Modal>
  );
}

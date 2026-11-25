import React, { useState, useRef, useEffect, useMemo } from 'react';
import { Printer, Download, Loader2 } from 'lucide-react';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';
import api from '../../services/api';

interface BookingPrintModalProps {
  bookingId?: number | null;
  bookingIds?: number[];
  isOpen: boolean;
  onClose: () => void;
}

export function BookingPrintModal({
  bookingId,
  bookingIds,
  isOpen,
  onClose,
}: BookingPrintModalProps) {
  const effectiveIds = useMemo(() => {
    if (bookingIds && bookingIds.length > 0) return bookingIds;
    if (bookingId) return [bookingId];
    return [];
  }, [bookingId, bookingIds]);

  const [activeIndex, setActiveIndex] = useState(0);
  const [printMode, setPrintMode] = useState<'thermal' | 'a4'>('thermal');
  const [htmlMap, setHtmlMap] = useState<Record<number, string>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    setActiveIndex(0);
  }, [effectiveIds, isOpen]);

  // Fetch all tickets in the batch via Axios (carries auth cookies automatically)
  useEffect(() => {
    if (effectiveIds.length === 0 || !isOpen) return;

    let cancelled = false;
    setIsLoading(true);
    setError(null);
    setHtmlMap({});

    Promise.all(
      effectiveIds.map((id) =>
        api
          .get(`/bookings/${id}/print?mode=${printMode}&format=html`)
          .then((res) => [id, res.data as string] as const)
      )
    )
      .then((entries) => {
        if (cancelled) return;
        const map: Record<number, string> = {};
        for (const [id, html] of entries) {
          map[id] = html;
        }
        setHtmlMap(map);
      })
      .catch((err) => {
        if (cancelled) return;
        const msg =
          err.response?.data?.detail ||
          `فشل تحميل السند (${err.response?.status || 'خطأ شبكة'})`;
        setError(msg);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [effectiveIds, isOpen, printMode]);

  if (effectiveIds.length === 0) return null;

  const activeId = effectiveIds[Math.min(activeIndex, effectiveIds.length - 1)];
  const htmlContent = htmlMap[activeId] || '';

  const handlePrintCurrent = () => {
    if (iframeRef.current?.contentWindow) {
      iframeRef.current.contentWindow.focus();
      iframeRef.current.contentWindow.print();
    }
  };

  const handlePrintAll = () => {
    const pages = effectiveIds.map((id) => htmlMap[id]).filter(Boolean);
    if (pages.length === 0) return;
    if (pages.length === 1) {
      handlePrintCurrent();
      return;
    }
    const firstStyleMatch = pages[0].match(/<style[^>]*>[\s\S]*?<\/style>/i);
    const styleBlock = firstStyleMatch ? firstStyleMatch[0] : '';
    const bodies = pages.map((html, idx) => {
      const m = html.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
      const inner = m ? m[1] : html;
      const breakStyle = idx < pages.length - 1 ? 'page-break-after: always; break-after: page;' : '';
      return `<div style="${breakStyle}">${inner}</div>`;
    });
    const combinedHtml = `<!DOCTYPE html><html dir="rtl" lang="ar"><head><meta charset="UTF-8"><title>طباعة التذاكر (${pages.length})</title>${styleBlock}</head><body>${bodies.join('\n')}</body></html>`;
    const printWin = window.open('', '_blank', 'width=900,height=650');
    if (!printWin) return;
    printWin.document.open();
    printWin.document.write(combinedHtml);
    printWin.document.close();
    printWin.focus();
    setTimeout(() => printWin.print(), 300);
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        effectiveIds.length > 1
          ? `معاينة وطباعة تذاكر الدفعة (${effectiveIds.length} تذاكر)`
          : 'معاينة وطباعة سند الحجز الرسمي'
      }
      description="اختر صيغة الطباعة المناسبة (سند حراري 80mm أفقي أو قياس A4 رسمي)"
      size="xl"
    >
      <div className="space-y-4">
        {/* Batch ticket switcher */}
        {effectiveIds.length > 1 && (
          <div className="flex flex-wrap items-center gap-2 p-2.5 bg-blue-50/70 border border-blue-200 rounded-xl">
            <span className="text-xs font-bold text-blue-900 ml-1">التذاكر المُصدَرة:</span>
            {effectiveIds.map((id, idx) => (
              <button
                key={id}
                type="button"
                onClick={() => setActiveIndex(idx)}
                className={`px-3 py-1 text-xs font-bold rounded-lg transition-colors ${
                  activeIndex === idx
                    ? 'bg-[#1e3a8a] text-white shadow-sm'
                    : 'bg-white text-blue-900 border border-blue-200 hover:bg-blue-100/60'
                }`}
              >
                تذكرة {idx + 1}
              </button>
            ))}
          </div>
        )}

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
              حراري (80mm × 60mm أفقي)
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
            <button
              type="button"
              onClick={handlePrintCurrent}
              disabled={isLoading || !!error || !htmlContent}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors disabled:opacity-50"
              title="اختر Save as PDF من نافذة الطباعة لحفظ ملف PDF أصلي"
            >
              <Download className="w-3.5 h-3.5 text-slate-500" />
              طباعة الحالية / PDF
            </button>
            {effectiveIds.length > 1 ? (
              <Button
                type="button"
                variant="primary"
                size="sm"
                onClick={handlePrintAll}
                disabled={isLoading || !!error || Object.keys(htmlMap).length === 0}
                icon={<Printer className="w-4 h-4" />}
              >
                طباعة جميع التذاكر ({effectiveIds.length})
              </Button>
            ) : (
              <Button
                type="button"
                variant="primary"
                size="sm"
                onClick={handlePrintCurrent}
                disabled={isLoading || !!error || !htmlContent}
                icon={<Printer className="w-4 h-4" />}
              >
                طباعة الآن
              </Button>
            )}
          </div>
        </div>

        {/* Preview Area */}
        <div className="border border-slate-200 rounded-xl overflow-hidden bg-slate-100 h-[500px] flex items-center justify-center">
          {isLoading && (
            <div className="flex flex-col items-center gap-3 text-slate-500">
              <Loader2 className="w-8 h-8 animate-spin" />
              <span className="text-sm">جاري تحميل التذاكر...</span>
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
                printMode === 'thermal' ? 'w-[420px]' : 'w-full'
              }`}
            />
          )}
        </div>
      </div>
    </Modal>
  );
}

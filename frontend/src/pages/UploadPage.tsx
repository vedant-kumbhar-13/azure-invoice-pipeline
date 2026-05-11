import { useState } from 'react';
import { useUploadInvoice } from '../hooks/useUploadInvoice';
import { useBulkUploadInvoice } from '../hooks/useBulkUploadInvoice';
import { FileDropzone } from '../components/FileDropzone';
import { UploadCloud, ChevronRight, FileSearch, Fingerprint, Network, Files } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../api/client';
import type { InvoiceListItem } from '../types';
import { StatusBadge } from '../components/StatusBadge';
import { formatCurrency, formatTimeAgo } from '../utils/formatters';

type UploadMode = 'single' | 'bulk';

export const UploadPage = () => {
  const [mode, setMode] = useState<UploadMode>('single');
  const { mutate: uploadInvoice, isPending: isSinglePending } = useUploadInvoice();
  const { mutate: uploadBulk, isPending: isBulkPending } = useBulkUploadInvoice();

  const handleUpload = (file: File) => {
    uploadInvoice(file);
  };

  const handleBulkUpload = (files: File[]) => {
    uploadBulk(files);
  };

  const isPending = mode === 'single' ? isSinglePending : isBulkPending;

  const { data: recentInvoices } = useQuery<{items: InvoiceListItem[]}>({
    queryKey: ['invoices', { limit: 5 }],
    queryFn: async () => {
      const res = await apiClient.get('/invoices/?limit=5');
      return res.data;
    }
  });

  return (
    <div className="max-w-3xl mx-auto flex flex-col gap-10 pb-20">
      
      <div className="text-center pt-4">
         <h1 className="text-3xl font-bold tracking-tight text-ink-900 mb-2">Ingest Documents</h1>
         <p className="text-ink-500 font-medium">Securely upload e-Invoices or PDF documents for intelligent extraction.</p>
      </div>

      {/* Mode Toggle */}
      <div className="flex justify-center">
        <div className="inline-flex bg-ink-100 rounded-xl p-1 gap-0.5">
          <button
            onClick={() => setMode('single')}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-bold transition-all duration-200 ${
              mode === 'single'
                ? 'bg-white text-ink-900 shadow-sm'
                : 'text-ink-500 hover:text-ink-700'
            }`}
          >
            <UploadCloud className="h-4 w-4" />
            Single Invoice
          </button>
          <button
            onClick={() => setMode('bulk')}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-bold transition-all duration-200 ${
              mode === 'bulk'
                ? 'bg-white text-ink-900 shadow-sm'
                : 'text-ink-500 hover:text-ink-700'
            }`}
          >
            <Files className="h-4 w-4" />
            Bulk Upload
            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-md ${
              mode === 'bulk'
                ? 'bg-blue-100 text-blue-700'
                : 'bg-ink-200 text-ink-500'
            }`}>
              up to 20
            </span>
          </button>
        </div>
      </div>

      <div>
         <FileDropzone
           onUpload={handleUpload}
           onBulkUpload={handleBulkUpload}
           isUploading={isPending}
           mode={mode}
         />
      </div>

      {/* How it works - Horizontal Flow */}
      <div className="pt-2">
         <h3 className="text-[10px] font-bold text-ink-400 uppercase tracking-widest text-center mb-6">Processing Pipeline</h3>
         
         <div className="flex items-center justify-between gap-2 max-w-xl mx-auto relative">
            <div className="flex flex-col items-center flex-1 z-10">
               <div className="w-12 h-12 bg-white rounded-full border border-ink-200 shadow-sm flex items-center justify-center mb-3 text-indigo-500 relative">
                  <FileSearch className="w-5 h-5" />
                  <span className="absolute -top-1 -right-1 w-4 h-4 bg-ink-900 text-white rounded-full flex items-center justify-center text-[9px] font-bold">1</span>
               </div>
               <span className="text-[11px] font-bold text-ink-900 uppercase tracking-wider text-center">Scan</span>
               <span className="text-[10px] font-semibold text-ink-400 text-center mt-0.5">Detect e-Invoice QR</span>
            </div>
            
            <div className="text-ink-300 shrink-0 mt-[-24px]"><ChevronRight className="w-5 h-5" /></div>

            <div className="flex flex-col items-center flex-1 z-10">
               <div className="w-12 h-12 bg-white rounded-full border border-ink-200 shadow-sm flex items-center justify-center mb-3 text-sky-500 relative">
                  <Fingerprint className="w-5 h-5" />
                  <span className="absolute -top-1 -right-1 w-4 h-4 bg-ink-900 text-white rounded-full flex items-center justify-center text-[9px] font-bold">2</span>
               </div>
               <span className="text-[11px] font-bold text-ink-900 uppercase tracking-wider text-center">Extract</span>
               <span className="text-[10px] font-semibold text-ink-400 text-center mt-0.5">Azure AI Visual OCR</span>
            </div>

            <div className="text-ink-300 shrink-0 mt-[-24px]"><ChevronRight className="w-5 h-5" /></div>

            <div className="flex flex-col items-center flex-1 z-10">
               <div className="w-12 h-12 bg-white rounded-full border border-ink-200 shadow-sm flex items-center justify-center mb-3 text-emerald-500 relative">
                  <Network className="w-5 h-5" />
                  <span className="absolute -top-1 -right-1 w-4 h-4 bg-ink-900 text-white rounded-full flex items-center justify-center text-[9px] font-bold">3</span>
               </div>
               <span className="text-[11px] font-bold text-ink-900 uppercase tracking-wider text-center">Route</span>
               <span className="text-[10px] font-semibold text-ink-400 text-center mt-0.5">Smart validation</span>
            </div>
         </div>
      </div>

      {/* Recent Uploads block */}
      <div className="mt-4 flex flex-col gap-4">
         <h3 className="text-sm font-bold text-ink-900 tracking-tight">Recent Activity</h3>
         
         <div className="bg-white rounded-2xl border border-ink-200 shadow-sm overflow-hidden flex flex-col">
          {!recentInvoices?.items?.length ? (
            <div className="p-12 flex flex-col items-center justify-center text-center">
              <div className="w-16 h-16 bg-ink-50 rounded-full flex items-center justify-center mb-4">
                 <UploadCloud className="w-8 h-8 text-ink-300" />
              </div>
              <h4 className="font-bold text-ink-900">No uploads yet</h4>
              <p className="text-sm font-medium text-ink-500 mt-1">Files you process will appear here in chronological order.</p>
            </div>
          ) : (
            <div className="divide-y divide-ink-100">
              {recentInvoices.items.map((inv: InvoiceListItem) => (
                <div key={inv.id} className="p-4 flex items-center justify-between hover:bg-ink-50 transition-colors">
                  
                  <div className="flex items-center gap-4 min-w-0 pr-4">
                     <StatusBadge status={inv.status} />
                     <div className="flex flex-col gap-0.5 min-w-0">
                        <span className="font-semibold text-ink-900 text-sm truncate max-w-[150px] sm:max-w-xs" title={inv.original_filename}>
                          {inv.original_filename}
                        </span>
                        <span className="text-[11px] font-medium text-ink-500 truncate mt-0.5" title={inv.vendor_name || 'Unknown Vendor'}>
                          {inv.vendor_name || '—'}
                        </span>
                     </div>
                  </div>

                  <div className="flex items-center gap-6 shrink-0">
                    <span className="text-sm font-mono font-bold text-ink-900 text-right hidden sm:block">
                      {formatCurrency(inv.total_amount)}
                    </span>
                    <span className="text-xs font-semibold text-ink-400 text-right min-w-[70px]">
                      {formatTimeAgo(inv.created_at)}
                    </span>
                  </div>
                  
                </div>
              ))}
            </div>
          )}
         </div>
      </div>

    </div>
  );
};
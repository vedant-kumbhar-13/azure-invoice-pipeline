import { useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useInvoiceStatus } from '../hooks/useInvoiceStatus';
import { StatusBadge } from '../components/StatusBadge';
import { GSTRulesPanel } from '../components/GSTRulesPanel';
import { LineItemsTable } from '../components/LineItemsTable';
import { formatDate, formatCurrency } from '../utils/formatters';

import { AlertTriangle, Copy, Check, ArrowRight } from 'lucide-react';
import toast from 'react-hot-toast';

export const InvoiceDetailPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: invoice, isLoading, error, isPollingTimedOut } = useInvoiceStatus(id);
  const [activeTab, setActiveTab] = useState<'data' | 'gst' | 'items' | 'json'>('data');
  const [copied, setCopied] = useState(false);
  // Must be declared BEFORE any early returns — Rules of Hooks
  const lockedFileUrl = useRef<string>('');

  if (isLoading) {
    return <div className="flex h-[80vh] items-center justify-center text-ink-500 font-medium">Loading source context...</div>;
  }

  if (error || !invoice) {
    return <div className="flex h-[80vh] items-center justify-center text-red-500 font-medium">Failed to retrieve ledger record.</div>;
  }

  const data = invoice.data_json || invoice.data;
  const gstRulesJson = invoice.gst_rules_json || invoice.data?.gst_rules_json;

  const handleCopyJson = () => {
    navigator.clipboard.writeText(JSON.stringify(invoice, null, 2));
    setCopied(true);
    toast.success('Raw JSON copied to clipboard!');
    setTimeout(() => setCopied(false), 2000);
  };

  const renderField = (label: string, field: any, isCurrency = false) => {
    const isLowConfidence = field?.confidence !== undefined && field.confidence < 0.60 && field.confidence !== null;
    const valueStr = isCurrency ? formatCurrency(field?.value) : (field?.value ?? '—');
    const scorePct = field?.confidence !== undefined && field.confidence !== null ? Math.round(field.confidence * 100) : null;
    
    let confColor = 'bg-ink-300';
    if (scorePct !== null) {
       if (scorePct >= 90) confColor = 'bg-green-500';
       else if (scorePct >= 60) confColor = 'bg-amber-500';
       else confColor = 'bg-red-500';
    }

    return (
      <div className={`p-3 rounded-lg border ${isLowConfidence ? 'bg-red-50 border-red-200' : 'bg-white border-ink-200 shadow-sm'}`}>
        <span className="text-[10px] font-bold text-ink-500 uppercase tracking-wider">{label}</span>
        <p className={`font-semibold mt-0.5 mb-2 truncate ${isLowConfidence ? 'text-red-900' : 'text-ink-900'}`} title={valueStr}>{valueStr}</p>
        
        {/* Compact Bar */}
        {scorePct !== null && (
          <div className="w-full bg-ink-100 rounded-full h-1 overflow-hidden">
            <div className={`h-full ${confColor} transition-all`} style={{ width: `${scorePct}%` }} />
          </div>
        )}
      </div>
    );
  };

  const isReviewNeeded = ['NEEDS_REVIEW', 'HUMAN_REQUIRED'].includes(invoice.status?.toUpperCase() || '');
  // BUG-C3: file_url_sas is now the only file URL — backend no longer returns raw blob name.
  const freshFileUrl = invoice.file_url_sas || '';
  if (freshFileUrl && !lockedFileUrl.current) lockedFileUrl.current = freshFileUrl;
  const fileUrl = lockedFileUrl.current;
  const isPDF = invoice.original_filename?.toLowerCase().endsWith('.pdf');
  const hasFileUrl = !!fileUrl;
  
  // Overall Confidence Ring
  const ovScore = invoice.confidence_score !== null && invoice.confidence_score !== undefined ? Math.round(invoice.confidence_score * 100) : null;
  let ovRingColor = 'stroke-ink-200 text-ink-300';
  if (ovScore !== null) {
      if (ovScore >= 90) ovRingColor = 'stroke-green-500 text-green-500';
      else if (ovScore >= 60) ovRingColor = 'stroke-amber-500 text-amber-500';
      else ovRingColor = 'stroke-red-500 text-red-500';
  }

  const isQR = invoice.ingestion_method === 'QR' || invoice.source_type === 'GST_EINVOICE';
  const isOCR = invoice.ingestion_method === 'OCR' || invoice.source_type === 'GST_PDF';

  return (
    <div className={`flex flex-col lg:flex-row h-full min-h-[85vh] gap-6 lg:gap-8 ${isReviewNeeded ? 'pb-24' : ''}`}>
      
      {/* LEFT COLUMN: Original Doc */}
      <div className="lg:w-[40%] bg-ink-100 rounded-xl overflow-hidden flex flex-col ring-1 ring-ink-200">
        <div className="bg-ink-100 border-b border-ink-200 px-4 py-3 flex items-center justify-between shrink-0">
          <h3 className="font-bold text-sm text-ink-900 tracking-tight">Source Document</h3>
          {isQR ? (
             <span className="bg-indigo-100 text-indigo-700 border border-indigo-200 text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider">QR Code</span>
          ) : isOCR ? (
             <span className="bg-sky-100 text-sky-700 border border-sky-200 text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider">AI OCR</span>
          ) : null}
        </div>
        
        <div className="flex-1 overflow-hidden bg-white/50 relative flex items-center justify-center p-2 min-h-[500px]">
           {/* BUG-20: Loading skeleton when file URL is not yet available */}
           {!hasFileUrl ? (
             <div className="w-full h-full flex flex-col items-center justify-center space-y-4">
               <div className="w-3/4 h-4 bg-ink-200 rounded animate-pulse" />
               <div className="w-2/3 h-4 bg-ink-200 rounded animate-pulse" />
               <div className="w-1/2 h-4 bg-ink-200 rounded animate-pulse" />
               <div className="w-3/4 h-48 bg-ink-200 rounded animate-pulse mt-4" />
               <p className="text-xs text-ink-400 font-medium mt-2">Loading document preview...</p>
             </div>
           ) : isPDF ? (
             <iframe src={fileUrl} className="w-full h-full rounded shadow-inner" title="PDF Viewer" />
           ) : (
             <img src={fileUrl} alt="Invoice Document" className="max-w-full max-h-full object-contain rounded drop-shadow-sm" />
           )}
        </div>
        
        <div className="bg-ink-100 border-t border-ink-200 px-4 py-2 shrink-0 flex items-center justify-between">
           <span className="text-xs font-medium text-ink-500 truncate max-w-[200px]" title={invoice.original_filename}>{invoice.original_filename}</span>
           <span className="text-xs font-semibold text-ink-400">{formatDate(invoice.created_at)}</span>
        </div>
      </div>

      {/* RIGHT COLUMN: Data */}
      <div className="lg:w-[60%] flex flex-col h-full gap-6">
        
        {/* Header */}
        <div className="flex items-start justify-between bg-white p-5 rounded-xl border border-ink-200 shadow-sm shrink-0">
           <div>
               <h2 className="text-xl font-bold tracking-tight text-ink-900 truncate max-w-sm xl:max-w-md mb-2">
                 {invoice.original_filename}
               </h2>
               <StatusBadge status={invoice.status} />
           </div>
           
           <div className="flex flex-col items-center justify-center shrink-0 ml-4 border-l border-ink-100 pl-6">
              <div className="relative w-12 h-12 flex items-center justify-center">
                 <svg className="absolute inset-0 w-full h-full transform -rotate-90">
                   <circle cx="24" cy="24" r="20" fill="none" className="stroke-ink-100" strokeWidth="4" />
                   {ovScore !== null && (
                      <circle 
                        cx="24" cy="24" r="20" fill="none" className={`transition-all duration-1000 ${ovRingColor.split(' ')[0]}`}
                        strokeWidth="4" strokeDasharray="125.6" strokeDashoffset={125.6 - (125.6 * ovScore) / 100} strokeLinecap="round"
                      />
                   )}
                 </svg>
                 <span className={`text-[11px] font-black ${ovScore !== null ? ovRingColor.split(' ')[1] : 'text-ink-400'}`}>
                   {ovScore !== null ? `${ovScore}%` : '—'}
                 </span>
              </div>
              <span className="text-[9px] font-bold uppercase tracking-widest text-ink-400 mt-1">Confidence</span>
           </div>
        </div>

        {/* Segmented Control */}
        <div className="flex space-x-1 bg-ink-100 p-1 rounded-lg w-fit shadow-inner shrink-0">
          {(['data', 'gst', 'items', 'json'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-1.5 text-xs font-bold rounded-md transition-all uppercase tracking-wider
                ${activeTab === tab ? 'bg-white text-ink-900 shadow-sm' : 'text-ink-500 hover:text-ink-700'}`}
            >
              {tab === 'data' && 'Invoice Data'}
              {tab === 'gst' && 'GST Rules'}
              {tab === 'items' && 'Line Items'}
              {tab === 'json' && 'Raw JSON'}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="flex-1 overflow-y-auto custom-scrollbar pr-2 min-h-[400px]">
           {activeTab === 'data' && (
             <div className="space-y-6 animate-in fade-in duration-200">
                {/* Vendors & Buyers */}
                <div className="grid grid-cols-2 gap-4">
                   {renderField('Vendor Name', data?.vendor_name)}
                   {renderField('Vendor GSTIN', data?.vendor_gstin)}
                   {renderField('Buyer Name', data?.buyer_name)}
                   {renderField('Buyer GSTIN', data?.buyer_gstin)}
                </div>
                
                {/* Invoice Details */}
                <div className="grid grid-cols-3 gap-4">
                   {renderField('Invoice Number', data?.invoice_number)}
                   {renderField('Date', data?.invoice_date)}
                   {renderField('Subtotal', data?.subtotal, true)}
                </div>

                {/* Taxes */}
                <div className="grid grid-cols-3 gap-4">
                   {renderField('CGST', data?.cgst, true)}
                   {renderField('SGST', data?.sgst, true)}
                   {renderField('IGST', data?.igst, true)}
                </div>

                {/* Total */}
                <div className="bg-ink-950 p-6 rounded-xl flex items-center justify-between shadow-lg">
                   <span className="text-ink-400 font-bold uppercase tracking-widest text-sm">Grand Total Amount</span>
                   <span className="text-white text-4xl font-mono font-bold tracking-tight">
                      {formatCurrency(data?.total_amount?.value !== null && data?.total_amount?.value !== undefined ? Number(data.total_amount.value) : null)}
                   </span>
                </div>
             </div>
           )}

           {activeTab === 'gst' && (
             <div className="animate-in fade-in duration-200">
               <GSTRulesPanel gstData={gstRulesJson} />
             </div>
           )}

           {activeTab === 'items' && (
             <div className="animate-in fade-in duration-200">
               <LineItemsTable items={data?.line_items} />
             </div>
           )}

           {activeTab === 'json' && (
             <div className="relative h-full min-h-[400px] flex flex-col bg-ink-950 rounded-xl overflow-hidden animate-in fade-in duration-200 shadow-inner">
                <button 
                  onClick={handleCopyJson}
                  className="absolute top-4 right-4 p-2 bg-ink-800 hover:bg-ink-700 text-ink-300 rounded-md transition-colors shadow-sm ring-1 ring-white/10"
                  title="Copy JSON"
                >
                  {copied ? <Check className="h-4 w-4 text-emerald-400" /> : <Copy className="h-4 w-4" />}
                </button>
                <pre className="p-6 text-emerald-400 text-xs font-mono overflow-auto flex-1 custom-scrollbar whitespace-pre-wrap">
                  {JSON.stringify(invoice, null, 2)}
                </pre>
             </div>
           )}
        </div>
      </div>

      {/* BUG-16: Polling timeout warning */}
      {isPollingTimedOut && invoice.status?.toUpperCase() === 'PROCESSING' && (
        <div className="fixed bottom-0 left-0 right-0 z-50 md:left-[240px]">
          <div className="bg-red-50 border-t-2 border-red-400 px-6 py-3 flex items-center gap-3">
            <AlertTriangle className="h-5 w-5 text-red-500 shrink-0" />
            <p className="text-xs font-semibold text-red-700">Processing is taking longer than expected. The server will auto-escalate this invoice for manual review shortly.</p>
          </div>
        </div>
      )}

      {/* Manual Review Required Banner */}
      {isReviewNeeded && (
        <div className="fixed bottom-0 left-0 right-0 z-50 md:left-[240px]">
           <div className="bg-amber-50 border-t-2 border-amber-500 px-6 py-4 flex flex-col sm:flex-row items-center justify-between gap-4 shadow-[0_-10px_40px_rgba(0,0,0,0.1)]">
             <div className="flex items-center gap-4">
                <AlertTriangle className="h-6 w-6 text-amber-500 shrink-0" />
                <div>
                   <h4 className="font-extrabold text-amber-900 tracking-tight text-sm">Manual verification required</h4>
                   <p className="text-xs font-semibold text-amber-700/80 mt-0.5">Automated confidence constraint failed ({ovScore}%) or rule flagged.</p>
                </div>
             </div>
             <button 
                onClick={() => navigate('/review-queue')}
                className="whitespace-nowrap bg-amber-500 hover:bg-amber-600 focus:ring-4 focus:ring-amber-500/20 text-white px-5 py-2.5 rounded-md font-bold transition-all shadow-sm text-xs uppercase tracking-wider"
             >
                Open Review Queue <ArrowRight className="h-4 w-4 inline-block ml-1" />
             </button>
           </div>
        </div>
      )}

    </div>
  );
};
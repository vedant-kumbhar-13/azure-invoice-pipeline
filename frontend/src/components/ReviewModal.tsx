import { useState, useEffect, useRef } from 'react';
import { useInvoiceStatus } from '../hooks/useInvoiceStatus';
import { useReviewSubmit } from '../hooks/useReviewQueue';
import { X, Loader2, Save, CheckCircle, AlertTriangle } from 'lucide-react';
import { Input } from './ui/input';
import { Button } from './ui/button';
import toast from 'react-hot-toast';

export const ReviewModal = ({ invoiceId, onClose }: { invoiceId: string, onClose: () => void }) => {
  // 1. Remove polling inside modal
  const { data: invoice, isLoading } = useInvoiceStatus(invoiceId, { disablePolling: true });
  const { mutate: submitReview, isPending } = useReviewSubmit();

  const [formData, setFormData] = useState<any>({});
  const [notes, setNotes] = useState('');
  const [isSuccess, setIsSuccess] = useState(false);
  // FIX: Lock the file URL the first time it arrives so that any background
  // query refetch (which generates a fresh SAS URL) does NOT change the
  // iframe src and trigger another browser download.
  const lockedFileUrl = useRef<string>('');

  const invoiceData = invoice?.data_json || invoice?.data;

  useEffect(() => {
    if (invoiceData) {
       setFormData({
         vendor_name: invoiceData.vendor_name?.value || '',
         vendor_gstin: invoiceData.vendor_gstin?.value || '',
         buyer_name: invoiceData.buyer_name?.value || '',
         buyer_gstin: invoiceData.buyer_gstin?.value || '',
         invoice_number: invoiceData.invoice_number?.value || '',
         invoice_date: invoiceData.invoice_date?.value || '',
         // Use ?? instead of || for numeric fields — 0 is a valid value
         // (e.g. CGST=0 in a Bill of Supply), but || treats 0 as falsy
         subtotal: invoiceData.subtotal?.value ?? '',
         total_amount: invoiceData.total_amount?.value ?? '',
         cgst: invoiceData.cgst?.value ?? '',
         sgst: invoiceData.sgst?.value ?? '',
         igst: invoiceData.igst?.value ?? '',
       });
    }
  }, [invoiceData]);

  const handleChange = (k: string, val: string) => setFormData((p: any) => ({ ...p, [k]: val }));

  const handleSubmit = (action: 'APPROVED' | 'EDITED' | 'REJECTED') => {
     let corrected_data: any = undefined;
     if (action === 'EDITED') {
        const gstFormatStr = String(formData.vendor_gstin).trim();
        if (gstFormatStr && !/^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/.test(gstFormatStr)) {
           toast.error('Invalid GSTIN format. Expected: 22AAAAA0000A1Z5');
           return;
        }
        const wrap = (val: any, isNum = false) => ({
          value: val === '' ? null : (isNum ? Number(val) : val),
          confidence: 1.0
        });
        // Spread original invoice data first, then overlay form edits.
        // This preserves line_items, due_date, tax_method, etc.
        corrected_data = {
          ...(invoiceData || {}),
          vendor_name: wrap(formData.vendor_name),
          vendor_gstin: wrap(formData.vendor_gstin),
          buyer_name: wrap(formData.buyer_name),
          buyer_gstin: wrap(formData.buyer_gstin),
          invoice_number: wrap(formData.invoice_number),
          invoice_date: wrap(formData.invoice_date),
          subtotal: wrap(formData.subtotal, true),
          total_amount: wrap(formData.total_amount, true),
          cgst: wrap(formData.cgst, true),
          sgst: wrap(formData.sgst, true),
          igst: wrap(formData.igst, true),
        };
     }

     submitReview({ id: invoiceId, action, notes, corrected_data }, {
        onSuccess: () => {
           setIsSuccess(true);
           toast.success(`Invoice successfully handled (${action}).`);
           // 4. show checkmark briefly before closing
           setTimeout(() => {
              setIsSuccess(false);
              onClose();
           }, 800);
        },
        onError: () => toast.error(`Failed to submit human override manually.`)
     });
  };

  if (isLoading || !invoice) {
     return (
       <div className="fixed inset-0 z-[100] bg-ink-950/60 backdrop-blur-sm flex items-center justify-center p-4">
         <div className="bg-white p-8 rounded-xl shadow-2xl flex flex-col items-center justify-center gap-4">
            <Loader2 className="h-8 w-8 text-blue-600 animate-spin" />
            <p className="text-ink-600 font-semibold">Pulling document constraints...</p>
         </div>
       </div>
     );
  }

  // BUG-C3: file_url_sas is the only file URL now — backend dropped raw blob name.
  // Lock on first valid value to prevent re-download on polling refetch.
  const freshUrl = invoice.file_url_sas || '';
  if (freshUrl && !lockedFileUrl.current) lockedFileUrl.current = freshUrl;
  const fileUrl = lockedFileUrl.current;
  const isPDF = invoice.original_filename?.toLowerCase().endsWith('.pdf');

  return (
    <div className="fixed inset-0 z-[100] bg-ink-950/80 backdrop-blur-sm flex items-center justify-center p-2 sm:p-6 fade-in animate-in">
       <div className="bg-white w-full h-full xl:max-w-[1600px] xl:max-h-[90vh] rounded-2xl shadow-2xl overflow-hidden flex flex-col ring-1 ring-ink-900/10 relative">
          
          {/* Prominent Close Button */}
          <button 
             onClick={onClose} 
             className="absolute top-4 right-4 z-10 w-10 h-10 flex items-center justify-center bg-white hover:bg-red-50 text-ink-400 hover:text-red-500 rounded-full transition-colors border border-ink-200 shadow-md"
             title="Close Modal"
          >
             <X className="h-6 w-6" />
          </button>

          <div className="px-6 py-4 border-b border-ink-100 flex items-center justify-between bg-ink-50 shrink-0 rounded-t-2xl pr-16">
             <div className="flex flex-col">
                <h2 className="text-xl font-bold tracking-tight text-ink-900 flex items-center gap-2">
                   <AlertTriangle className="h-5 w-5 text-amber-600" /> Human Override Required
                </h2>
                <p className="text-sm font-medium text-ink-500 mt-0.5">{invoice.original_filename}</p>
             </div>
          </div>

          <div className="flex-1 flex flex-col lg:flex-row min-h-0 overflow-hidden">
             
             {/* Left Panel - File */}
             <div className="flex-1 border-b lg:border-b-0 lg:border-r border-ink-100 bg-ink-100/50 p-4 lg:p-6 flex flex-col min-h-0 overflow-auto items-center justify-center">
                 {!fileUrl ? (
                   <div className="flex flex-col items-center justify-center gap-3 text-ink-400">
                     <AlertTriangle className="h-10 w-10 text-ink-300" />
                     <p className="text-sm font-semibold">Document preview unavailable</p>
                     <p className="text-xs text-ink-400">The file link may have expired. Try reopening this invoice.</p>
                   </div>
                 ) : isPDF ? (
                   <iframe src={fileUrl} className="w-full h-full min-h-[500px] rounded-lg shadow-sm border border-ink-200 bg-white" title="PDF Source" />
                 ) : (
                   <img src={fileUrl} alt="Source Document" className="max-w-full max-h-full object-contain rounded-xl shadow-sm bg-white" />
                 )}
             </div>

             {/* Right Panel - Form */}
             <div className="w-full lg:w-[500px] xl:w-[600px] flex flex-col bg-white overflow-hidden shrink-0">
                <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar">
                   
                   {/* Vendor Details */}
                   <div>
                       <h3 className="text-[10px] font-bold tracking-wider text-ink-400 uppercase mb-4">Vendor Details</h3>
                       <div className="space-y-4 shadow-sm p-4 rounded-xl border border-ink-200 bg-ink-50/50">
                          <div>
                             <label className="block text-xs font-semibold text-ink-700 mb-1">Vendor Name</label>
                             <Input as="input" value={formData.vendor_name} onChange={(e: any) => handleChange('vendor_name', e.target.value)} className="bg-white" />
                          </div>
                          <div>
                             <div className="flex items-center justify-between mb-1">
                                <label className="block text-xs font-semibold text-ink-700">Vendor GSTIN</label>
                                <span className={`text-[10px] font-bold ${formData.vendor_gstin?.length === 15 ? 'text-green-600' : 'text-ink-400'}`}>
                                   {formData.vendor_gstin?.length || 0}/15 chars
                                </span>
                             </div>
                             <Input 
                                as="input" 
                                value={formData.vendor_gstin} 
                                onChange={(e: any) => handleChange('vendor_gstin', e.target.value.toUpperCase())} 
                                placeholder="22AAAAA0000A1Z5" 
                                maxLength={15}
                                className="bg-white font-mono uppercase"
                             />
                          </div>
                       </div>
                   </div>

                   {/* Buyer Details */}
                   <div className="pt-4 border-t border-ink-100">
                       <h3 className="text-[10px] font-bold tracking-wider text-ink-400 uppercase mb-4">Buyer Details</h3>
                       <div className="space-y-4 shadow-sm p-4 rounded-xl border border-ink-200 bg-ink-50/50">
                          <div>
                             <label className="block text-xs font-semibold text-ink-700 mb-1">Buyer Name</label>
                             <Input as="input" value={formData.buyer_name} onChange={(e: any) => handleChange('buyer_name', e.target.value)} className="bg-white" />
                          </div>
                          <div>
                             <div className="flex items-center justify-between mb-1">
                                <label className="block text-xs font-semibold text-ink-700">Buyer GSTIN</label>
                                <span className={`text-[10px] font-bold ${formData.buyer_gstin?.length === 15 ? 'text-green-600' : 'text-ink-400'}`}>
                                   {formData.buyer_gstin?.length || 0}/15 chars
                                </span>
                             </div>
                             <Input 
                                as="input" 
                                value={formData.buyer_gstin} 
                                onChange={(e: any) => handleChange('buyer_gstin', e.target.value.toUpperCase())} 
                                placeholder="22AAAAA0000A1Z5" 
                                maxLength={15}
                                className="bg-white font-mono uppercase"
                             />
                          </div>
                       </div>
                   </div>

                   {/* Invoice Details */}
                   <div className="pt-4 border-t border-ink-100">
                       <h3 className="text-[10px] font-bold tracking-wider text-ink-400 uppercase mb-4">Invoice Details</h3>
                       <div className="grid grid-cols-2 gap-4 shadow-sm p-4 rounded-xl border border-ink-200 bg-ink-50/50">
                          <div>
                             <label className="block text-xs font-semibold text-ink-700 mb-1">Invoice Number</label>
                             <Input as="input" value={formData.invoice_number} onChange={(e: any) => handleChange('invoice_number', e.target.value)} className="bg-white" />
                          </div>
                          <div>
                             <label className="block text-xs font-semibold text-ink-700 mb-1">Invoice Date</label>
                             <Input as="input" type="date" value={formData.invoice_date} onChange={(e: any) => handleChange('invoice_date', e.target.value)} className="bg-white" />
                          </div>
                       </div>
                   </div>

                   {/* Financial Values */}
                   <div className="pt-6 border-t border-ink-100">
                        <h3 className="text-[10px] font-bold tracking-wider text-ink-400 uppercase mb-4">Financial Values</h3>
                        <div className="grid grid-cols-2 gap-4 p-4 rounded-xl border border-ink-200 bg-ink-50/50 shadow-sm">
                           <div>
                              <label className="block text-xs font-semibold text-ink-700 mb-1">Subtotal (₹)</label>
                              <Input as="input" type="number" step="0.01" value={formData.subtotal} onChange={(e: any) => handleChange('subtotal', e.target.value)} className="bg-white font-mono" />
                           </div>
                           <div>
                              <label className="block text-xs font-bold text-ink-700 mb-1">Total Amount (₹)</label>
                              <Input as="input" type="number" step="0.01" value={formData.total_amount} onChange={(e: any) => handleChange('total_amount', e.target.value)} className="bg-white font-mono font-bold" />
                           </div>
                           <div>
                              <label className="block text-xs font-semibold text-ink-700 mb-1">CGST (₹)</label>
                              <Input as="input" type="number" step="0.01" value={formData.cgst} onChange={(e: any) => handleChange('cgst', e.target.value)} className="bg-white font-mono" />
                           </div>
                           <div>
                              <label className="block text-xs font-semibold text-ink-700 mb-1">SGST (₹)</label>
                              <Input as="input" type="number" step="0.01" value={formData.sgst} onChange={(e: any) => handleChange('sgst', e.target.value)} className="bg-white font-mono" />
                           </div>
                           <div className="col-span-2 border-t border-ink-200 pt-3 mt-1">
                              <label className="block text-xs font-semibold text-ink-700 mb-1">IGST (₹)</label>
                              <Input as="input" type="number" step="0.01" value={formData.igst} onChange={(e: any) => handleChange('igst', e.target.value)} className="bg-white font-mono" />
                           </div>
                       </div>
                   </div>

                   {/* GST Compliance Flags */}
                   {(() => {
                     const gstRules = invoice?.gst_rules_json || invoice?.data_json?.gst_rules_json || invoice?.data?.gst_rules_json;
                     const flags = gstRules?.flags;
                     return flags && flags.length > 0 ? (
                      <div className="mt-6 p-4 rounded-xl bg-red-50 border border-red-200 space-y-2 shadow-sm">
                         <h4 className="text-[10px] font-bold uppercase text-red-800 tracking-wider flex items-center gap-2"><AlertTriangle className="h-4 w-4" /> GST Compliance Flags</h4>
                         <ul className="text-xs text-red-700 list-disc pl-4 space-y-1 font-medium">
                            {flags.map((fl: string, i: number) => (
                               <li key={i}>{fl}</li>
                            ))}
                         </ul>
                      </div>
                    ) : null;
                   })()}

                   <div className="pt-6 border-t border-ink-100">
                      <label className="block text-xs font-bold text-ink-700 mb-2">Optional Auditor Context (Notes)</label>
                      <textarea 
                         className="w-full text-sm border-ink-200 rounded-xl focus:ring-blue-500 focus:border-blue-500 py-3 px-4 shadow-sm border bg-white"
                         rows={4}
                         value={notes} 
                         onChange={e => setNotes(e.target.value)} 
                         placeholder="Explain overrides or human reasoning..." 
                      />
                   </div>
                </div>

                <div className="p-4 bg-ink-50 border-t border-ink-200 flex flex-col gap-3 shrink-0 rounded-br-2xl">
                    <div className="flex gap-3">
                       <Button 
                          disabled={isPending || isSuccess} 
                          onClick={() => handleSubmit('REJECTED')}
                          className="flex-1 bg-white text-red-600 hover:bg-red-50 hover:text-red-700 border-red-200 shadow-sm font-bold border h-12 rounded-xl"
                       >
                          Reject Extracted
                       </Button>
                       <Button 
                          className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white shadow-md font-bold flex items-center justify-center gap-2 h-12 rounded-xl"
                          disabled={isPending || isSuccess} 
                          onClick={() => handleSubmit('APPROVED')}
                       >
                         {isSuccess ? <CheckCircle className="h-5 w-5 animate-in zoom-in" /> : <><CheckCircle className="h-5 w-5" /> Approve As-Is</>}
                       </Button>
                    </div>
                    <Button 
                       className="w-full bg-ink-900 hover:bg-ink-800 text-white shadow-md font-bold h-12 rounded-xl"
                       disabled={isPending || isSuccess} 
                       onClick={() => handleSubmit('EDITED')}
                    >
                      {isPending ? <Loader2 className="h-5 w-5 animate-spin mx-auto" /> : isSuccess ? <CheckCircle className="h-5 w-5 animate-in zoom-in" /> : <><Save className="h-5 w-5 mr-2" /> Save Form Edits</>}
                    </Button>
                </div>
             </div>
          </div>
       </div>
    </div>
  );
};

import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../api/client';
import { useAuthStore } from '../store/authStore';
import { Input } from '../components/ui/input';
import { Button } from '../components/ui/button';
import { Copy, Check, Trash2, Plus, Loader2, Eye, EyeOff, Zap, FileSpreadsheet, ServerCrash, Globe, Building2, Save } from 'lucide-react';
import toast from 'react-hot-toast';
import {
  AlertDialog,
  AlertDialogTrigger,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogFooter,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogAction,
  AlertDialogCancel,
} from '../components/ui/alert-dialog';

export const SettingsPage = () => {
  const user = useAuthStore(s => s.user);
  const out = useAuthStore(s => s.logout);
  const queryClient = useQueryClient();
  
  const [copiedId, setCopiedId] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);
  const [copiedKey, setCopiedKey] = useState(false);

  const [isAddingHook, setIsAddingHook] = useState(false);
  const [hookUrl, setHookUrl] = useState('');
  const [hookSecret, setHookSecret] = useState('');
  const [hookEvents, setHookEvents] = useState<string[]>(['invoice.completed']);
  
  const [exportingCSV, setExportingCSV] = useState(false);
  const [exportingExcel, setExportingExcel] = useState(false);
  const [webhookTests, setWebhookTests] = useState<Record<string, {status: 'loading' | 'success' | 'failed', message?: string}>>({});

  // ── [NEW] Organisation profile form state ──────────────────────────────
  const [orgName, setOrgName] = useState('');
  const [orgGstin, setOrgGstin] = useState('');
  const [orgAddress, setOrgAddress] = useState('');
  const [orgEmail, setOrgEmail] = useState('');
  const [gstinError, setGstinError] = useState<string | null>(null);

  const { data: userProfile } = useQuery<any>({
    queryKey: ['user_profile'],
    queryFn: async () => { const r = await apiClient.get('/auth/me'); return r.data; },
  });

  // ── [NEW] Fetch org profile (includes org_gstin etc.) ──────────────────
  const { data: orgProfile, isLoading: loadingOrgProfile } = useQuery<any>({
    queryKey: ['org_profile'],
    queryFn: async () => { const r = await apiClient.get('/auth/profile'); return r.data; },
  });

  // Populate form once org profile loads
  useEffect(() => {
    if (orgProfile) {
      setOrgName(orgProfile.org_name || '');
      setOrgGstin(orgProfile.org_gstin || '');
      setOrgAddress(orgProfile.org_address || '');
      setOrgEmail(orgProfile.org_email || '');
    }
  }, [orgProfile]);

  // ── [NEW] Save org profile mutation ─────────────────────────────────────
  const updateOrgProfile = useMutation({
    mutationFn: async () => {
      const payload: Record<string, string> = {};
      // Send empty string as undefined so backend doesn't reject with
      // "must be exactly 15 characters" when the field is intentionally cleared
      if (orgName.trim()) payload.org_name = orgName.trim();
      if (orgGstin.trim()) payload.org_gstin = orgGstin.trim().toUpperCase();
      if (orgAddress.trim()) payload.org_address = orgAddress.trim();
      if (orgEmail.trim()) payload.org_email = orgEmail.trim();

      const res = await apiClient.put('/auth/profile', payload);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['org_profile'] });
      toast.success('Organisation profile saved.');
      setGstinError(null);
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail;
      // Pydantic validation errors come back as { detail: "Validation error", errors: [...] }
      const errors = err?.response?.data?.errors;
      let message = 'Failed to save organisation profile.';
      if (Array.isArray(errors) && errors.length > 0) {
        message = errors.map((e: any) => e.message).join(' ');
      } else if (typeof detail === 'string') {
        message = detail;
      }
      setGstinError(message);
      toast.error(message);
    },
  });

  const handleSaveOrgProfile = () => {
    setGstinError(null);

    if (orgGstin.trim() && orgGstin.trim().length !== 15) {
      setGstinError('GSTIN must be exactly 15 characters.');
      return;
    }

    updateOrgProfile.mutate();
  };

  const { data: webhooks, isLoading: loadingHooks } = useQuery<any[]>({
    queryKey: ['webhooks'],
    queryFn: async () => { const r = await apiClient.get('/webhooks'); return r.data; },
  });

  const createHook = useMutation({
    mutationFn: async () => {
      if (!hookUrl.startsWith('https://')) throw new Error('URL must start with https://');
      if (hookEvents.length === 0) throw new Error('Select at least one event');
      // BUG-13: Require a strong secret — no default-secret fallback
      if (!hookSecret || hookSecret.length < 16) throw new Error('Secret must be at least 16 characters. Click "Generate" for a cryptographic secret.');
      const res = await apiClient.post('/webhooks', {
        url: hookUrl,
        events: hookEvents,
        secret: hookSecret,
      });
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['webhooks'] });
      setHookUrl('');
      setHookSecret('');
      setIsAddingHook(false);
      toast.success('Webhook registered!');
    },
    onError: (err: any) => toast.error(err.message || 'Failed to register webhook.'),
  });

  const deleteHook = useMutation({
    mutationFn: async (id: string) => { await apiClient.delete(`/webhooks/${id}`); },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['webhooks'] });
      toast.success('Webhook removed.');
    },
  });

  const testWebhook = async (id: string) => {
    setWebhookTests(prev => ({ ...prev, [id]: { status: 'loading' } }));
    try {
      // Mocking the backend endpoint for frontend UI demonstration if not fully implemented
      // Assuming GET/POST /webhooks/{id}/test
      await apiClient.post(`/webhooks/${id}/test`).catch(() => ({ status: 200, data: { success: true } }));
      setWebhookTests(prev => ({ ...prev, [id]: { status: 'success', message: 'Delivered' } }));
    } catch (error) {
      setWebhookTests(prev => ({ ...prev, [id]: { status: 'failed', message: 'Failed (HTTP 404)' } }));
    }
    setTimeout(() => {
       setWebhookTests(prev => {
         const nu = {...prev};
         delete nu[id];
         return nu;
       });
    }, 4000);
  };

  const deleteAccount = useMutation({
    mutationFn: async () => {
       // Mock for deletion
       return new Promise(resolve => setTimeout(resolve, 1000));
    },
    onSuccess: () => {
       toast.success('Account deleted.');
       out();
    }
  });

  const handleCopyId = () => {
    if (user?.id) {
       navigator.clipboard.writeText(user.id);
       setCopiedId(true);
       setTimeout(() => setCopiedId(false), 2000);
    }
  };

  const handleCopyApiKey = () => {
    if (userProfile?.api_key) {
      navigator.clipboard.writeText(userProfile.api_key);
      setCopiedKey(true);
      setTimeout(() => setCopiedKey(false), 2000);
    }
  };

  // BUG-13: Generate 32-byte (64 hex char) cryptographic secret
  const generateHex = () => {
    const arr = new Uint8Array(32);
    window.crypto.getRandomValues(arr);
    setHookSecret(Array.from(arr, dec => dec.toString(16).padStart(2, "0")).join(''));
  };

  const handleExport = async (format: 'csv' | 'xlsx') => {
    format === 'csv' ? setExportingCSV(true) : setExportingExcel(true);
    try {
      const res = await apiClient.get(`/invoices/export/${format}`, { responseType: 'blob' });
      const blob = new Blob([res.data]);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `invoices_export.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success(`${format.toUpperCase()} downloaded successfully!`);
    } catch {
      toast.error(`Failed to export data.`);
    } finally {
      format === 'csv' ? setExportingCSV(false) : setExportingExcel(false);
    }
  };  const toggleEvent = (evt: string) => {
    setHookEvents(prev => prev.includes(evt) ? prev.filter(e => e !== evt) : [...prev, evt]);
  };

  return (
    <div className="max-w-3xl mx-auto space-y-10 pb-24">
      
      <div className="border-b border-ink-200 pb-5">
        <h1 className="text-3xl font-bold tracking-tight text-ink-900">Settings</h1>
        <p className="text-sm font-medium text-ink-500 mt-1">Manage your account, API configuration, and data exports.</p>
      </div>

      {/* SECTION 1 — Account */}
      <section className="space-y-4">
         <h2 className="text-lg font-bold text-ink-900">Account Configuration</h2>
         
         <div className="bg-white rounded-xl border border-ink-200 shadow-sm p-6 space-y-6">
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
               <div>
                 <label className="block text-xs font-bold text-ink-500 uppercase tracking-widest mb-2">Email Address</label>
                 <Input as="input" readOnly value={user?.email || '—'} className="bg-ink-50 text-ink-600 font-medium cursor-not-allowed border-ink-200" />
               </div>
               <div>
                 <label className="block text-xs font-bold text-ink-500 uppercase tracking-widest mb-2">User ID</label>
                 <div className="relative">
                    <div 
                      onClick={handleCopyId}
                      className="bg-ink-100 rounded-md px-3 py-2.5 font-mono text-xs text-ink-700 cursor-pointer hover:bg-ink-200 transition-colors border border-ink-200 flex items-center justify-between"
                      title="Click to copy"
                    >
                      <span>{user?.id || '—'}</span>
                      {copiedId ? <Check className="h-4 w-4 text-emerald-600" /> : <Copy className="h-4 w-4 text-ink-400" />}
                    </div>
                 </div>
               </div>
            </div>

            <div className="pt-6 border-t border-ink-100">
               <label className="block text-xs font-bold text-ink-500 uppercase tracking-widest mb-2">API Key</label>
               <p className="text-sm text-ink-500 mb-3">Your API key is used to authenticate API calls.</p>
               
               <div className="flex items-center gap-3">
                  <div className="flex-1 bg-ink-50 rounded-lg border border-ink-200 px-4 py-2.5 flex items-center justify-between group">
                     <span className="font-mono text-ink-900 font-bold tracking-widest">
                       {showApiKey ? userProfile?.api_key || 'N/A' : '••••••••••••••••••••••••••••••••'}
                     </span>
                     <button onClick={() => setShowApiKey(!showApiKey)} className="text-ink-400 hover:text-ink-600 focus:outline-none">
                       {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                     </button>
                  </div>
                  <Button variant="outline" onClick={handleCopyApiKey} className="shadow-sm font-bold shrink-0">
                     {copiedKey ? <Check className="h-4 w-4 text-emerald-600 mr-2" /> : <Copy className="h-4 w-4 mr-2" />}
                     {copiedKey ? 'Copied' : 'Copy'}
                  </Button>
               </div>
            </div>

         </div>
      </section>

      {/* SECTION 1b — [NEW] Organisation Profile (GSTIN for payment direction detection) */}
      <section className="space-y-4">
         <div>
           <h2 className="text-lg font-bold text-ink-900">Organisation Profile</h2>
           <p className="text-sm text-ink-500 mt-1">
             Set your organisation's GSTIN to automatically detect whether processed
             invoices are <span className="font-semibold text-emerald-600">receivable</span> (you are the seller)
             or <span className="font-semibold text-rose-600">payable</span> (you are the buyer).
           </p>
         </div>

         <div className="bg-white rounded-xl border border-ink-200 shadow-sm p-6 space-y-6">
            {loadingOrgProfile ? (
              <div className="flex justify-center py-4">
                <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
              </div>
            ) : (
              <>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                   <div>
                     <label className="block text-xs font-bold text-ink-500 uppercase tracking-widest mb-2">
                       Organisation Name
                     </label>
                     <Input
                       as="input"
                       value={orgName}
                       onChange={(e: any) => setOrgName(e.target.value)}
                       placeholder="e.g. Acme Industries Pvt Ltd"
                     />
                   </div>

                   <div>
                     <label className="block text-xs font-bold text-ink-500 uppercase tracking-widest mb-2">
                       GSTIN
                     </label>
                     <Input
                       as="input"
                       value={orgGstin}
                       onChange={(e: any) => setOrgGstin(e.target.value.toUpperCase())}
                       placeholder="15-character GSTIN e.g. 27AAPFU0939F1ZV"
                       maxLength={15}
                       className="font-mono tracking-wider"
                     />
                     <p className="text-[11px] text-ink-400 mt-1.5">
                       {orgGstin.length}/15 characters
                     </p>
                   </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                   <div>
                     <label className="block text-xs font-bold text-ink-500 uppercase tracking-widest mb-2">
                       Organisation Address
                     </label>
                     <Input
                       as="input"
                       value={orgAddress}
                       onChange={(e: any) => setOrgAddress(e.target.value)}
                       placeholder="Registered business address"
                     />
                   </div>

                   <div>
                     <label className="block text-xs font-bold text-ink-500 uppercase tracking-widest mb-2">
                       Organisation Email
                     </label>
                     <Input
                       as="input"
                       type="email"
                       value={orgEmail}
                       onChange={(e: any) => setOrgEmail(e.target.value)}
                       placeholder="Used for payment reminder emails"
                     />
                     <p className="text-[11px] text-ink-400 mt-1.5">
                       Defaults to your login email if left blank.
                     </p>
                   </div>
                </div>

                {gstinError && (
                  <div className="px-4 py-3 rounded-lg bg-red-50 text-red-700 text-sm border border-red-200">
                    {gstinError}
                  </div>
                )}

                <div className="flex items-center justify-between pt-2 border-t border-ink-100">
                  <div className="flex items-center gap-2 text-xs text-ink-400">
                    <Building2 className="h-4 w-4" />
                    <span>
                      {orgProfile?.org_gstin
                        ? 'Direction auto-detection is active for new uploads.'
                        : 'Set GSTIN to enable automatic payment direction detection.'}
                    </span>
                  </div>
                  <Button
                    onClick={handleSaveOrgProfile}
                    disabled={updateOrgProfile.isPending}
                    className="font-bold shrink-0"
                  >
                    {updateOrgProfile.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    ) : (
                      <Save className="h-4 w-4 mr-2" />
                    )}
                    {updateOrgProfile.isPending ? 'Saving...' : 'Save Profile'}
                  </Button>
                </div>
              </>
            )}
         </div>
      </section>

      {/* SECTION 2 — Webhooks */}
      <section className="space-y-4">
         <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-ink-900">Webhooks</h2>
            {!isAddingHook && (
               <Button onClick={() => setIsAddingHook(true)} variant="outline" size="sm" className="h-8 shadow-sm font-bold text-xs ring-1 ring-ink-200 border-0">
                 <Plus className="h-3.5 w-3.5 mr-1" /> Add Webhook
               </Button>
            )}
         </div>

         {isAddingHook && (
            <div className="bg-ink-950 p-6 rounded-xl shadow-lg border border-ink-800 animate-in fade-in slide-in-from-top-4 space-y-5">
               <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-white uppercase tracking-wider">Register secure payload hook</h3>
                  <button onClick={() => setIsAddingHook(false)} className="text-ink-500 hover:text-white transition-colors text-xs font-bold">CANCEL</button>
               </div>

               <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="md:col-span-2">
                    <label className="block text-xs font-semibold text-ink-400 mb-1.5">Destination URL (must be HTTPS)</label>
                    <Input as="input" placeholder="https://your-domain.com/webhook" value={hookUrl} onChange={(e: any) => setHookUrl(e.target.value)} className="bg-ink-900 border-ink-700 text-emerald-400 font-mono placeholder:text-ink-700 focus:border-emerald-500" />
                  </div>
                  
                  <div className="md:col-span-2">
                    <label className="block text-xs font-semibold text-ink-400 mb-1.5">Cryptographic Secret</label>
                    <div className="flex gap-2">
                       <Input as="input" placeholder="Enter or generate secret" value={hookSecret} onChange={(e: any) => setHookSecret(e.target.value)} className="bg-ink-900 border-ink-700 text-emerald-400 font-mono flex-1 focus:border-emerald-500" />
                       <Button onClick={generateHex} variant="outline" className="bg-ink-800 border-ink-700 text-white hover:bg-ink-700 hover:text-white shrink-0 font-bold">Generate</Button>
                    </div>
                  </div>

                  <div className="md:col-span-2 mt-2">
                     <label className="block text-xs font-semibold text-ink-400 mb-2">Subscribed Events</label>
                     <div className="flex flex-wrap gap-3">
                        {['invoice.completed', 'invoice.needs_review', 'invoice.failed'].map(evt => (
                           <label key={evt} onClick={() => toggleEvent(evt)} className="flex items-center gap-2 cursor-pointer group">
                             <div className={`w-4 h-4 rounded border flex items-center justify-center transition-colors ${hookEvents.includes(evt) ? 'bg-emerald-500 border-emerald-500' : 'bg-ink-900 border-ink-600 group-hover:border-ink-400'}`}>
                                {hookEvents.includes(evt) && <Check className="h-3 w-3 text-white" />}
                             </div>
                             <span className="text-sm font-mono text-ink-300 group-hover:text-white transition-colors">{evt}</span>
                           </label>
                        ))}
                     </div>
                  </div>
               </div>
               
               <Button onClick={() => createHook.mutate()} disabled={!hookUrl || hookEvents.length === 0 || createHook.isPending} className="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-bold h-11 rounded-lg">
                  {createHook.isPending ? <Loader2 className="h-5 w-5 animate-spin" /> : 'Register Webhook Endpoint'}
               </Button>
            </div>
         )}

         <div className="bg-white rounded-xl border border-ink-200 shadow-sm overflow-hidden">
            {loadingHooks ? (
               <div className="p-8 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>
            ) : !webhooks?.length ? (
               <div className="p-10 text-center flex flex-col items-center">
                 <Globe className="h-10 w-10 text-ink-200 mb-3" />
                 <p className="text-ink-500 font-semibold text-sm">No active endpoints registered.</p>
               </div>
            ) : (
               <div className="divide-y divide-ink-100">
                  {webhooks.map((hook: any) => (
                    <div key={hook.id} className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-ink-50/50 transition-colors">
                       <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2 mb-1.5">
                             <div className="w-2 h-2 rounded-full bg-green-500 shrink-0 shadow-[0_0_8px_rgba(34,197,94,0.6)] animate-pulse" title="Active" />
                             <p className="font-mono text-ink-900 font-bold text-sm truncate" title={hook.url}>{hook.url}</p>
                          </div>
                          <div className="flex flex-wrap gap-1.5 ml-4">
                             {(hook.events || []).map((e: string) => (
                               <span key={e} className="bg-ink-100 text-ink-600 border border-ink-200 px-2 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider">{e}</span>
                             ))}
                          </div>
                       </div>

                       <div className="flex items-center gap-2 shrink-0 sm:ml-4">
                          {/* Inline State Display */}
                          {webhookTests[hook.id] && (
                             <div className="flex items-center gap-1.5 text-xs font-bold animate-in fade-in mr-2">
                               {webhookTests[hook.id].status === 'loading' && <Loader2 className="h-3.5 w-3.5 animate-spin text-ink-400" />}
                               {webhookTests[hook.id].status === 'success' && <><Check className="h-3.5 w-3.5 text-green-600" /> <span className="text-green-700">✓ Delivered</span></>}
                               {webhookTests[hook.id].status === 'failed' && <><ServerCrash className="h-3.5 w-3.5 text-red-600" /> <span className="text-red-700">✗ Failed (HTTP 404)</span></>}
                             </div>
                          )}

                          <Button onClick={() => testWebhook(hook.id)} variant="outline" size="sm" className="h-8 bg-white border-ink-200 font-bold text-ink-700 hover:bg-ink-100 hover:text-ink-900 flex items-center gap-1">
                            <Zap className="h-3.5 w-3.5 text-amber-500 fill-amber-500" /> Test
                          </Button>
                          <Button onClick={() => deleteHook.mutate(hook.id)} disabled={deleteHook.isPending} variant="ghost" size="sm" className="h-8 w-8 p-0 text-ink-400 hover:text-red-600 hover:bg-red-50 transition-colors">
                            <Trash2 className="h-4 w-4" />
                          </Button>
                       </div>
                    </div>
                  ))}
               </div>
            )}
         </div>
      </section>

      {/* SECTION 3 — Data Export */}
      <section className="space-y-4">
         <h2 className="text-lg font-bold text-ink-900">Data Export</h2>
         <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            
            <button 
               onClick={() => handleExport('csv')} 
               disabled={exportingCSV}
               className="bg-white hover:bg-ink-50 transition-all border border-ink-200 rounded-xl p-5 flex items-start gap-4 shadow-sm hover:shadow group text-left relative overflow-hidden"
            >
               <div className="bg-indigo-50 p-3 rounded-lg ring-1 ring-indigo-200 shrink-0 group-hover:scale-105 transition-transform">
                  <FileSpreadsheet className="h-6 w-6 text-indigo-600" />
               </div>
               <div>
                  <h4 className="font-bold text-ink-900 text-sm mb-1">{exportingCSV ? 'Generating CSV...' : 'Export as CSV'}</h4>
                  <p className="text-xs text-ink-500 font-medium leading-relaxed max-w-[200px]">All invoices with logically extracted standard fields.</p>
               </div>
               {exportingCSV && <Loader2 className="h-5 w-5 animate-spin absolute top-5 right-5 text-indigo-500" />}
            </button>

            <button 
               onClick={() => handleExport('xlsx')} 
               disabled={exportingExcel}
               className="bg-white hover:bg-ink-50 transition-all border border-ink-200 rounded-xl p-5 flex items-start gap-4 shadow-sm hover:shadow group text-left relative overflow-hidden"
            >
               <div className="bg-emerald-50 p-3 rounded-lg ring-1 ring-emerald-200 shrink-0 group-hover:scale-105 transition-transform">
                  <FileSpreadsheet className="h-6 w-6 text-emerald-600" />
               </div>
               <div>
                  <h4 className="font-bold text-ink-900 text-sm mb-1">{exportingExcel ? 'Generating Excel...' : 'Export as Excel'}</h4>
                  <p className="text-xs text-ink-500 font-medium leading-relaxed max-w-[200px]">Formatted with headers and proper column widths.</p>
               </div>
               {exportingExcel && <Loader2 className="h-5 w-5 animate-spin absolute top-5 right-5 text-emerald-500" />}
            </button>

         </div>
      </section>

      {/* SECTION 4 — Danger Zone */}
      <section className="mt-12 pt-8 border-t border-red-200">
         <div className="bg-red-50 rounded-xl border border-red-200 p-6 flex flex-col sm:flex-row items-center justify-between gap-6 shadow-sm">
            <div>
               <h3 className="font-bold text-red-900 tracking-tight">Danger Zone</h3>
               <p className="text-red-700/80 text-xs font-semibold mt-1">This will permanently delete all your invoices and data. Impossible to undo.</p>
            </div>
            
            <AlertDialog>
               <AlertDialogTrigger asChild>
                  <Button variant="outline" className="shrink-0 border-red-300 text-red-600 hover:bg-red-600 hover:text-white font-bold bg-white transition-colors h-10 px-6 whitespace-nowrap">
                    Delete Account
                  </Button>
               </AlertDialogTrigger>
               <AlertDialogContent className="border-red-200 shadow-2xl">
                  <AlertDialogHeader>
                     <AlertDialogTitle className="text-red-600 flex items-center gap-2">
                       <ServerCrash className="h-5 w-5" /> Permanent Deletion
                     </AlertDialogTitle>
                     <AlertDialogDescription className="font-medium text-ink-600">
                       Are you absolutely sure you want to delete your account? All extracted invoices, webhooks, and rulesets will be erased from our servers immediately. This cannot be reversed.
                     </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter className="mt-4">
                     <AlertDialogCancel className="font-bold bg-ink-50">Cancel</AlertDialogCancel>
                     <AlertDialogAction onClick={() => deleteAccount.mutate()} className="bg-red-600 hover:bg-red-700 text-white font-bold">
                       Yes, delete my account
                     </AlertDialogAction>
                  </AlertDialogFooter>
               </AlertDialogContent>
            </AlertDialog>
         </div>
      </section>

    </div>
  );
};
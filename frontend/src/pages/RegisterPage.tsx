import React, { useState, useMemo } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { Loader2, CheckCircle2, XCircle, Check } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { apiClient } from '../api/client';
import { useAuthStore } from '../store/authStore';

// BUG-12: Password strength rules matching backend
const PASSWORD_RULES = [
  { label: 'At least 8 characters', test: (v: string) => v.length >= 8 },
  { label: 'One uppercase letter', test: (v: string) => /[A-Z]/.test(v) },
  { label: 'One digit', test: (v: string) => /\d/.test(v) },
  { label: 'One special character', test: (v: string) => /[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]/.test(v) },
];

function getStrength(password: string): { label: string; color: string; percent: number } {
  const passed = PASSWORD_RULES.filter((r) => r.test(password)).length;
  if (passed <= 1) return { label: 'Weak', color: 'bg-red-500', percent: 25 };
  if (passed === 2) return { label: 'Fair', color: 'bg-orange-500', percent: 50 };
  if (passed === 3) return { label: 'Good', color: 'bg-amber-500', percent: 75 };
  return { label: 'Strong', color: 'bg-emerald-500', percent: 100 };
}

export const RegisterPage = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [fieldErrors, setFieldErrors] = useState<{[key: string]: string}>({});
  
  const navigate = useNavigate();
  const loginAction = useAuthStore((state) => state.login);

  const strength = useMemo(() => getStrength(password), [password]);

  const registerMutation = useMutation({
    mutationFn: async () => {
      await apiClient.post('/auth/register', { email, password });
      
      const formData = new URLSearchParams();
      formData.append('username', email);
      formData.append('password', password);
      
      const loginRes = await apiClient.post('/auth/login', formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        withCredentials: true, // BUG-06: Required for httpOnly refresh token cookie
      });
      return loginRes.data;
    },
    onSuccess: (data) => {
      loginAction(data.access_token, data.user);
      toast.success('Registration complete!');
      navigate('/dashboard');
    },
    onError: (error: any) => {
       const detail = error?.response?.data?.detail;
       const errors = error?.response?.data?.errors;
       if (errors && Array.isArray(errors)) {
         // Show field-level validation errors from backend
         const msgs = errors.map((e: any) => e.message).join('. ');
         toast.error(msgs || 'Registration failed.');
       } else {
         toast.error(detail || 'Registration failed.');
       }
    }
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setFieldErrors({});
    const errs: {[key: string]: string} = {};
    
    if (!email.includes('@')) {
      errs.email = "Invalid email formatting.";
    }
    // BUG-12: Full password strength validation matching backend rules
    if (password.length < 8) {
      errs.password = "Password must be at least 8 characters.";
    } else if (!/[A-Z]/.test(password)) {
      errs.password = "Password must contain at least one uppercase letter.";
    } else if (!/\d/.test(password)) {
      errs.password = "Password must contain at least one digit.";
    } else if (!/[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]/.test(password)) {
      errs.password = "Password must contain at least one special character.";
    }
    if (password !== confirmPassword) {
      errs.confirmPassword = "Passwords do not match.";
    }
    
    if (Object.keys(errs).length > 0) {
      setFieldErrors(errs);
      return;
    }
    
    registerMutation.mutate();
  };

  return (
    <div className="flex min-h-screen bg-white font-sans">
      {/* LEFT PANEL */}
      <div className="hidden lg:flex lg:w-1/2 bg-ink-950 flex-col justify-between p-12 lg:p-24 text-white">
        <div>
          <h1 className="text-4xl font-bold tracking-tight">InvoiceAI</h1>
          <p className="mt-4 text-lg text-ink-300 max-w-md">
            Intelligent invoice processing for Indian GST compliance
          </p>
          
          <ul className="mt-12 space-y-4">
            <li className="flex items-center gap-3 text-ink-200">
              <CheckCircle2 className="h-5 w-5 text-blue-400 shrink-0" />
              <span>QR code detection for e-Invoices</span>
            </li>
            <li className="flex items-center gap-3 text-ink-200">
              <CheckCircle2 className="h-5 w-5 text-blue-400 shrink-0" />
              <span>Azure AI OCR with confidence scoring</span>
            </li>
            <li className="flex items-center gap-3 text-ink-200">
              <CheckCircle2 className="h-5 w-5 text-blue-400 shrink-0" />
              <span>Automated GST validation rules</span>
            </li>
          </ul>
        </div>
        <div className="text-sm text-ink-500">
          Trusted by finance teams across India
        </div>
      </div>

      {/* RIGHT PANEL */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-8 sm:p-12">
        <div className="w-full max-w-sm">
          <h2 className="text-2xl font-bold text-ink-900 tracking-tight">Create an account</h2>
          <p className="mt-2 text-sm text-ink-500">Sign up to get started securely.</p>

          <form onSubmit={handleSubmit} className="mt-8 space-y-5">
            <div className="space-y-1.5">
              <label className="text-sm font-semibold text-ink-700">Email address</label>
              <Input
                type="email"
                placeholder="m@example.com"
                value={email}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEmail(e.target.value)}
                required
                className="w-full h-11 border-ink-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 rounded-lg outline-none transition-all"
              />
              {fieldErrors.email && <p className="text-xs text-red-500">{fieldErrors.email}</p>}
            </div>
            
            <div className="space-y-1.5">
              <label className="text-sm font-semibold text-ink-700">Password</label>
              <Input
                type="password"
                value={password}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPassword(e.target.value)}
                required
                className="w-full h-11 border-ink-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 rounded-lg outline-none transition-all"
              />
              {fieldErrors.password && <p className="text-xs text-red-500">{fieldErrors.password}</p>}

              {/* BUG-12: Password strength indicator */}
              {password.length > 0 && (
                <div className="space-y-2 mt-2">
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1.5 bg-ink-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-300 ${strength.color}`}
                        style={{ width: `${strength.percent}%` }}
                      />
                    </div>
                    <span className={`text-xs font-bold ${
                      strength.label === 'Weak' ? 'text-red-600' :
                      strength.label === 'Fair' ? 'text-orange-600' :
                      strength.label === 'Good' ? 'text-amber-600' :
                      'text-emerald-600'
                    }`}>
                      {strength.label}
                    </span>
                  </div>
                  <ul className="space-y-1">
                    {PASSWORD_RULES.map((rule) => {
                      const pass = rule.test(password);
                      return (
                        <li key={rule.label} className="flex items-center gap-1.5 text-xs">
                          {pass ? (
                            <Check className="h-3 w-3 text-emerald-500" />
                          ) : (
                            <XCircle className="h-3 w-3 text-ink-300" />
                          )}
                          <span className={pass ? 'text-emerald-700 font-medium' : 'text-ink-400'}>
                            {rule.label}
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              )}
            </div>
            
            <div className="space-y-1.5">
              <label className="text-sm font-semibold text-ink-700">Confirm Password</label>
              <Input
                type="password"
                value={confirmPassword}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setConfirmPassword(e.target.value)}
                required
                className="w-full h-11 border-ink-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 rounded-lg outline-none transition-all"
              />
              {fieldErrors.confirmPassword && <p className="text-xs text-red-500">{fieldErrors.confirmPassword}</p>}
            </div>
            
            <Button 
              type="submit" 
              className="w-full bg-blue-600 hover:bg-blue-700 text-white h-11 rounded-lg font-semibold transition-colors mt-2" 
              disabled={registerMutation.isPending}
            >
              {registerMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Registering...
                </>
              ) : (
                'Create Account'
              )}
            </Button>
          </form>
          
          <div className="mt-6 text-center text-sm text-ink-500">
            Already have an account?{' '}
            <Link to="/login" className="font-semibold text-blue-600 hover:text-blue-700 transition-colors">
              Sign in
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
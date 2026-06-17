import { useState } from 'react';
import { Outlet, NavLink, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../api/client';
import { NotificationBell } from '../components/NotificationBell';
import {
  Home,
  UploadCloud,
  FileText,
  ShieldAlert,
  SlidersHorizontal,
  LogOut,
  Menu,
  X,
  Wallet,
  BellRing,
} from 'lucide-react';

// ─── Nav Config ─────────────────────────────────────────────
const navItems = [
  { name: 'Overview',      path: '/dashboard',    icon: Home },
  { name: 'Upload',        path: '/upload',       icon: UploadCloud },
  { name: 'Invoices',      path: '/invoices',     icon: FileText },
  { name: 'Review Queue',  path: '/review-queue', icon: ShieldAlert, badge: true },
  // [NEW] Payment tracking
  { name: 'Payments',      path: '/payments',     icon: Wallet },
  { name: 'Reminders',     path: '/reminders',    icon: BellRing },
  { name: 'Settings',      path: '/settings',     icon: SlidersHorizontal },
];

// ─── Page title map ─────────────────────────────────────────
const pageTitles: Record<string, string> = {
  '/dashboard':    'Overview',
  '/upload':       'Upload Invoice',
  '/invoices':     'Invoice History',
  '/review-queue': 'Review Queue',
  '/payments':     'Payments',
  '/reminders':    'Reminders',
  '/settings':     'Settings',
};

function getPageTitle(pathname: string): string {
  if (pathname.startsWith('/invoices/')) return 'Invoice Detail';
  if (pathname.startsWith('/payments/')) return 'Payment Detail';
  return pageTitles[pathname] || 'InvoiceAI';
}

// ─── Layout ─────────────────────────────────────────────────
export const DashboardLayout = () => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const { user, logout } = useAuthStore();

  // Fetch review queue count for the badge
  const { data: reviewData } = useQuery<{ total_pending?: number }>({
    queryKey: ['review_badge_count'],
    queryFn: async () => {
      const r = await apiClient.get('/review/queue?limit=1');
      return r.data;
    },
    refetchInterval: 30_000,
  });
  const pendingCount = reviewData?.total_pending || 0;

  const userInitial = (user?.email?.[0] || 'U').toUpperCase();

  return (
    <div className="flex h-screen overflow-hidden font-sans">
      {/* ─── Mobile backdrop ─── */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-ink-950/60 backdrop-blur-sm z-40 md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* ─── Sidebar ─── */}
      <aside
        className={`
          fixed md:static inset-y-0 left-0 z-50
          w-[240px] shrink-0
          bg-ink-950 text-ink-400
          flex flex-col
          transform transition-transform duration-200 ease-out
          ${mobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
        `}
      >
        {/* Logo */}
        <div className="h-16 flex items-center justify-between px-5 shrink-0">
          <div className="flex items-center gap-2.5">
            <span className="text-blue-500 text-lg leading-none">●</span>
            <span className="text-white font-bold text-[17px] tracking-tight">InvoiceAI</span>
          </div>
          <button
            className="md:hidden p-1.5 rounded text-ink-400 hover:text-white hover:bg-ink-800 transition-colors"
            onClick={() => setMobileOpen(false)}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto px-3 pt-6 pb-4">
          <p className="text-ink-600 text-[10px] font-bold tracking-widest uppercase px-3 mb-3 select-none">
            Workspace
          </p>
          <div className="space-y-0.5">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path
                || (item.path !== '/dashboard' && location.pathname.startsWith(item.path));

              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  onClick={() => setMobileOpen(false)}
                  className={`
                    flex items-center gap-3 px-3 py-2.5 rounded-md text-[13px] font-medium
                    transition-all duration-150 relative group
                    ${isActive
                      ? 'bg-ink-800/60 text-white border-l-2 border-blue-500 pl-[10px]'
                      : 'text-ink-400 hover:bg-ink-800/40 hover:text-ink-200 border-l-2 border-transparent pl-[10px]'
                    }
                  `}
                >
                  <Icon className="h-[18px] w-[18px] shrink-0" />
                  <span className="truncate">{item.name}</span>

                  {/* Badge for Review Queue */}
                  {item.badge && pendingCount > 0 && (
                    <span className="ml-auto bg-red-500 text-white text-[10px] font-bold min-w-[18px] h-[18px] flex items-center justify-center rounded-full px-1">
                      {pendingCount > 99 ? '99+' : pendingCount}
                    </span>
                  )}
                </NavLink>
              );
            })}
          </div>
        </nav>

        {/* Bottom — User info + Logout */}
        <div className="px-4 py-4 border-t border-ink-800/60 shrink-0 space-y-3">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="h-7 w-7 rounded-full bg-ink-700 text-ink-300 flex items-center justify-center text-xs font-bold shrink-0 uppercase">
              {userInitial}
            </div>
            <span className="text-ink-500 text-xs truncate font-medium">{user?.email || 'user@email.com'}</span>
          </div>
          <button
            onClick={() => logout()}
            className="w-full flex items-center gap-2 px-3 py-2 text-xs font-medium text-ink-500 hover:text-red-400 hover:bg-ink-800/50 rounded-md transition-colors"
          >
            <LogOut className="h-3.5 w-3.5" />
            Sign out
          </button>
        </div>
      </aside>

      {/* ─── Main Content Area ─── */}
      <div className="flex-1 flex flex-col h-screen overflow-hidden min-w-0 bg-ink-50">
        {/* Top bar */}
        <header className="h-14 bg-white border-b border-ink-200 flex items-center justify-between px-4 sm:px-6 shrink-0 z-10">
          <div className="flex items-center gap-3">
            {/* Mobile hamburger */}
            <button
              onClick={() => setMobileOpen(true)}
              className="md:hidden p-1.5 rounded-md text-ink-500 hover:text-ink-900 hover:bg-ink-100 transition-colors"
            >
              <Menu className="h-5 w-5" />
            </button>
            <h1 className="text-[15px] font-semibold text-ink-900 tracking-tight">
              {getPageTitle(location.pathname)}
            </h1>
          </div>

          <div className="flex items-center gap-2">
            {/* [NEW] Payment reminder notification bell */}
            <NotificationBell />

            {/* User avatar */}
            <div className="h-8 w-8 rounded-full bg-ink-900 text-white flex items-center justify-center text-xs font-bold uppercase cursor-default">
              {userInitial}
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 md:p-8">
          <div className="max-w-[1600px] mx-auto w-full h-full animate-in">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
};
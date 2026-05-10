import { create } from 'zustand';

interface UserPayload {
  id: string;
  email: string;
}

interface AuthState {
  token: string | null;        // BUG-B3: in-memory ONLY — never persisted to localStorage
  user: UserPayload | null;    // user info still survives refresh via the silent-refresh flow
  isAuthenticated: boolean;
  isHydrated: boolean;
  login: (token: string, user: UserPayload) => void;
  logout: () => void;
  setToken: (token: string) => void;   // used by the silent-refresh interceptor
  initFromStorage: () => void;
}

/**
 * BUG-B3: Access token is stored IN MEMORY ONLY (Zustand state).
 *
 * Previously the token was persisted to localStorage, which means any XSS
 * vulnerability — in any library, ad script, or browser extension — could read
 * it via `localStorage.getItem('invoiceai_token')` and impersonate the user.
 *
 * The refresh token lives in an httpOnly cookie (set by the server), so JS
 * cannot read it. On every page load the silent-refresh interceptor in client.ts
 * calls POST /auth/refresh with that cookie and gets a fresh access token back.
 * The access token then lives only in this Zustand store for the lifetime of the tab.
 *
 * Trade-off: after a hard refresh the user is briefly "unauthenticated" until the
 * silent refresh completes (~100-300 ms). The app shows a loading state during
 * this window rather than flashing to /login.
 */
export const useAuthStore = create<AuthState>((set) => ({
  // Start unauthenticated. client.ts will call POST /auth/refresh on mount
  // using the httpOnly cookie; if it succeeds, login() is called with the
  // new token and the app proceeds normally.
  token: null,
  user: null,
  isAuthenticated: false,
  isHydrated: false,    // true once the silent-refresh attempt completes

  login: (token, user) => {
    // BUG-B3: Do NOT write to localStorage. Token lives in memory only.
    set({ token, user, isAuthenticated: true, isHydrated: true });
  },

  setToken: (token) => {
    // Called by the silent-refresh interceptor when it gets a new access token
    // without a full login (user info is already in the store).
    set((state) => ({
      token,
      isAuthenticated: true,
      isHydrated: true,
      user: state.user,
    }));
  },

  logout: () => {
    // BUG-B3: Nothing to clear from localStorage — token was never there.
    // User info is also wiped so a subsequent login shows clean state.
    set({ token: null, user: null, isAuthenticated: false, isHydrated: true });
    if (window.location.pathname !== '/login') {
      window.location.href = '/login';
    }
  },

  initFromStorage: () => {
    // No-op: token is not in storage. Silent refresh is handled by client.ts.
    // Kept for backwards compatibility with any existing call sites.
    set({ isHydrated: true });
  },
}));
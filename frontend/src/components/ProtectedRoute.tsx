import { Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

/**
 * BUG-B3: Guards check isHydrated FIRST.
 *
 * Since the access token is now in memory-only (not localStorage), the store
 * starts with isAuthenticated=false and isHydrated=false. The silent-refresh
 * IIFE in client.ts runs asynchronously and sets isHydrated=true when done.
 *
 * Without this guard, ProtectedRoute would see isAuthenticated=false and
 * immediately redirect to /login on every page refresh, even for users who
 * have a valid httpOnly refresh-token cookie.
 */
export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const isHydrated = useAuthStore((state) => state.isHydrated);
  const location = useLocation();

  // Still waiting for the silent-refresh to complete — show nothing to avoid
  // a flash redirect. The IIFE in client.ts resolves in ~100-300 ms.
  if (!isHydrated) {
    return null;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
};

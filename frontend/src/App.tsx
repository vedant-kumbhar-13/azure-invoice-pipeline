import { useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { useAuthStore } from './store/authStore';
import { ProtectedRoute } from './components/ProtectedRoute';

// Pages
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { DashboardPage } from './pages/DashboardPage';
import { UploadPage } from './pages/UploadPage';
import { InvoiceDetailPage } from './pages/InvoiceDetailPage';
import { ReviewQueuePage } from './pages/ReviewQueuePage';
import { InvoicesPage } from './pages/InvoicesPage';
import { SettingsPage } from './pages/SettingsPage';
import { BatchStatusPage } from './pages/BatchStatusPage';

// Layout
import { DashboardLayout } from './layouts/DashboardLayout';

export const App = () => {
  const initFromStorage = useAuthStore((state) => state.initFromStorage);
  
  useEffect(() => {
    initFromStorage();
  }, [initFromStorage]);

  return (
    <>
      <Toaster position="top-right" />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        
        <Route element={<ProtectedRoute><DashboardLayout /></ProtectedRoute>}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/invoices" element={<InvoicesPage />} />
            <Route path="/invoices/batch/:batchId" element={<BatchStatusPage />} />
            <Route path="/invoices/:id" element={<InvoiceDetailPage />} />
            <Route path="/review-queue" element={<ReviewQueuePage />} />
            <Route path="/settings" element={<SettingsPage />} />
        </Route>
        
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </>
  );
};

export default App;

import { useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { apiClient } from '../api/client';
import type { BulkUploadResponse } from '../types';

export const useBulkUploadInvoice = () => {
  const navigate = useNavigate();

  return useMutation<BulkUploadResponse, Error, File[]>({
    mutationFn: async (files: File[]) => {
      const formData = new FormData();
      files.forEach((f) => formData.append('files', f));

      const response = await apiClient.post('/invoices/upload/bulk', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return response.data;
    },
    onSuccess: (data) => {
      if (data?.batch_id) {
        const accepted = data.accepted;
        const rejected = data.rejected?.length || 0;
        if (rejected > 0) {
          toast.success(`${accepted} file(s) accepted, ${rejected} rejected.`);
        } else {
          toast.success(`${accepted} file(s) uploaded successfully!`);
        }
        navigate(`/invoices/batch/${data.batch_id}`);
      }
    },
    onError: (error: any) => {
      const msg = error?.response?.data?.detail || 'Bulk upload failed. Please try again.';
      toast.error(msg);
    },
  });
};

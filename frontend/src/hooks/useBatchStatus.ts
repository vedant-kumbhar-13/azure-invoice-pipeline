import { useQuery } from '@tanstack/react-query';
import { useRef, useEffect } from 'react';
import toast from 'react-hot-toast';
import { apiClient } from '../api/client';
import type { BatchStatusResponse } from '../types';

/**
 * Polls GET /invoices/batch/{batchId} every 3 seconds.
 * Stops when overall_status === "COMPLETED" or after 10 minutes.
 * Shows a one-time toast when the batch finishes processing.
 */
export const useBatchStatus = (batchId: string | undefined) => {
  const pollingStart = useRef<number | null>(null);
  const notifiedRef = useRef(false);

  const query = useQuery<BatchStatusResponse>({
    queryKey: ['batch', batchId],
    queryFn: async () => {
      const response = await apiClient.get(`/invoices/batch/${batchId}`);
      return response.data;
    },
    enabled: !!batchId,
    refetchInterval: (q) => {
      const overall = q.state.data?.overall_status;

      if (overall === 'COMPLETED') {
        pollingStart.current = null;
        return false;
      }

      // Start tracking polling time
      if (!pollingStart.current) pollingStart.current = Date.now();

      const elapsed = Date.now() - pollingStart.current;
      // Stop after 10 minutes
      if (elapsed > 10 * 60 * 1000) return false;

      return 3000;
    },
  });

  // Show a one-time toast when batch processing finishes
  useEffect(() => {
    if (query.data?.overall_status === 'COMPLETED' && !notifiedRef.current) {
      notifiedRef.current = true;
      const total = query.data.total;
      const failed = query.data.failed;
      if (failed > 0) {
        toast.success(`Batch complete! ${total - failed} processed, ${failed} failed.`);
      } else {
        toast.success(`All ${total} invoices processed!`);
      }
    }
  }, [query.data?.overall_status, query.data?.total, query.data?.failed]);

  const isPollingTimedOut =
    pollingStart.current !== null &&
    Date.now() - pollingStart.current > 10 * 60 * 1000;

  return {
    ...query,
    isPollingTimedOut,
  };
};

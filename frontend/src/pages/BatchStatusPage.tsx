import { useParams, Link } from 'react-router-dom';
import { useBatchStatus } from '../hooks/useBatchStatus';
import { StatusBadge } from '../components/StatusBadge';
import { Progress } from '../components/ui/progress';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '../components/ui/table';
import {
  CheckCircle2,
  Loader2,
  AlertTriangle,
  ArrowLeft,
  ExternalLink,
  PackageCheck,
} from 'lucide-react';
import { Button } from '../components/ui/button';

export const BatchStatusPage = () => {
  const { batchId } = useParams<{ batchId: string }>();
  const { data, isLoading, isError, isPollingTimedOut } = useBatchStatus(batchId);

  if (isLoading) {
    return (
      <div className="max-w-4xl mx-auto py-20 flex flex-col items-center gap-4">
        <Loader2 className="h-10 w-10 text-blue-500 animate-spin" />
        <p className="text-ink-500 font-semibold">Loading batch status…</p>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="max-w-4xl mx-auto py-20 flex flex-col items-center gap-4">
        <AlertTriangle className="h-10 w-10 text-amber-500" />
        <p className="text-ink-700 font-bold text-lg">Batch not found</p>
        <Link to="/upload">
          <Button variant="outline">← Back to Upload</Button>
        </Link>
      </div>
    );
  }

  const progressPercent = data.total > 0
    ? Math.round((data.completed / data.total) * 100)
    : 0;

  const isComplete = data.overall_status === 'COMPLETED';
  const isProcessing = data.overall_status === 'PROCESSING';

  return (
    <div className="max-w-4xl mx-auto flex flex-col gap-8 pb-20">

      {/* Header */}
      <div className="flex items-center justify-between pt-4">
        <div className="flex items-center gap-4">
          <Link to="/upload">
            <Button variant="ghost" size="sm" className="text-ink-400 hover:text-ink-700">
              <ArrowLeft className="h-4 w-4 mr-1" />
              Upload
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-ink-900">
              Batch Processing
            </h1>
            <p className="text-xs font-semibold text-ink-400 mt-0.5 font-mono">
              {batchId}
            </p>
          </div>
        </div>
      </div>

      {/* Completion Banner */}
      {isComplete && (
        <div className="bg-gradient-to-r from-emerald-50 to-green-50 border border-emerald-200 rounded-2xl p-6 flex items-center justify-between animate-in fade-in duration-500 shadow-sm">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-emerald-100 rounded-xl">
              <PackageCheck className="h-7 w-7 text-emerald-600" />
            </div>
            <div>
              <h3 className="font-bold text-emerald-900 text-lg tracking-tight">
                All Done!
              </h3>
              <p className="text-sm text-emerald-700 font-medium mt-0.5">
                {data.completed} of {data.total} invoices processed
                {data.failed > 0 && ` (${data.failed} failed)`}
              </p>
            </div>
          </div>
          <Link to="/invoices">
            <Button className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold shadow-md">
              View All Invoices
              <ExternalLink className="h-4 w-4 ml-2" />
            </Button>
          </Link>
        </div>
      )}

      {/* Timed out warning */}
      {isPollingTimedOut && !isComplete && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-center gap-3">
          <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0" />
          <p className="text-sm font-semibold text-amber-800">
            Polling timed out. Refresh the page to check the latest status.
          </p>
        </div>
      )}

      {/* Progress Card */}
      <div className="bg-white border border-ink-200 rounded-2xl p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            {isProcessing && (
              <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />
            )}
            {isComplete && (
              <CheckCircle2 className="h-5 w-5 text-emerald-500" />
            )}
            <span className="font-bold text-ink-900 text-sm tracking-tight">
              {isProcessing
                ? `Processing ${data.completed} of ${data.total} invoices…`
                : isComplete
                  ? `${data.total} invoices processed`
                  : `${data.completed} of ${data.total} done`}
            </span>
          </div>
          <span className="text-sm font-bold text-ink-500">
            {progressPercent}%
          </span>
        </div>
        <Progress
          value={progressPercent}
          className={`h-3 rounded-full ${isComplete ? '[&>div]:bg-emerald-500' : ''}`}
        />

        {/* Summary stats */}
        <div className="flex gap-6 mt-4 pt-4 border-t border-ink-100">
          <div className="flex flex-col">
            <span className="text-[10px] font-bold text-ink-400 uppercase tracking-widest">Total</span>
            <span className="text-xl font-bold text-ink-900">{data.total}</span>
          </div>
          <div className="flex flex-col">
            <span className="text-[10px] font-bold text-ink-400 uppercase tracking-widest">Completed</span>
            <span className="text-xl font-bold text-emerald-600">{data.completed}</span>
          </div>
          {data.failed > 0 && (
            <div className="flex flex-col">
              <span className="text-[10px] font-bold text-ink-400 uppercase tracking-widest">Failed</span>
              <span className="text-xl font-bold text-red-600">{data.failed}</span>
            </div>
          )}
        </div>
      </div>

      {/* Invoice Table */}
      <div className="bg-white border border-ink-200 rounded-2xl shadow-sm overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-b border-ink-200 bg-ink-50/50">
              <TableHead className="pl-6">Filename</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Confidence</TableHead>
              <TableHead>Method</TableHead>
              <TableHead className="pr-6 text-right">Action</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.invoices.map((inv) => (
              <TableRow key={inv.id} className="group">
                <TableCell className="pl-6">
                  <span
                    className="text-sm font-semibold text-ink-800 truncate max-w-[200px] sm:max-w-xs inline-block"
                    title={inv.original_filename}
                  >
                    {inv.original_filename}
                  </span>
                </TableCell>
                <TableCell>
                  <StatusBadge status={inv.status} />
                </TableCell>
                <TableCell>
                  {inv.confidence_score !== null && inv.confidence_score !== undefined ? (
                    <span className={`text-sm font-bold font-mono ${
                      inv.confidence_score >= 0.85
                        ? 'text-emerald-600'
                        : inv.confidence_score >= 0.6
                          ? 'text-amber-600'
                          : 'text-red-600'
                    }`}>
                      {(inv.confidence_score * 100).toFixed(1)}%
                    </span>
                  ) : (
                    <span className="text-xs text-ink-400 font-medium">—</span>
                  )}
                </TableCell>
                <TableCell>
                  <span className="text-xs font-semibold text-ink-500 uppercase">
                    {inv.ingestion_method || '—'}
                  </span>
                </TableCell>
                <TableCell className="pr-6 text-right">
                  {inv.status !== 'processing' && (
                    <Link to={`/invoices/${inv.id}`}>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-blue-600 hover:text-blue-800 hover:bg-blue-50 text-xs font-bold opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        View →
                      </Button>
                    </Link>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
};

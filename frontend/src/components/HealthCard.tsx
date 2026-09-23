import React from 'react';
import { HealthResponse } from '../api/client';

interface HealthCardProps {
  data: HealthResponse | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}

export const HealthCard: React.FC<HealthCardProps> = ({
  data,
  loading,
  error,
  onRefresh,
}) => {
  return (
    <div className="bg-panel border border-line rounded p-6 shadow-none">
      <div className="flex items-center justify-between pb-4 border-b border-line mb-5">
        <div>
          <h2 className="text-[1.125rem] font-semibold text-ink font-sans">
            Backend Subsystem Health
          </h2>
          <p className="text-[0.8125rem] text-muted font-sans mt-0.5">
            Real-time status check of FastAPI gateway, storage engine, and event pub/sub.
          </p>
        </div>

        <button
          onClick={onRefresh}
          disabled={loading}
          className="px-3 py-1.5 text-[0.8125rem] font-sans font-medium bg-accent text-white rounded hover:opacity-90 disabled:opacity-50 transition-opacity"
        >
          {loading ? 'Checking...' : 'Refresh Status'}
        </button>
      </div>

      {loading && !data && (
        <div className="py-8 text-center text-muted font-sans text-[0.9375rem]">
          <div className="inline-block w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin mr-2 align-middle" />
          Querying backend health endpoint...
        </div>
      )}

      {error && (
        <div className="p-4 rounded border border-status-anomalous/30 bg-status-anomalous/10 text-status-anomalous text-[0.875rem] font-sans">
          <p className="font-semibold">Backend Unreachable</p>
          <p className="mt-1 text-[0.8125rem]">{error}</p>
          <p className="mt-2 text-[0.75rem] text-muted">
            Ensure FastAPI server is running on port 8000 or via Docker Compose.
          </p>
        </div>
      )}

      {data && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-3 border border-line rounded bg-surface">
              <span className="text-[0.75rem] text-muted font-sans block">Overall Status</span>
              <span className="text-[1rem] font-medium font-mono text-status-valid mt-0.5 block uppercase">
                {data.status}
              </span>
            </div>
            <div className="p-3 border border-line rounded bg-surface">
              <span className="text-[0.75rem] text-muted font-sans block">Environment</span>
              <span className="text-[1rem] font-medium font-mono text-ink mt-0.5 block capitalize">
                {data.environment} (v{data.version})
              </span>
            </div>
            <div className="p-3 border border-line rounded bg-surface">
              <span className="text-[0.75rem] text-muted font-sans block">Server Time (UTC)</span>
              <span className="text-[0.875rem] font-medium font-mono text-ink mt-0.5 block truncate">
                {data.timestamp}
              </span>
            </div>
          </div>

          <div className="pt-2">
            <h3 className="text-[0.9375rem] font-medium text-ink font-sans mb-2.5">
              Service Registry Readiness
            </h3>
            <div className="border border-line rounded overflow-hidden">
              <table className="w-full text-left text-[0.8125rem]">
                <thead className="bg-surface border-b border-line text-muted font-sans">
                  <tr>
                    <th className="px-4 py-2 font-medium">Service</th>
                    <th className="px-4 py-2 font-medium">Health</th>
                    <th className="px-4 py-2 font-medium">Diagnostic Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line font-sans">
                  {Object.entries(data.services).map(([name, svc]) => (
                    <tr key={name} className="hover:bg-surface/50">
                      <td className="px-4 py-2.5 font-mono text-ink uppercase text-[0.75rem]">
                        {name}
                      </td>
                      <td className="px-4 py-2.5">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-[0.75rem] font-mono ${
                            svc.status === 'healthy' || svc.status === 'configured'
                              ? 'bg-status-valid/15 text-status-valid'
                              : 'bg-status-anomalous/15 text-status-anomalous'
                          }`}
                        >
                          {svc.status}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-muted font-sans">
                        {svc.details}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

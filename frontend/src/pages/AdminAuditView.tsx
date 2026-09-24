import React, { useEffect, useState } from 'react';
import { FileText, RefreshCw } from 'lucide-react';
import { fetchAuditLogs, AuditLogItem } from '../api/admin';

export const AdminAuditView: React.FC = () => {
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [actionFilter, setActionFilter] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  const loadLogs = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAuditLogs(50, actionFilter || undefined);
      setLogs(data);
    } catch (e: any) {
      setError(e.message || 'Failed to load audit trail');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLogs();
  }, [actionFilter]);

  const getActionBadge = (action: string) => {
    if (action.includes('denied') || action.includes('unauthorized')) {
      return 'bg-red-500/15 text-red-400 border-red-500/30';
    }
    if (action.includes('created') || action.includes('boot')) {
      return 'bg-accent/15 text-accent border-accent/30';
    }
    if (action.includes('updated') || action.includes('synced')) {
      return 'bg-amber-500/15 text-amber-400 border-amber-500/30';
    }
    return 'bg-surface text-muted border-line';
  };

  return (
    <div className="space-y-6">
      <div className="bg-panel border border-line rounded-lg p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-lg bg-accent/15 border border-accent/30 text-accent">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-ink">Security & Operational Audit Log</h2>
              <p className="text-xs text-muted mt-0.5">
                Immutable chronological log of authentication events, permission checks, and operational changes.
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2.5">
            <select
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              className="px-2.5 py-1.5 rounded bg-surface border border-line text-xs font-mono text-ink focus:border-accent outline-hidden"
            >
              <option value="">All Actions</option>
              <option value="access_denied">access_denied</option>
              <option value="login">login</option>
              <option value="user_created">user_created</option>
              <option value="user_updated">user_updated</option>
              <option value="setting_updated">setting_updated</option>
              <option value="system_boot">system_boot</option>
            </select>

            <button
              onClick={loadLogs}
              className="px-3 py-1.5 rounded bg-surface border border-line hover:border-muted text-ink text-xs font-mono flex items-center space-x-1.5"
            >
              <RefreshCw className={`w-3.5 h-3.5 text-muted ${loading ? 'animate-spin' : ''}`} />
              <span>Refresh</span>
            </button>
          </div>
        </div>

        {error && (
          <div className="mt-3 p-2.5 rounded bg-red-500/10 border border-red-500/30 text-red-400 text-xs font-mono">
            {error}
          </div>
        )}
      </div>

      {/* Audit Logs Table */}
      <div className="bg-panel border border-line rounded-lg overflow-hidden">
        <div className="p-4 border-b border-line flex items-center justify-between">
          <span className="text-xs font-semibold text-ink font-mono uppercase tracking-wider">
            Recorded Audit Trail ({logs.length} Events)
          </span>
          <span className="text-[11px] font-mono text-muted">Protected Append-Only Storage</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-surface/80 border-b border-line font-mono text-[11px] uppercase text-muted">
              <tr>
                <th className="px-4 py-3">Timestamp</th>
                <th className="px-4 py-3">Action</th>
                <th className="px-4 py-3">Operator Identity</th>
                <th className="px-4 py-3">Resource Target</th>
                <th className="px-4 py-3">Details / Metadata</th>
                <th className="px-4 py-3 text-right">Client IP</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {logs.map((log) => (
                <tr key={log.id} className="hover:bg-hover/30 transition-colors">
                  <td className="px-4 py-3 font-mono text-muted whitespace-nowrap">
                    {new Date(log.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-mono font-semibold uppercase border ${getActionBadge(
                        log.action
                      )}`}
                    >
                      {log.action}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-ink font-medium">{log.user_email}</td>
                  <td className="px-4 py-3 font-mono text-muted">{log.resource}</td>
                  <td className="px-4 py-3 font-mono text-muted max-w-xs truncate">
                    {JSON.stringify(log.details)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-muted">{log.ip_address || '127.0.0.1'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

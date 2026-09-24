import React, { useEffect, useState } from 'react';
import { ShieldCheck, Check, X, RefreshCw } from 'lucide-react';
import { fetchAdminRoles, fetchAdminPermissions, RoleInfo, PermissionInfo } from '../api/admin';

export const AdminRolesView: React.FC = () => {
  const [roles, setRoles] = useState<RoleInfo[]>([]);
  const [permissions, setPermissions] = useState<PermissionInfo[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [rData, pData] = await Promise.all([
        fetchAdminRoles(),
        fetchAdminPermissions(),
      ]);
      setRoles(rData);
      setPermissions(pData);
    } catch (e: any) {
      setError(e.message || 'Failed to load roles and permissions matrix');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Group permissions by module domain
  const modules: Record<string, PermissionInfo[]> = {};
  permissions.forEach((p) => {
    if (!modules[p.module]) modules[p.module] = [];
    modules[p.module].push(p);
  });

  return (
    <div className="space-y-6">
      <div className="bg-panel border border-line rounded-lg p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-lg bg-accent/15 border border-accent/30 text-accent">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-ink">Role-Based Access Control (RBAC) Matrix</h2>
              <p className="text-xs text-muted mt-0.5">
                Granular security matrix mapping 5 operational roles to 21 explicit permission codes.
              </p>
            </div>
          </div>

          <button
            onClick={loadData}
            className="px-3 py-1.5 rounded bg-surface border border-line hover:border-muted text-ink text-xs font-mono flex items-center space-x-1.5"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-muted ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>

        {error && (
          <div className="mt-3 p-2.5 rounded bg-red-500/10 border border-red-500/30 text-red-400 text-xs font-mono">
            {error}
          </div>
        )}
      </div>

      {/* Role Cards Overview */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
        {roles.map((r) => (
          <div key={r.name} className="p-4 rounded-lg bg-panel border border-line space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[11px] font-bold uppercase text-accent">{r.name}</span>
              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-surface border border-line text-muted">
                {r.user_count} users
              </span>
            </div>
            <h4 className="font-medium text-ink text-xs">{r.display_name}</h4>
            <p className="text-[11px] text-muted font-sans leading-tight line-clamp-2">{r.description}</p>
            <div className="pt-1 text-[10px] font-mono text-muted">
              {r.permissions.length} / 21 Permissions
            </div>
          </div>
        ))}
      </div>

      {/* Permissions Matrix Table */}
      <div className="bg-panel border border-line rounded-lg overflow-hidden">
        <div className="p-4 border-b border-line flex items-center justify-between">
          <span className="text-xs font-semibold text-ink font-mono uppercase tracking-wider">
            Permission Enforcement Grid (21 Permissions)
          </span>
          <span className="text-[11px] font-mono text-muted">Enforced at FastAPI route layer</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead className="bg-surface/80 border-b border-line font-mono text-[11px] uppercase">
              <tr>
                <th className="px-4 py-3 min-w-[200px]">Permission Code</th>
                <th className="px-3 py-3 text-center min-w-[90px]">Admin</th>
                <th className="px-3 py-3 text-center min-w-[90px]">Forecaster</th>
                <th className="px-3 py-3 text-center min-w-[90px]">QC Analyst</th>
                <th className="px-3 py-3 text-center min-w-[90px]">Field Tech</th>
                <th className="px-3 py-3 text-center min-w-[90px]">Viewer</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {Object.entries(modules).map(([moduleName, perms]) => (
                <React.Fragment key={moduleName}>
                  {/* Module Group Header */}
                  <tr className="bg-surface/40">
                    <td colSpan={6} className="px-4 py-2 font-mono text-[10px] font-bold uppercase tracking-wider text-accent">
                      Domain: {moduleName}
                    </td>
                  </tr>

                  {perms.map((p) => (
                    <tr key={p.code} className="hover:bg-hover/30 transition-colors">
                      <td className="px-4 py-2.5">
                        <div className="font-mono text-ink font-semibold text-[11px]">{p.code}</div>
                        <div className="text-[11px] text-muted font-sans">{p.description}</div>
                      </td>

                      {/* Role Checkmarks */}
                      {['admin', 'forecaster', 'qc_analyst', 'field_technician', 'viewer'].map((roleName) => {
                        const roleObj = roles.find((r) => r.name === roleName);
                        const hasPerm = roleObj?.permissions.includes(p.code);

                        return (
                          <td key={roleName} className="px-3 py-2.5 text-center">
                            {hasPerm ? (
                              <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-[#3FB876]/15 text-[#3FB876]">
                                <Check className="w-3.5 h-3.5 stroke-[2.5]" />
                              </span>
                            ) : (
                              <span className="inline-flex items-center justify-center w-5 h-5 rounded-full text-muted/30">
                                <X className="w-3.5 h-3.5" />
                              </span>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

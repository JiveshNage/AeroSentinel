import React, { useEffect, useState } from 'react';
import { Users, UserPlus, Shield, RefreshCw, AlertCircle } from 'lucide-react';
import { fetchAdminUsers, createAdminUser, updateAdminUser, AdminUser } from '../api/admin';

export const AdminUsersView: React.FC = () => {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [newName, setNewName] = useState<string>('');
  const [newEmail, setNewEmail] = useState<string>('');
  const [newPassword, setNewPassword] = useState<string>('');
  const [newRole, setNewRole] = useState<string>('qc_analyst');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const loadUsers = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAdminUsers();
      setUsers(data);
    } catch (e: any) {
      setError(e.message || 'Failed to load user list');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await createAdminUser({
        name: newName,
        email: newEmail,
        password: newPassword,
        role: newRole,
      });
      setStatusMessage(`User ${newEmail} created successfully.`);
      setShowCreateModal(false);
      setNewName('');
      setNewEmail('');
      setNewPassword('');
      loadUsers();
      setTimeout(() => setStatusMessage(null), 4000);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleRoleChange = async (userId: string, newRoleValue: string) => {
    try {
      await updateAdminUser(userId, { role: newRoleValue });
      setStatusMessage('User role updated successfully.');
      loadUsers();
      setTimeout(() => setStatusMessage(null), 3000);
    } catch (e: any) {
      setError(e.message);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-panel border border-line rounded-lg p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-lg bg-accent/15 border border-accent/30 text-accent">
              <Users className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-ink">User Account Administration</h2>
              <p className="text-xs text-muted mt-0.5">
                Manage operator accounts, assign operational roles, and enforce security policies.
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2.5">
            <button
              onClick={loadUsers}
              className="px-3 py-1.5 rounded bg-surface border border-line hover:border-muted text-ink text-xs font-mono flex items-center space-x-1.5"
            >
              <RefreshCw className={`w-3.5 h-3.5 text-muted ${loading ? 'animate-spin' : ''}`} />
              <span>Refresh</span>
            </button>
            <button
              onClick={() => setShowCreateModal(true)}
              className="px-3 py-1.5 rounded bg-accent text-white text-xs font-medium hover:opacity-90 flex items-center space-x-1.5"
            >
              <UserPlus className="w-3.5 h-3.5" />
              <span>Create Account</span>
            </button>
          </div>
        </div>

        {statusMessage && (
          <div className="mt-3 p-2.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono">
            {statusMessage}
          </div>
        )}

        {error && (
          <div className="mt-3 p-2.5 rounded bg-red-500/10 border border-red-500/30 text-red-400 text-xs font-mono flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* Users Table */}
      <div className="bg-panel border border-line rounded-lg overflow-hidden">
        <div className="p-4 border-b border-line flex items-center justify-between">
          <span className="text-xs font-semibold text-ink font-mono uppercase tracking-wider">
            Registered System Personnel ({users.length})
          </span>
          <span className="text-[11px] font-mono text-muted">RBAC Role Clearance</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-surface/60 border-b border-line text-muted font-mono text-[11px] uppercase">
              <tr>
                <th className="px-4 py-3">Operator Name</th>
                <th className="px-4 py-3">Email Address</th>
                <th className="px-4 py-3">Assigned Role</th>
                <th className="px-4 py-3">Role Modifier</th>
                <th className="px-4 py-3 text-right">Created Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-hover/40 transition-colors">
                  <td className="px-4 py-3 font-medium text-ink flex items-center space-x-2.5">
                    <div className="w-7 h-7 rounded-full bg-accent/20 border border-accent/40 flex items-center justify-center text-accent font-bold font-mono text-xs">
                      {u.name.charAt(0)}
                    </div>
                    <span>{u.name}</span>
                  </td>
                  <td className="px-4 py-3 font-mono text-muted">{u.email}</td>
                  <td className="px-4 py-3">
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase font-semibold border bg-surface text-ink border-line">
                      {u.role}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <select
                      value={u.role}
                      onChange={(e) => handleRoleChange(u.id, e.target.value)}
                      className="px-2 py-1 rounded bg-surface border border-line text-xs font-mono text-ink focus:border-accent outline-hidden"
                    >
                      <option value="admin">admin</option>
                      <option value="forecaster">forecaster</option>
                      <option value="qc_analyst">qc_analyst</option>
                      <option value="field_technician">field_technician</option>
                      <option value="viewer">viewer</option>
                    </select>
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-muted">
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
          <div className="bg-panel border border-line rounded-lg w-full max-w-md p-5 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-line pb-3">
              <div className="flex items-center space-x-2">
                <Shield className="w-4 h-4 text-accent" />
                <h3 className="text-sm font-semibold text-ink">Register Operator Account</h3>
              </div>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-muted hover:text-ink text-xs font-mono"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreate} className="space-y-3 text-xs">
              <div>
                <label className="block text-muted font-mono mb-1">Full Name</label>
                <input
                  type="text"
                  required
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="e.g. Dr. Rajesh Kumar"
                  className="w-full px-3 py-2 rounded bg-surface border border-line text-ink focus:border-accent outline-hidden font-sans"
                />
              </div>

              <div>
                <label className="block text-muted font-mono mb-1">Email Address</label>
                <input
                  type="email"
                  required
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                  placeholder="e.g. rajesh@imd.gov.in"
                  className="w-full px-3 py-2 rounded bg-surface border border-line text-ink focus:border-accent outline-hidden font-mono"
                />
              </div>

              <div>
                <label className="block text-muted font-mono mb-1">Password</label>
                <input
                  type="password"
                  required
                  minLength={6}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full px-3 py-2 rounded bg-surface border border-line text-ink focus:border-accent outline-hidden font-mono"
                />
              </div>

              <div>
                <label className="block text-muted font-mono mb-1">Operational Role</label>
                <select
                  value={newRole}
                  onChange={(e) => setNewRole(e.target.value)}
                  className="w-full px-3 py-2 rounded bg-surface border border-line text-ink focus:border-accent outline-hidden font-mono"
                >
                  <option value="admin">admin (Full Access)</option>
                  <option value="forecaster">forecaster (Weather Operations)</option>
                  <option value="qc_analyst">qc_analyst (Anomaly Adjudication)</option>
                  <option value="field_technician">field_technician (Hardware & Maintenance)</option>
                  <option value="viewer">viewer (Read-Only Observer)</option>
                </select>
              </div>

              <div className="flex items-center justify-end space-x-2 pt-3 border-t border-line">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-3 py-1.5 rounded bg-surface border border-line text-ink hover:bg-hover font-mono"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-3.5 py-1.5 rounded bg-accent text-white font-medium hover:opacity-90 font-sans disabled:opacity-50"
                >
                  {submitting ? 'Creating...' : 'Create Account'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

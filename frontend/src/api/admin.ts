/**
 * admin.ts — Client API for Administration & RBAC Governance
 * AeroSentinel (SIH26073)
 */

import { getStoredToken } from './auth';

export interface AdminUser {
  id: string;
  name: string;
  email: string;
  role: string;
  created_at: string;
}

export interface RoleInfo {
  name: string;
  display_name: string;
  description: string;
  user_count: number;
  permissions: string[];
}

export interface PermissionInfo {
  code: string;
  module: string;
  description: string;
}

export interface AuditLogItem {
  id: number;
  user_email: string;
  action: string;
  resource: string;
  details: Record<string, any>;
  ip_address: string | null;
  created_at: string;
}

export interface SystemSettingItem {
  key: string;
  value: Record<string, any>;
  description: string | null;
  updated_by: string | null;
  updated_at: string;
}

function getAuthHeaders(): HeadersInit {
  const token = getStoredToken();
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

export async function fetchAdminUsers(): Promise<AdminUser[]> {
  const res = await fetch('/api/admin/users', { headers: getAuthHeaders() });
  if (!res.ok) throw new Error(`Failed to fetch users (${res.status})`);
  return res.json();
}

export async function createAdminUser(payload: { name: string; email: string; password: string; role: string }): Promise<AdminUser> {
  const res = await fetch('/api/admin/users', {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to create user (${res.status})`);
  }
  return res.json();
}

export async function updateAdminUser(userId: string, payload: { name?: string; role?: string; password?: string }): Promise<AdminUser> {
  const res = await fetch(`/api/admin/users/${userId}`, {
    method: 'PUT',
    headers: getAuthHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to update user (${res.status})`);
  }
  return res.json();
}

export async function fetchAdminRoles(): Promise<RoleInfo[]> {
  const res = await fetch('/api/admin/roles', { headers: getAuthHeaders() });
  if (!res.ok) throw new Error(`Failed to fetch roles (${res.status})`);
  return res.json();
}

export async function fetchAdminPermissions(): Promise<PermissionInfo[]> {
  const res = await fetch('/api/admin/permissions', { headers: getAuthHeaders() });
  if (!res.ok) throw new Error(`Failed to fetch permissions (${res.status})`);
  return res.json();
}

export async function fetchAuditLogs(limit: number = 50, action?: string): Promise<AuditLogItem[]> {
  let url = `/api/admin/audit-logs?limit=${limit}`;
  if (action) url += `&action=${encodeURIComponent(action)}`;
  const res = await fetch(url, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error(`Failed to fetch audit logs (${res.status})`);
  return res.json();
}

export async function fetchSystemSettings(): Promise<SystemSettingItem[]> {
  const res = await fetch('/api/admin/settings', { headers: getAuthHeaders() });
  if (!res.ok) throw new Error(`Failed to fetch system settings (${res.status})`);
  return res.json();
}

export async function updateSystemSetting(key: string, value: Record<string, any>, description?: string): Promise<SystemSettingItem> {
  const res = await fetch('/api/admin/settings', {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ key, value, description }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to update setting (${res.status})`);
  }
  return res.json();
}

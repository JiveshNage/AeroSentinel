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

import { apiUrl, fetchJson } from './client';

export async function fetchAdminUsers(): Promise<AdminUser[]> {
  return fetchJson<AdminUser[]>(apiUrl('/api/admin/users'), { headers: getAuthHeaders() });
}

export async function createAdminUser(payload: { name: string; email: string; password: string; role: string }): Promise<AdminUser> {
  return fetchJson<AdminUser>(apiUrl('/api/admin/users'), {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(payload),
  });
}

export async function updateAdminUser(userId: string, payload: { name?: string; role?: string; password?: string }): Promise<AdminUser> {
  return fetchJson<AdminUser>(apiUrl(`/api/admin/users/${userId}`), {
    method: 'PUT',
    headers: getAuthHeaders(),
    body: JSON.stringify(payload),
  });
}

export async function fetchAdminRoles(): Promise<RoleInfo[]> {
  return fetchJson<RoleInfo[]>(apiUrl('/api/admin/roles'), { headers: getAuthHeaders() });
}

export async function fetchAdminPermissions(): Promise<PermissionInfo[]> {
  return fetchJson<PermissionInfo[]>(apiUrl('/api/admin/permissions'), { headers: getAuthHeaders() });
}

export async function fetchAuditLogs(limit: number = 50, action?: string): Promise<AuditLogItem[]> {
  let url = `/api/admin/audit-logs?limit=${limit}`;
  if (action) url += `&action=${encodeURIComponent(action)}`;
  return fetchJson<AuditLogItem[]>(apiUrl(url), { headers: getAuthHeaders() });
}

export async function fetchSystemSettings(): Promise<SystemSettingItem[]> {
  return fetchJson<SystemSettingItem[]>(apiUrl('/api/admin/settings'), { headers: getAuthHeaders() });
}

export async function updateSystemSetting(key: string, value: Record<string, any>, description?: string): Promise<SystemSettingItem> {
  return fetchJson<SystemSettingItem>(apiUrl('/api/admin/settings'), {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ key, value, description }),
  });
}


/**
 * auth.ts — Client API for Feature F15 Auth & Role-Based Access Control (RBAC)
 * AeroSentinel (SIH26073)
 */

import { supabase } from './supabase';

export type UserRoleType =
  | 'admin'
  | 'forecaster'
  | 'qc_analyst'
  | 'data_quality_officer'
  | 'field_technician'
  | 'viewer';

export type PermissionCode =
  | 'dashboard.view'
  | 'fleet.view'
  | 'stations.view'
  | 'stations.edit'
  | 'telemetry.view'
  | 'alerts.view'
  | 'alerts.acknowledge'
  | 'anomalies.view'
  | 'anomalies.investigate'
  | 'anomalies.resolve'
  | 'forecasts.view'
  | 'forecasts.create'
  | 'health.view'
  | 'maintenance.view'
  | 'maintenance.update'
  | 'data.upload'
  | 'users.view'
  | 'users.manage'
  | 'roles.manage'
  | 'audit.view'
  | 'system.manage';

export interface AuthUser {
  id: string;
  name: string;
  email: string;
  role: UserRoleType;
  permissions?: PermissionCode[];
  created_at?: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

// Client-side fallback mapping matching backend core.permissions.ROLE_PERMISSIONS_MAP
export const ROLE_PERMISSIONS_FALLBACK: Record<UserRoleType, PermissionCode[]> = {
  admin: [
    'dashboard.view',
    'fleet.view',
    'stations.view',
    'stations.edit',
    'telemetry.view',
    'alerts.view',
    'alerts.acknowledge',
    'anomalies.view',
    'anomalies.investigate',
    'anomalies.resolve',
    'forecasts.view',
    'forecasts.create',
    'health.view',
    'maintenance.view',
    'maintenance.update',
    'data.upload',
    'users.view',
    'users.manage',
    'roles.manage',
    'audit.view',
    'system.manage',
  ],
  forecaster: [
    'dashboard.view',
    'fleet.view',
    'telemetry.view',
    'stations.view',
    'alerts.view',
    'alerts.acknowledge',
    'anomalies.view',
    'anomalies.investigate',
    'forecasts.view',
    'forecasts.create',
    'health.view',
  ],
  qc_analyst: [
    'dashboard.view',
    'fleet.view',
    'telemetry.view',
    'stations.view',
    'alerts.view',
    'alerts.acknowledge',
    'anomalies.view',
    'anomalies.investigate',
    'anomalies.resolve',
    'health.view',
    'data.upload',
  ],
  data_quality_officer: [
    'dashboard.view',
    'fleet.view',
    'telemetry.view',
    'stations.view',
    'alerts.view',
    'alerts.acknowledge',
    'anomalies.view',
    'anomalies.investigate',
    'anomalies.resolve',
    'health.view',
    'data.upload',
  ],
  field_technician: [
    'fleet.view',
    'stations.view',
    'stations.edit',
    'health.view',
    'maintenance.view',
    'maintenance.update',
  ],
  viewer: [
    'dashboard.view',
    'fleet.view',
    'stations.view',
    'telemetry.view',
    'alerts.view',
  ],
};

export const DEMO_USERS: Record<string, AuthUser & { pass: string; title: string }> = {
  admin: {
    id: 'admin-seed',
    email: 'admin@imd.gov.in',
    name: 'Dr. R. Sharma',
    title: 'System Administrator',
    role: 'admin',
    pass: 'AdminPassword123!',
    permissions: ROLE_PERMISSIONS_FALLBACK.admin,
  },
  forecaster: {
    id: 'forecaster-seed',
    email: 'forecaster@imd.gov.in',
    name: 'P. Nair',
    title: 'Operational Forecaster',
    role: 'forecaster',
    pass: 'ForecasterPassword123!',
    permissions: ROLE_PERMISSIONS_FALLBACK.forecaster,
  },
  qc_analyst: {
    id: 'qc-seed',
    email: 'qc@imd.gov.in',
    name: 'A. Verma',
    title: 'Quality Control Analyst',
    role: 'qc_analyst',
    pass: 'QcPassword123!',
    permissions: ROLE_PERMISSIONS_FALLBACK.qc_analyst,
  },
  field_technician: {
    id: 'tech-seed',
    email: 'tech@imd.gov.in',
    name: 'K. Singh',
    title: 'Field Maintenance Technician',
    role: 'field_technician',
    pass: 'TechPassword123!',
    permissions: ROLE_PERMISSIONS_FALLBACK.field_technician,
  },
  viewer: {
    id: 'viewer-seed',
    email: 'viewer@imd.gov.in',
    name: 'S. Das',
    title: 'Read-Only Observer',
    role: 'viewer',
    pass: 'ViewerPassword123!',
    permissions: ROLE_PERMISSIONS_FALLBACK.viewer,
  },
};

const TOKEN_KEY = 'aerosentinel_auth_token';
const USER_KEY = 'aerosentinel_auth_user';

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setStoredAuth(token: string, user: AuthUser): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function getStoredUser(): AuthUser | null {
  const data = localStorage.getItem(USER_KEY);
  if (!data) return null;
  try {
    const user: AuthUser = JSON.parse(data);
    if (!user.permissions || user.permissions.length === 0) {
      user.permissions = ROLE_PERMISSIONS_FALLBACK[user.role] || [];
    }
    return user;
  } catch {
    return null;
  }
}

export function clearStoredAuth(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function hasPermission(user: AuthUser | null, permission: PermissionCode): boolean {
  if (!user) return false;
  const userPerms = user.permissions && user.permissions.length > 0
    ? user.permissions
    : ROLE_PERMISSIONS_FALLBACK[user.role] || [];
  return userPerms.includes(permission);
}

export async function loginWithCredentials(email: string, pass: string): Promise<LoginResponse> {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password: pass }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Login failed with HTTP ${res.status}`);
  }

  const data: LoginResponse = await res.json();
  if (!data.user.permissions || data.user.permissions.length === 0) {
    data.user.permissions = ROLE_PERMISSIONS_FALLBACK[data.user.role] || [];
  }
  setStoredAuth(data.access_token, data.user);
  return data;
}

export async function fetchCurrentUser(): Promise<AuthUser> {
  const token = getStoredToken();
  if (!token) {
    throw new Error('No active token');
  }

  const res = await fetch('/api/auth/me', {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) {
    clearStoredAuth();
    throw new Error(`Session expired (${res.status})`);
  }

  const user: AuthUser = await res.json();
  if (!user.permissions || user.permissions.length === 0) {
    user.permissions = ROLE_PERMISSIONS_FALLBACK[user.role] || [];
  }
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  return user;
}

/**
 * Sign in using Supabase Auth (Email + Password).
 * Extracts profile and role directly from Supabase session.
 */
export async function signInWithSupabase(email: string, pass: string): Promise<LoginResponse> {
  if (!supabase) {
    throw new Error('Supabase client is not configured.');
  }

  const { data, error } = await supabase.auth.signInWithPassword({
    email,
    password: pass,
  });

  if (error || !data.session || !data.user) {
    throw new Error(error?.message || 'Supabase authentication failed');
  }

  const role: UserRoleType = (data.user.user_metadata?.role as UserRoleType) || 'viewer';
  const fullName: string = data.user.user_metadata?.full_name || data.user.email?.split('@')[0] || 'User';

  const authUser: AuthUser = {
    id: data.user.id,
    name: fullName,
    email: data.user.email || email,
    role,
    permissions: ROLE_PERMISSIONS_FALLBACK[role] || [],
    created_at: data.user.created_at,
  };

  const loginRes: LoginResponse = {
    access_token: data.session.access_token,
    token_type: 'bearer',
    user: authUser,
  };

  setStoredAuth(loginRes.access_token, loginRes.user);
  return loginRes;
}

/**
 * Register a new user using Supabase Auth.
 * Enforces default role: 'viewer' (users cannot choose elevated roles during signup).
 */
export async function signUpWithSupabase(
  email: string,
  pass: string,
  fullName: string
): Promise<{ user: any; session: any }> {
  if (!supabase) {
    throw new Error('Supabase client is not configured.');
  }

  // Force default role to 'viewer' per security requirements
  const { data, error } = await supabase.auth.signUp({
    email,
    password: pass,
    options: {
      data: {
        full_name: fullName,
        role: 'viewer',
      },
    },
  });

  if (error) {
    throw new Error(error.message);
  }

  return data;
}

/**
 * Global Sign out helper: clears Supabase session and local storage.
 */
export async function signOutUser(): Promise<void> {
  try {
    if (supabase) {
      await supabase.auth.signOut();
    }
  } catch (err) {
    console.error('Error signing out of Supabase:', err);
  } finally {
    clearStoredAuth();
  }
}



/**
 * auth.ts — Client API for Feature F15 Auth & Role-Based Access Control
 */

export interface AuthUser {
  id: string;
  name: string;
  email: string;
  role: 'admin' | 'data_quality_officer' | 'field_technician' | 'forecaster';
  created_at?: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export const DEMO_USERS: Record<string, AuthUser & { pass: string }> = {
  admin: {
    id: 'admin-seed',
    email: 'admin@imd.gov.in',
    name: 'Dr. R. Sharma (Admin)',
    role: 'admin',
    pass: 'AdminPassword123!',
  },
  operator: {
    id: 'operator-seed',
    email: 'operator@imd.gov.in',
    name: 'A. Verma (DQO)',
    role: 'data_quality_officer',
    pass: 'OperatorPassword123!',
  },
  tech: {
    id: 'tech-seed',
    email: 'tech@imd.gov.in',
    name: 'K. Singh (Technician)',
    role: 'field_technician',
    pass: 'TechPassword123!',
  },
  forecaster: {
    id: 'forecaster-seed',
    email: 'forecaster@imd.gov.in',
    name: 'P. Nair (Forecaster)',
    role: 'forecaster',
    pass: 'ForecasterPassword123!',
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
    return JSON.parse(data);
  } catch {
    return null;
  }
}

export function clearStoredAuth(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
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
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  return user;
}

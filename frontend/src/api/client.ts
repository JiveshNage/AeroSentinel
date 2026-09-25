/**
 * client.ts — Base API Client & Health Check
 * AeroSentinel (SIH26073)
 */

const BASE_URL: string = (
  import.meta.env.VITE_API_URL ||
  import.meta.env.NEXT_PUBLIC_API_URL ||
  ''
).replace(/\/+$/, '');

/**
 * Returns full API URL, prefixing VITE_API_URL if configured.
 * Defaults to relative path (e.g. /api/...) for local Vite proxy.
 */
export function apiUrl(endpoint: string): string {
  const clean = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  return BASE_URL ? `${BASE_URL}${clean}` : clean;
}

/**
 * Returns full WebSocket URL for telemetry and alert streaming.
 * Automatically adapts wss:// / ws:// protocol.
 */
export function wsUrl(endpoint: string): string {
  const clean = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  if (BASE_URL) {
    const wsBase = BASE_URL.replace(/^http:/i, 'ws:').replace(/^https:/i, 'wss:');
    return `${wsBase}${clean}`;
  }
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}${clean}`;
}

/**
 * Safe JSON fetch wrapper that guards against HTML error pages (e.g. 404/502/SPA redirects)
 */
export async function fetchJson<T = any>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init);
  const contentType = response.headers.get('content-type') || '';

  if (!contentType.includes('application/json')) {
    const text = await response.text();
    if (text.trim().startsWith('<') || text.includes('<!doctype') || text.includes('<!DOCTYPE')) {
      throw new Error(
        `Backend returned HTML instead of JSON (HTTP ${response.status}). If deployed on Vercel, ensure VITE_API_URL is set to your active Render backend service URL.`
      );
    }
    throw new Error(`Expected JSON but received: ${contentType || 'plain text'}`);
  }

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Request failed with HTTP ${response.status}`);
  }

  return response.json();
}

export interface ServiceHealth {
  status: string;
  details: string;
}

export interface HealthResponse {
  status: string;
  app_name: string;
  version: string;
  environment: string;
  timestamp: string;
  services: Record<string, ServiceHealth>;
}

export async function fetchHealth(): Promise<HealthResponse> {
  return fetchJson<HealthResponse>(apiUrl('/api/health'));
}

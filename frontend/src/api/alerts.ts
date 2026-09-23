/**
 * alerts.ts — API client for Operational Alerts & WebSocket Stream (F10 / F11 / F13)
 */

export interface AlertItem {
  id: number;
  station_id: string;
  station_code: string;
  station_name: string;
  variable: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  status: 'open' | 'acknowledged' | 'resolved';
  message: string;
  channel_sent: Record<string, any>;
  created_at: string;
  resolved_at?: string | null;
}

export interface AlertListResponse {
  total: number;
  alerts: AlertItem[];
}

export async function fetchAlerts(params?: {
  status?: string;
  severity?: string;
  station_id?: string;
  limit?: number;
}): Promise<AlertListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.set('status', params.status);
  if (params?.severity) searchParams.set('severity', params.severity);
  if (params?.station_id) searchParams.set('station_id', params.station_id);
  if (params?.limit) searchParams.set('limit', params.limit.toString());

  const qs = searchParams.toString();
  const resp = await fetch(`/api/alerts${qs ? `?${qs}` : ''}`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch alerts: HTTP ${resp.status}`);
  }
  return resp.json();
}

export async function updateAlertStatus(
  alertId: number,
  newStatus: 'acknowledged' | 'resolved',
): Promise<AlertItem> {
  const resp = await fetch(`/api/alerts/${alertId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: newStatus }),
  });
  if (!resp.ok) {
    throw new Error(`Failed to update alert: HTTP ${resp.status}`);
  }
  return resp.json();
}

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
  feedback_label?: 'confirmed_fault' | 'false_alarm' | 'unsure' | null;
}

export interface AlertListResponse {
  total: number;
  alerts: AlertItem[];
}

export interface FeedbackItem {
  id: number;
  alert_id?: number | null;
  qc_result_id: number;
  station_code?: string | null;
  station_name?: string | null;
  variable?: string | null;
  label: 'confirmed_fault' | 'false_alarm' | 'unsure';
  notes?: string | null;
  user_id?: string | null;
  user_email?: string | null;
  created_at: string;
}

export interface FeedbackListResponse {
  total: number;
  feedback: FeedbackItem[];
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

export async function submitAlertFeedback(
  alertId: number,
  feedback: {
    label: 'confirmed_fault' | 'false_alarm' | 'unsure';
    notes?: string;
    user_email?: string;
  },
): Promise<FeedbackItem> {
  const resp = await fetch(`/api/alerts/${alertId}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(feedback),
  });
  if (!resp.ok) {
    throw new Error(`Failed to submit feedback: HTTP ${resp.status}`);
  }
  return resp.json();
}

export async function fetchFeedbackList(params?: {
  label?: string;
  limit?: number;
  offset?: number;
}): Promise<FeedbackListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.label) searchParams.set('label', params.label);
  if (params?.limit) searchParams.set('limit', params.limit.toString());
  if (params?.offset) searchParams.set('offset', params.offset.toString());

  const qs = searchParams.toString();
  const resp = await fetch(`/api/feedback${qs ? `?${qs}` : ''}`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch feedback: HTTP ${resp.status}`);
  }
  return resp.json();
}

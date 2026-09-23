/**
 * stations.ts — API client for Station Registry and Real-Time Health Status (F11)
 */

export type StationHealthStatus = 'healthy' | 'suspect' | 'anomalous' | 'offline';

export interface LatestReading {
  timestamp: string;
  temperature?: number | null;
  humidity?: number | null;
  pressure?: number | null;
  wind_speed?: number | null;
  wind_direction?: number | null;
  rainfall?: number | null;
  solar_radiation?: number | null;
}

export interface StationSummary {
  id: string;
  station_code: string;
  name: string;
  latitude: number;
  longitude: number;
  elevation_m?: number | null;
  state: string;
  district: string;
  status: string;
  health_status: StationHealthStatus;
  latest_reading?: LatestReading | null;
  latest_verdict?: 'valid' | 'suspect' | 'anomalous' | null;
  active_alerts_count: number;
  latest_fault_type?: string | null;
  sensor_specs: Record<string, any>;
}

export interface StationListResponse {
  total: number;
  healthy_count: number;
  suspect_count: number;
  anomalous_count: number;
  offline_count: number;
  stations: StationSummary[];
}

export interface StationDetail extends StationSummary {
  recent_readings: LatestReading[];
  active_alerts: Array<{
    id: number;
    severity: string;
    status: string;
    message: string;
    created_at: string;
  }>;
}

export async function fetchStations(params?: {
  state?: string;
  status?: string;
}): Promise<StationListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.state && params.state !== 'ALL') {
    searchParams.set('state', params.state);
  }
  if (params?.status) {
    searchParams.set('status', params.status);
  }

  const queryString = searchParams.toString();
  const url = `/api/stations${queryString ? `?${queryString}` : ''}`;
  const resp = await fetch(url);
  if (!resp.ok) {
    throw new Error(`Failed to fetch stations: HTTP ${resp.status}`);
  }
  return resp.json();
}

export async function fetchStationDetail(stationId: string): Promise<StationDetail> {
  const resp = await fetch(`/api/stations/${stationId}`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch station detail: HTTP ${resp.status}`);
  }
  return resp.json();
}

export interface QCVariableVerdict {
  verdict: 'valid' | 'suspect' | 'anomalous';
  reason_code: string;
  fault_type?: string | null;
  confidence: number;
  details: Record<string, any>;
}

export interface TelemetryPoint {
  id: number;
  timestamp: string;
  temperature?: number | null;
  humidity?: number | null;
  pressure?: number | null;
  wind_speed?: number | null;
  wind_direction?: number | null;
  rainfall?: number | null;
  solar_radiation?: number | null;
  qc_verdicts: Record<string, QCVariableVerdict>;
}

export interface StationTelemetryResponse {
  station_id: string;
  station_code: string;
  name: string;
  sensor_specs: Record<string, any>;
  total_points: number;
  telemetry: TelemetryPoint[];
}

export async function fetchStationTelemetry(
  stationId: string,
  params?: {
    start_time?: string;
    end_time?: string;
    limit?: number;
  },
): Promise<StationTelemetryResponse> {
  const searchParams = new URLSearchParams();
  if (params?.start_time) searchParams.set('start_time', params.start_time);
  if (params?.end_time) searchParams.set('end_time', params.end_time);
  if (params?.limit) searchParams.set('limit', params.limit.toString());

  const qs = searchParams.toString();
  const resp = await fetch(`/api/stations/${stationId}/telemetry${qs ? `?${qs}` : ''}`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch station telemetry: HTTP ${resp.status}`);
  }
  return resp.json();
}

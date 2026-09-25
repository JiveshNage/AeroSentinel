/**
 * live.ts — Client API for Real-Time Telemetry Streaming and Simulation
 */

import { TelemetryPoint } from './stations';

export interface SimulateTickPayload {
  force_anomaly?: boolean;
  fault_type?: 'spike' | 'flatline' | 'out_of_bounds' | string;
  variable?: 'temperature' | 'humidity' | 'pressure' | 'wind_speed' | string;
}

import { apiUrl, fetchJson } from './client';

export async function simulateStationTick(
  stationId: string,
  payload?: SimulateTickPayload
): Promise<TelemetryPoint> {
  return fetchJson<TelemetryPoint>(apiUrl(`/api/stations/${stationId}/simulate-tick`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload || {}),
  });
}


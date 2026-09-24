/**
 * live.ts — Client API for Real-Time Telemetry Streaming and Simulation
 */

import { TelemetryPoint } from './stations';

export interface SimulateTickPayload {
  force_anomaly?: boolean;
  fault_type?: 'spike' | 'flatline' | 'out_of_bounds' | string;
  variable?: 'temperature' | 'humidity' | 'pressure' | 'wind_speed' | string;
}

export async function simulateStationTick(
  stationId: string,
  payload?: SimulateTickPayload
): Promise<TelemetryPoint> {
  const res = await fetch(`/api/stations/${stationId}/simulate-tick`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload || {}),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Live tick simulation failed with HTTP ${res.status}`);
  }

  return res.json();
}

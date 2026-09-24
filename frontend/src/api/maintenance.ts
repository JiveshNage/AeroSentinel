/**
 * maintenance.ts — Client API for Feature F16 Predictive Maintenance
 */

export interface MaintenancePredictionResponse {
  id: number;
  station_id: string;
  station_code: string;
  station_name: string;
  state: string;
  district: string;
  status: string;
  predicted_at: string;
  failure_probability_30d: number;
  risk_level: 'critical' | 'elevated' | 'moderate' | 'nominal';
  top_driver: string;
  recommended_action: string;
  top_factors: {
    risk_level: string;
    top_driver: string;
    recommended_action: string;
    factor_breakdown: Record<string, number>;
    metrics_summary: Record<string, any>;
  };
}

export interface FleetMaintenanceSummary {
  total_stations: number;
  critical_risk_count: number;
  elevated_risk_count: number;
  moderate_risk_count: number;
  nominal_risk_count: number;
  mean_failure_probability: number;
  ranked_predictions: MaintenancePredictionResponse[];
}

export async function fetchMaintenancePredictions(
  riskLevel?: string
): Promise<FleetMaintenanceSummary> {
  const url = riskLevel && riskLevel !== 'all'
    ? `/api/maintenance/predictions?risk_level=${encodeURIComponent(riskLevel)}`
    : '/api/maintenance/predictions';

  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Failed to fetch maintenance predictions: HTTP ${res.status}`);
  }
  return res.json();
}

export async function recomputeMaintenancePredictions(): Promise<FleetMaintenanceSummary> {
  const res = await fetch('/api/maintenance/recompute', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) {
    throw new Error(`Failed to recompute maintenance predictions: HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchStationMaintenanceDetail(
  stationId: string
): Promise<MaintenancePredictionResponse> {
  const res = await fetch(`/api/maintenance/stations/${encodeURIComponent(stationId)}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch station maintenance detail: HTTP ${res.status}`);
  }
  return res.json();
}

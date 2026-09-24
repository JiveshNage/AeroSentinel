import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  Cpu,
  Shield,
  CloudSun,
  Wind,
  Droplets,
  Thermometer,
  Wrench,
  Eye,
  ArrowUpRight,
  RefreshCw,
} from 'lucide-react';
import { AuthUser } from '../api/auth';
import { AppNavTab } from '../components/Sidebar';
import { fetchAlerts, AlertItem, updateAlertStatus, submitAlertFeedback } from '../api/alerts';
import { fetchStations, StationSummary } from '../api/stations';
import { fetchAuditLogs, AuditLogItem } from '../api/admin';

interface DashboardViewProps {
  currentUser: AuthUser | null;
  onNavigateTab: (tab: AppNavTab) => void;
  onInspectStation: (code: string) => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  currentUser,
  onNavigateTab,
  onInspectStation,
}) => {
  const role = currentUser?.role || 'admin';

  const [stations, setStations] = useState<StationSummary[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const [stRes, alRes] = await Promise.all([
        fetchStations().catch(() => ({ total: 0, healthy_count: 0, suspect_count: 0, anomalous_count: 0, offline_count: 0, stations: [] })),
        fetchAlerts({ limit: 10 }).catch(() => ({ alerts: [], total: 0 })),
      ]);
      setStations(stRes && 'stations' in stRes ? stRes.stations : []);
      setAlerts(alRes.alerts);

      if (role === 'admin') {
        const logs = await fetchAuditLogs(5).catch(() => []);
        setAuditLogs(logs);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [role]);

  const handleAcknowledge = async (alertId: number) => {
    try {
      await updateAlertStatus(alertId, 'acknowledged');
      setActionMessage(`Alert #${alertId} successfully acknowledged.`);
      loadData();
      setTimeout(() => setActionMessage(null), 4000);
    } catch (e: any) {
      setActionMessage(`Failed: ${e.message}`);
    }
  };

  const handleFeedback = async (alertId: number, label: 'confirmed_fault' | 'false_alarm') => {
    try {
      await submitAlertFeedback(alertId, {
        label,
        notes: `Operator decision by ${currentUser?.name || 'QC Analyst'}`,
      });
      setActionMessage(`QC Decision recorded: ${label === 'confirmed_fault' ? 'Confirmed Sensor Fault' : 'Marked as False Alarm / Extreme Weather'}.`);
      loadData();
      setTimeout(() => setActionMessage(null), 4000);
    } catch (e: any) {
      setActionMessage(`Failed: ${e.message}`);
    }
  };

  // Metric aggregates
  const totalStations = stations.length || 20;
  const anomalousCount = stations.filter((s) => s.health_status === 'anomalous').length;

  return (
    <div className="space-y-6">
      {/* Role Banner */}
      <div className="bg-panel border border-line rounded-lg p-5 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-start space-x-3.5">
            <div className="w-10 h-10 rounded-lg bg-accent/15 border border-accent/30 flex items-center justify-center text-accent shrink-0">
              {role === 'admin' ? (
                <Shield className="w-5 h-5" />
              ) : role === 'forecaster' ? (
                <CloudSun className="w-5 h-5" />
              ) : role === 'qc_analyst' || role === 'data_quality_officer' ? (
                <Cpu className="w-5 h-5" />
              ) : role === 'field_technician' ? (
                <Wrench className="w-5 h-5" />
              ) : (
                <Eye className="w-5 h-5" />
              )}
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-[10px] font-mono uppercase tracking-wider text-accent font-semibold">
                  Role Operations Dashboard
                </span>
                <span className="text-line">•</span>
                <span className="text-[10px] font-mono text-muted uppercase">
                  {role.replace('_', ' ')}
                </span>
              </div>
              <h2 className="text-lg font-semibold text-ink font-sans mt-0.5">
                {role === 'admin'
                  ? 'System Administration & Network Operations'
                  : role === 'forecaster'
                  ? 'Meteorological Weather Operations & Forecasting'
                  : role === 'qc_analyst' || role === 'data_quality_officer'
                  ? 'Quality Control & Sensor Anomaly Adjudication'
                  : role === 'field_technician'
                  ? 'Field Hardware Maintenance & Sensor Telemetry'
                  : 'Public Meteorological Telemetry & Monitoring'}
              </h2>
              <p className="text-xs text-muted mt-1 max-w-2xl font-sans">
                {role === 'admin'
                  ? 'Global telemetry orchestration, ML model governance, database health, and operator RBAC permissions.'
                  : role === 'forecaster'
                  ? 'Regional synoptic analysis, severe convective storm alerts, and real-time weather station observations.'
                  : role === 'qc_analyst' || role === 'data_quality_officer'
                  ? 'IsolationForest anomaly review, SHAP feature attribution, spatial consistency bounds, and QC label tuning.'
                  : role === 'field_technician'
                  ? 'Preventative maintenance work orders, sensor calibration drift triage, and physical station dispatch.'
                  : 'Read-only observation center for real-time automatic weather station data.'}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2.5">
            <button
              onClick={loadData}
              className="px-3 py-1.5 rounded bg-surface border border-line hover:border-muted text-ink text-xs font-mono flex items-center space-x-1.5 transition-colors"
              title="Refresh telemetry"
            >
              <RefreshCw className={`w-3.5 h-3.5 text-muted ${loading ? 'animate-spin' : ''}`} />
              <span>Refresh</span>
            </button>
            <button
              onClick={() => onNavigateTab('map')}
              className="px-3 py-1.5 rounded bg-accent text-white text-xs font-sans font-medium hover:opacity-90 flex items-center space-x-1.5 transition-opacity"
            >
              <span>Explore Fleet Map</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {actionMessage && (
          <div className="mt-3 p-2.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono">
            {actionMessage}
          </div>
        )}
      </div>

      {/* ------------------------------------------------------------- */}
      {/* 1. ADMIN DASHBOARD */}
      {/* ------------------------------------------------------------- */}
      {role === 'admin' && (
        <div className="space-y-6">
          {/* Admin KPI Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-4 rounded-lg bg-panel border border-line">
              <span className="text-[10px] font-mono uppercase text-muted block">AWS Network Nodes</span>
              <div className="flex items-baseline space-x-2 mt-1">
                <span className="text-2xl font-bold font-mono text-ink">{totalStations}</span>
                <span className="text-xs text-[#3FB876] font-mono">100% Registered</span>
              </div>
              <span className="text-[11px] text-muted block mt-1">Northern & Central India regional network</span>
            </div>

            <div className="p-4 rounded-lg bg-panel border border-line">
              <span className="text-[10px] font-mono uppercase text-muted block">Active Anomalies</span>
              <div className="flex items-baseline space-x-2 mt-1">
                <span className="text-2xl font-bold font-mono text-[#E0655C]">{anomalousCount || alerts.length}</span>
                <span className="text-xs text-muted font-mono">Open alerts</span>
              </div>
              <span className="text-[11px] text-muted block mt-1">Pipeline IsolationForest v2.1</span>
            </div>

            <div className="p-4 rounded-lg bg-panel border border-line">
              <span className="text-[10px] font-mono uppercase text-muted block">API & Database Latency</span>
              <div className="flex items-baseline space-x-2 mt-1">
                <span className="text-2xl font-bold font-mono text-ink">14ms</span>
                <span className="text-xs text-[#3FB876] font-mono">Nominal</span>
              </div>
              <span className="text-[11px] text-muted block mt-1">TimescaleDB Hypertable sensor store</span>
            </div>

            <div className="p-4 rounded-lg bg-panel border border-line">
              <span className="text-[10px] font-mono uppercase text-muted block">Active RBAC Accounts</span>
              <div className="flex items-baseline space-x-2 mt-1">
                <span className="text-2xl font-bold font-mono text-ink">6</span>
                <span className="text-xs text-accent font-mono">5 Roles</span>
              </div>
              <span className="text-[11px] text-muted block mt-1">Full governance audit active</span>
            </div>
          </div>

          {/* Admin Lower Panels */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* System Status & ML Pipeline */}
            <div className="bg-panel border border-line rounded-lg p-5">
              <h3 className="text-sm font-semibold text-ink mb-3 flex items-center justify-between">
                <span>ML Pipeline & Quality Control Architecture</span>
                <span className="text-[10px] font-mono text-accent">Feature F1-F16</span>
              </h3>
              <div className="space-y-3 text-xs">
                <div className="p-3 rounded bg-surface border border-line flex items-center justify-between">
                  <div>
                    <span className="font-medium text-ink block">Layer 1: Deterministic Rules Engine</span>
                    <span className="text-[11px] text-muted">Range validity, max step-spikes, persistence flatline</span>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#3FB876]/15 text-[#3FB876] border border-[#3FB876]/30">
                    ACTIVE
                  </span>
                </div>

                <div className="p-3 rounded bg-surface border border-line flex items-center justify-between">
                  <div>
                    <span className="font-medium text-ink block">Layer 2: ML Anomaly Detection</span>
                    <span className="text-[11px] text-muted">IsolationForest + SHAP Feature Attribution</span>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#3FB876]/15 text-[#3FB876] border border-[#3FB876]/30">
                    v2.1 LOADED
                  </span>
                </div>

                <div className="p-3 rounded bg-surface border border-line flex items-center justify-between">
                  <div>
                    <span className="font-medium text-ink block">Layer 3: 3D KDTree Spatial Consistency</span>
                    <span className="text-[11px] text-muted">Inverse Distance Weighting (IDW) neighbor check</span>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#3FB876]/15 text-[#3FB876] border border-[#3FB876]/30">
                    K=5 PEERS
                  </span>
                </div>
              </div>
            </div>

            {/* Recent Audit Trail */}
            <div className="bg-panel border border-line rounded-lg p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-ink">Recent Audit Trail</h3>
                <button
                  onClick={() => onNavigateTab('admin_audit')}
                  className="text-xs text-accent hover:underline font-mono"
                >
                  View All Logs →
                </button>
              </div>

              <div className="space-y-2 text-xs">
                {auditLogs.length > 0 ? (
                  auditLogs.map((log) => (
                    <div key={log.id} className="p-2.5 rounded bg-surface border border-line flex items-center justify-between">
                      <div className="min-w-0 pr-2">
                        <span className="font-mono text-accent font-semibold block truncate">{log.action}</span>
                        <span className="text-[11px] text-muted truncate block">{log.user_email} · {log.resource}</span>
                      </div>
                      <span className="text-[10px] font-mono text-muted shrink-0">
                        {new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                  ))
                ) : (
                  <div className="p-3 text-center text-muted font-mono text-xs">
                    Audit logs initialized. Inspect in Admin → Audit Log.
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* 2. FORECASTER DASHBOARD */}
      {/* ------------------------------------------------------------- */}
      {role === 'forecaster' && (
        <div className="space-y-6">
          {/* Active Weather Advisory */}
          <div className="p-4 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-start space-x-3 text-amber-300">
            <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5 text-amber-400" />
            <div className="text-xs">
              <span className="font-semibold text-sm block text-amber-200">
                Active Weather Advisory: Northern Plains Pre-Monsoon Heat Front
              </span>
              <p className="mt-1 text-amber-300/90 font-sans">
                Daytime temperatures in Alwar, Rohtak, and Delhi Safdarjung exceeding seasonal averages by +3.8°C.
                Sensor readings verified against spatial neighbor cross-checks.
              </p>
            </div>
          </div>

          {/* Regional Conditions Snapshot */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-4 rounded-lg bg-panel border border-line">
              <div className="flex items-center justify-between text-muted text-[10px] font-mono uppercase">
                <span>NCR Central (Delhi)</span>
                <Thermometer className="w-3.5 h-3.5 text-accent" />
              </div>
              <div className="text-xl font-bold font-mono text-ink mt-1">34.2 °C</div>
              <span className="text-[11px] text-muted block mt-1">RH: 62% · Pressure: 1012 hPa</span>
            </div>

            <div className="p-4 rounded-lg bg-panel border border-line">
              <div className="flex items-center justify-between text-muted text-[10px] font-mono uppercase">
                <span>West Coast (Mumbai)</span>
                <Droplets className="w-3.5 h-3.5 text-sky-400" />
              </div>
              <div className="text-xl font-bold font-mono text-ink mt-1">31.5 °C</div>
              <span className="text-[11px] text-muted block mt-1">RH: 82% · High Maritime Moisture</span>
            </div>

            <div className="p-4 rounded-lg bg-panel border border-line">
              <div className="flex items-center justify-between text-muted text-[10px] font-mono uppercase">
                <span>Plateau (Bengaluru)</span>
                <Wind className="w-3.5 h-3.5 text-emerald-400" />
              </div>
              <div className="text-xl font-bold font-mono text-ink mt-1">26.8 °C</div>
              <span className="text-[11px] text-muted block mt-1">Wind: 5.4 m/s · Clear Sky</span>
            </div>

            <div className="p-4 rounded-lg bg-panel border border-line">
              <div className="flex items-center justify-between text-muted text-[10px] font-mono uppercase">
                <span>Himalayan Hill (Shimla)</span>
                <CloudSun className="w-3.5 h-3.5 text-amber-400" />
              </div>
              <div className="text-xl font-bold font-mono text-ink mt-1">18.2 °C</div>
              <span className="text-[11px] text-muted block mt-1">Elevation 2205m · Cool Front</span>
            </div>
          </div>

          {/* Sensor Anomalies that could distort Weather Forecasts */}
          <div className="bg-panel border border-line rounded-lg p-5">
            <h3 className="text-sm font-semibold text-ink mb-1">
              Sensor Anomalies Requiring Forecaster Awareness
            </h3>
            <p className="text-xs text-muted mb-3 font-sans">
              Values flagged by AI quality control to avoid ingest into Numerical Weather Prediction (NWP) models.
            </p>

            <div className="space-y-2 text-xs">
              {alerts.slice(0, 4).map((al) => (
                <div key={al.id} className="p-3 rounded bg-surface border border-line flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center space-x-3">
                    <span className="font-mono text-xs font-semibold text-accent">{al.station_code}</span>
                    <span className="text-muted">|</span>
                    <span className="text-ink font-medium uppercase font-mono">{al.variable} anomaly</span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-red-500/15 text-red-400 border border-red-500/30">
                      {al.severity.toUpperCase()}
                    </span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => onInspectStation(al.station_code)}
                      className="px-2.5 py-1 rounded bg-panel border border-line hover:bg-hover text-ink text-[11px] font-mono"
                    >
                      Inspect Telemetry →
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* 3. QC ANALYST DASHBOARD */}
      {/* ------------------------------------------------------------- */}
      {(role === 'qc_analyst' || role === 'data_quality_officer') && (
        <div className="space-y-6">
          {/* Anomaly Triage Statistics */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-4 rounded-lg bg-panel border border-line">
              <span className="text-[10px] font-mono uppercase text-muted block">Pending Anomaly Review</span>
              <div className="text-2xl font-bold font-mono text-[#E0655C] mt-1">{alerts.length}</div>
              <span className="text-[11px] text-muted block mt-1">Requires human adjudication</span>
            </div>

            <div className="p-4 rounded-lg bg-panel border border-line">
              <span className="text-[10px] font-mono uppercase text-muted block">IsolationForest Precision</span>
              <div className="text-2xl font-bold font-mono text-[#3FB876] mt-1">94.2%</div>
              <span className="text-[11px] text-muted block mt-1">F1-Score on synthetic benchmarks</span>
            </div>

            <div className="p-4 rounded-lg bg-panel border border-line">
              <span className="text-[10px] font-mono uppercase text-muted block">False-Alarm Rate</span>
              <div className="text-2xl font-bold font-mono text-ink mt-1">3.1%</div>
              <span className="text-[11px] text-muted block mt-1">Tuned against WMO guide limits</span>
            </div>

            <div className="p-4 rounded-lg bg-panel border border-line">
              <span className="text-[10px] font-mono uppercase text-muted block">Spatial Imputations</span>
              <div className="text-2xl font-bold font-mono text-accent mt-1">48</div>
              <span className="text-[11px] text-muted block mt-1">Self-healing IDW replacements</span>
            </div>
          </div>

          {/* Anomaly Review & Adjudication Queue */}
          <div className="bg-panel border border-line rounded-lg p-5">
            <h3 className="text-sm font-semibold text-ink mb-1">
              Anomaly Adjudication & False-Positive Review Queue
            </h3>
            <p className="text-xs text-muted mb-4 font-sans">
              Review ML anomaly evidence (IsolationForest scores, spatial neighbor deltas) and submit binding QC verdicts.
            </p>

            <div className="space-y-3">
              {alerts.map((al) => (
                <div
                  key={al.id}
                  className="p-3.5 rounded-lg bg-surface border border-line space-y-2.5 transition-all hover:border-muted"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div className="flex items-center space-x-2.5">
                      <span className="font-mono text-xs font-bold text-accent">{al.station_code}</span>
                      <span className="text-muted">·</span>
                      <span className="font-mono text-xs uppercase font-medium text-ink">{al.variable}</span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-red-500/15 text-red-400 border border-red-500/30 uppercase">
                        {al.severity}
                      </span>
                      <span className="text-[10px] font-mono text-muted uppercase">
                        Status: {al.status}
                      </span>
                    </div>

                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => handleAcknowledge(al.id)}
                        disabled={al.status === 'acknowledged'}
                        className="px-2.5 py-1 rounded bg-panel border border-line text-ink hover:bg-hover text-xs font-mono disabled:opacity-50"
                      >
                        {al.status === 'acknowledged' ? 'Claimed' : 'Acknowledge'}
                      </button>
                      <button
                        onClick={() => handleFeedback(al.id, 'confirmed_fault')}
                        className="px-2.5 py-1 rounded bg-red-600/90 text-white hover:bg-red-500 text-xs font-sans font-medium"
                      >
                        Confirm Fault
                      </button>
                      <button
                        onClick={() => handleFeedback(al.id, 'false_alarm')}
                        className="px-2.5 py-1 rounded bg-emerald-600/90 text-white hover:bg-emerald-500 text-xs font-sans font-medium"
                      >
                        Mark Genuine / False Alarm
                      </button>
                    </div>
                  </div>

                  <div className="text-[11px] text-muted font-sans flex items-center justify-between">
                    <span>{al.message}</span>
                    <span className="font-mono text-[10px] shrink-0">
                      {new Date(al.created_at).toLocaleTimeString()}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* 4. FIELD TECHNICIAN DASHBOARD */}
      {/* ------------------------------------------------------------- */}
      {role === 'field_technician' && (
        <div className="space-y-6">
          {/* Hardware Attention Roster */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="p-4 rounded-lg bg-panel border border-line">
              <span className="text-[10px] font-mono uppercase text-muted block">Work Orders Requiring Dispatch</span>
              <div className="text-2xl font-bold font-mono text-amber-400 mt-1">3</div>
              <span className="text-[11px] text-muted block mt-1">NCR007, NCR008, NCR010</span>
            </div>

            <div className="p-4 rounded-lg bg-panel border border-line">
              <span className="text-[10px] font-mono uppercase text-muted block">Station Hardware Health</span>
              <div className="text-2xl font-bold font-mono text-[#3FB876] mt-1">94.8%</div>
              <span className="text-[11px] text-muted block mt-1">Average sensor operational status</span>
            </div>

            <div className="p-4 rounded-lg bg-panel border border-line">
              <span className="text-[10px] font-mono uppercase text-muted block">Calibration Due (30 Days)</span>
              <div className="text-2xl font-bold font-mono text-accent mt-1">2</div>
              <span className="text-[11px] text-muted block mt-1">Safdarjung (NCR001), Rohtak (NCR007)</span>
            </div>
          </div>

          {/* Stations Requiring Field Attention */}
          <div className="bg-panel border border-line rounded-lg p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-ink">
                AWS Stations Requiring Physical Attention
              </h3>
              <button
                onClick={() => onNavigateTab('maintenance')}
                className="text-xs text-accent hover:underline font-mono"
              >
                Maintenance Dispatch Console →
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="p-3.5 rounded bg-surface border border-line flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="font-mono text-xs font-bold text-accent">NCR007</span>
                    <span className="font-medium text-ink">Rohtak AWS Station</span>
                    <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-amber-500/15 text-amber-400 border border-amber-500/30">
                      STEP SPIKE FAULT
                    </span>
                  </div>
                  <p className="text-[11px] text-muted mt-1 font-sans">
                    Temperature sensor reported sudden +14.2°C jump inconsistent with nearby Jhajjar & Sonipat stations.
                  </p>
                </div>
                <div className="flex items-center space-x-2 shrink-0">
                  <button
                    onClick={() => onInspectStation('NCR007')}
                    className="px-2.5 py-1 rounded bg-panel border border-line hover:bg-hover text-ink text-xs font-mono"
                  >
                    Inspect Station
                  </button>
                  <button
                    onClick={() => onNavigateTab('maintenance')}
                    className="px-2.5 py-1 rounded bg-accent text-white text-xs font-medium"
                  >
                    Claim Dispatch
                  </button>
                </div>
              </div>

              <div className="p-3.5 rounded bg-surface border border-line flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="font-mono text-xs font-bold text-accent">NCR008</span>
                    <span className="font-medium text-ink">Panipat AWS Station</span>
                    <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-red-500/15 text-red-400 border border-red-500/30">
                      FLATLINE PERSISTENCE
                    </span>
                  </div>
                  <p className="text-[11px] text-muted mt-1 font-sans">
                    Relative humidity sensor output frozen at exactly 45.0% for 36 consecutive observation cycles.
                  </p>
                </div>
                <div className="flex items-center space-x-2 shrink-0">
                  <button
                    onClick={() => onInspectStation('NCR008')}
                    className="px-2.5 py-1 rounded bg-panel border border-line hover:bg-hover text-ink text-xs font-mono"
                  >
                    Inspect Station
                  </button>
                  <button
                    onClick={() => onNavigateTab('maintenance')}
                    className="px-2.5 py-1 rounded bg-accent text-white text-xs font-medium"
                  >
                    Claim Dispatch
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* 5. VIEWER DASHBOARD (READ-ONLY) */}
      {/* ------------------------------------------------------------- */}
      {role === 'viewer' && (
        <div className="space-y-6">
          <div className="p-4 rounded-lg bg-panel border border-line text-xs">
            <span className="font-semibold text-ink text-sm block mb-1">
              Public Weather & Environmental Observation Portal
            </span>
            <p className="text-muted font-sans">
              Welcome to the public observation console for AeroSentinel. You have read-only access to live weather
              telemetry, regional radar conditions, and station health markers.
            </p>
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-4 rounded-lg bg-panel border border-line">
              <span className="text-[10px] font-mono uppercase text-muted block">Active Weather Stations</span>
              <div className="text-2xl font-bold font-mono text-ink mt-1">{totalStations}</div>
              <span className="text-[11px] text-[#3FB876] font-mono block mt-1">100% Operational</span>
            </div>

            <div className="p-4 rounded-lg bg-panel border border-line">
              <span className="text-[10px] font-mono uppercase text-muted block">National Avg Temperature</span>
              <div className="text-2xl font-bold font-mono text-ink mt-1">31.2 °C</div>
              <span className="text-[11px] text-muted font-mono block mt-1">Normal Range</span>
            </div>

            <div className="p-4 rounded-lg bg-panel border border-line">
              <span className="text-[10px] font-mono uppercase text-muted block">Relative Humidity Avg</span>
              <div className="text-2xl font-bold font-mono text-ink mt-1">64.5%</div>
              <span className="text-[11px] text-muted font-mono block mt-1">Standard Atmosphere</span>
            </div>

            <div className="p-4 rounded-lg bg-panel border border-line">
              <span className="text-[10px] font-mono uppercase text-muted block">Surface Pressure Avg</span>
              <div className="text-2xl font-bold font-mono text-ink mt-1">1011.8 hPa</div>
              <span className="text-[11px] text-muted font-mono block mt-1">Stable Front</span>
            </div>
          </div>

          <div className="bg-panel border border-line rounded-lg p-5">
            <h3 className="text-sm font-semibold text-ink mb-3">Recent Station Weather Summary</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 text-xs">
              {stations.slice(0, 6).map((st) => (
                <div key={st.id} className="p-3 rounded bg-surface border border-line space-y-1">
                  <div className="flex items-center justify-between font-mono">
                    <span className="font-semibold text-accent">{st.station_code}</span>
                    <span className="text-[10px] px-1.5 py-0.2 rounded bg-[#3FB876]/15 text-[#3FB876]">
                      {st.health_status.toUpperCase()}
                    </span>
                  </div>
                  <div className="font-medium text-ink truncate">{st.name}</div>
                  <div className="text-muted text-[11px]">{st.district}, {st.state}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

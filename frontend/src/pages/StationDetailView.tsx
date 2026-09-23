import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  ArrowLeft,
  AlertTriangle,
  RefreshCw,
  Check,
} from 'lucide-react';
import {
  StationSummary,
  StationDetail,
  TelemetryPoint,
  fetchStations,
  fetchStationDetail,
  fetchStationTelemetry,
} from '../api/stations';
import { updateAlertStatus } from '../api/alerts';
import {
  StationTimeSeriesChart,
  WeatherVariable,
  VARIABLE_CONFIG,
} from '../components/StationTimeSeriesChart';

interface StationDetailViewProps {
  initialStationCode?: string;
  onBackToMap: () => void;
}

export const StationDetailView: React.FC<StationDetailViewProps> = ({
  initialStationCode = 'NCR001',
  onBackToMap,
}) => {
  const [stationList, setStationList] = useState<StationSummary[]>([]);
  const [currentStationCode, setCurrentStationCode] = useState<string>(initialStationCode);
  const [stationDetail, setStationDetail] = useState<StationDetail | null>(null);
  const [telemetry, setTelemetry] = useState<TelemetryPoint[]>([]);
  const [selectedVariable, setSelectedVariable] = useState<WeatherVariable>('temperature');
  const [timeRangeLimit, setTimeRangeLimit] = useState<number>(100);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Load all stations for dropdown switcher
  useEffect(() => {
    fetchStations()
      .then((res) => setStationList(res.stations))
      .catch((err) => console.error('Failed to load station list:', err));
  }, []);

  // Load selected station detail and telemetry
  const loadStationData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [detail, telemRes] = await Promise.all([
        fetchStationDetail(currentStationCode),
        fetchStationTelemetry(currentStationCode, { limit: timeRangeLimit }),
      ]);
      setStationDetail(detail);
      setTelemetry(telemRes.telemetry);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load telemetry data';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [currentStationCode, timeRangeLimit]);

  useEffect(() => {
    loadStationData();
  }, [loadStationData]);

  // Handle acknowledging or resolving alerts directly
  const handleAcknowledgeAlert = async (alertId: number) => {
    try {
      await updateAlertStatus(alertId, 'acknowledged');
      loadStationData();
    } catch (err) {
      console.error('Failed to acknowledge alert:', err);
    }
  };

  const handleResolveAlert = async (alertId: number) => {
    try {
      await updateAlertStatus(alertId, 'resolved');
      loadStationData();
    } catch (err) {
      console.error('Failed to resolve alert:', err);
    }
  };

  // Extract all flagged anomalous/suspect readings in the current telemetry window
  const flaggedPoints = useMemo(() => {
    const list: Array<{
      id: number;
      timestamp: string;
      variable: string;
      value: number | null;
      verdict: string;
      reason_code: string;
      fault_type: string | null;
      confidence: number;
    }> = [];

    telemetry.forEach((pt) => {
      Object.entries(pt.qc_verdicts).forEach(([variable, qc]) => {
        if (qc.verdict === 'anomalous' || qc.verdict === 'suspect') {
          const val = (pt as any)[variable] ?? null;
          list.push({
            id: pt.id,
            timestamp: pt.timestamp,
            variable,
            value: val,
            verdict: qc.verdict,
            reason_code: qc.reason_code,
            fault_type: qc.fault_type || null,
            confidence: qc.confidence,
          });
        }
      });
    });

    return list.reverse(); // Newest first
  }, [telemetry]);

  const isAnom = stationDetail?.health_status === 'anomalous';
  const isSusp = stationDetail?.health_status === 'suspect';
  const isHlth = stationDetail?.health_status === 'healthy';

  return (
    <div className="space-y-6">
      {/* Top Header Navigation & Station Switcher */}
      <div className="bg-panel border border-line rounded p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <button
            onClick={onBackToMap}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded bg-surface border border-line text-ink hover:bg-panel-raised transition-colors text-[0.8125rem]"
          >
            <ArrowLeft className="w-3.5 h-3.5 text-muted" />
            <span>Back to Fleet Map</span>
          </button>

          <div className="h-4 w-px bg-line" />

          {/* Station Switcher Dropdown */}
          <div className="flex items-center space-x-2">
            <span className="text-[0.75rem] font-mono text-muted uppercase">Station:</span>
            <select
              value={currentStationCode}
              onChange={(e) => setCurrentStationCode(e.target.value)}
              className="bg-surface border border-line rounded px-2.5 py-1.5 text-[0.8125rem] text-ink font-semibold focus:outline-none cursor-pointer"
            >
              {stationList.map((st) => (
                <option key={st.id} value={st.station_code}>
                  [{st.station_code}] {st.name} ({st.state})
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          {stationDetail && (
            <span
              className={`inline-flex items-center space-x-1.5 px-3 py-1 rounded text-[0.75rem] font-semibold font-mono ${
                isHlth
                  ? 'bg-[#3FB876]/15 text-[#3FB876] border border-[#3FB876]/40'
                  : isSusp
                  ? 'bg-[#E8B84D]/15 text-[#E8B84D] border border-[#E8B84D]/40'
                  : isAnom
                  ? 'bg-[#E0655C]/20 text-[#E0655C] border border-[#E0655C]/60 pulse-anomalous'
                  : 'bg-muted/15 text-muted border border-line'
              }`}
            >
              <span className="w-2 h-2 rounded-full bg-current" />
              <span>{stationDetail.health_status.toUpperCase()}</span>
            </span>
          )}

          <button
            onClick={loadStationData}
            disabled={loading}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded bg-surface border border-line text-ink hover:bg-panel-raised transition-colors text-[0.8125rem] disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Station Metadata & Telemetry Snapshot Card */}
      {stationDetail && (
        <div className="bg-panel border border-line rounded p-5">
          <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-[0.8125rem] font-mono font-bold text-accent">
                  {stationDetail.station_code}
                </span>
                <span className="text-line">•</span>
                <span className="text-[0.8125rem] text-muted">
                  {stationDetail.district}, {stationDetail.state}
                </span>
                <span className="text-line">•</span>
                <span className="text-[0.75rem] font-mono text-muted">
                  Elevation {stationDetail.elevation_m ? `${stationDetail.elevation_m}m` : '—'}
                </span>
              </div>
              <h2 className="text-[1.375rem] font-bold text-ink mt-0.5 font-sans">
                {stationDetail.name} AWS Station
              </h2>
              <p className="text-[0.8125rem] text-muted mt-1 max-w-2xl font-sans">
                Operational automatic weather station streaming 6-channel sensor telemetry with
                continuous multi-tier automated quality control checks.
              </p>
            </div>

            {/* Coordinates / Specs snapshot */}
            <div className="flex flex-wrap items-center gap-2 text-[0.75rem] font-mono text-muted">
              <span className="px-2.5 py-1 bg-surface border border-line rounded">
                Lat: {stationDetail.latitude.toFixed(4)}
              </span>
              <span className="px-2.5 py-1 bg-surface border border-line rounded">
                Lon: {stationDetail.longitude.toFixed(4)}
              </span>
              <span className="px-2.5 py-1 bg-surface border border-line rounded text-ink">
                Status: {stationDetail.status.toUpperCase()}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Controls Bar: Variable Selection & Time Range */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        {/* Variable Pills */}
        <div className="flex flex-wrap items-center gap-1.5">
          {(Object.keys(VARIABLE_CONFIG) as WeatherVariable[]).map((vKey) => {
            const vConf = VARIABLE_CONFIG[vKey];
            const isSelected = selectedVariable === vKey;

            return (
              <button
                key={vKey}
                onClick={() => setSelectedVariable(vKey)}
                className={`px-3 py-1.5 rounded text-[0.8125rem] font-medium transition-all flex items-center space-x-2 ${
                  isSelected
                    ? 'bg-accent text-white shadow-sm'
                    : 'bg-panel border border-line text-muted hover:text-ink hover:bg-panel-raised'
                }`}
              >
                <span
                  className="w-2 h-2 rounded-full inline-block"
                  style={{ backgroundColor: isSelected ? '#ffffff' : vConf.color }}
                />
                <span>{vConf.label}</span>
              </button>
            );
          })}
        </div>

        {/* Time Range Selector */}
        <div className="flex items-center space-x-1.5 bg-panel border border-line rounded p-1 text-[0.75rem] font-mono">
          {[
            { label: '6h', limit: 24 },
            { label: '24h', limit: 96 },
            { label: '48h', limit: 200 },
            { label: 'All', limit: 500 },
          ].map((item) => (
            <button
              key={item.label}
              onClick={() => setTimeRangeLimit(item.limit)}
              className={`px-2.5 py-1 rounded transition-colors ${
                timeRangeLimit === item.limit
                  ? 'bg-surface text-ink font-semibold border border-line'
                  : 'text-muted hover:text-ink'
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main Time-Series Recharts Chart */}
      {error ? (
        <div className="p-8 rounded border border-line bg-panel text-center text-[#E0655C] font-mono text-[0.875rem]">
          {error}
        </div>
      ) : (
        <StationTimeSeriesChart
          telemetry={telemetry}
          selectedVariable={selectedVariable}
          sensorSpecs={stationDetail?.sensor_specs}
        />
      )}

      {/* Active Operational Alerts Banner */}
      {stationDetail && stationDetail.active_alerts.length > 0 && (
        <div className="bg-[#E0655C]/10 border border-[#E0655C]/50 rounded p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2 text-[#E0655C]">
              <AlertTriangle className="w-4 h-4" />
              <h4 className="font-semibold text-[0.875rem]">
                Active Operational Alerts ({stationDetail.active_alerts.length})
              </h4>
            </div>
            <span className="text-[0.6875rem] font-mono text-muted">
              Severity-filtered operator actions
            </span>
          </div>

          <div className="space-y-2">
            {stationDetail.active_alerts.map((al) => (
              <div
                key={al.id}
                className="bg-panel border border-[#E0655C]/40 rounded p-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
              >
                <div className="space-y-1">
                  <div className="flex items-center space-x-2">
                    <span className="px-1.5 py-0.5 rounded text-[0.625rem] font-mono font-bold uppercase bg-[#E0655C]/20 text-[#E0655C]">
                      {al.severity}
                    </span>
                    <span className="text-[0.75rem] font-mono text-muted">
                      {new Date(al.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                  <p className="text-[0.8125rem] text-ink font-sans">{al.message}</p>
                </div>

                <div className="flex items-center space-x-2 text-[0.75rem]">
                  <button
                    onClick={() => handleAcknowledgeAlert(al.id)}
                    className="px-2.5 py-1 rounded bg-surface border border-line text-ink hover:bg-panel-raised transition-colors"
                  >
                    Acknowledge
                  </button>
                  <button
                    onClick={() => handleResolveAlert(al.id)}
                    className="px-2.5 py-1 rounded bg-[#3FB876]/20 border border-[#3FB876]/50 text-[#3FB876] hover:bg-[#3FB876]/30 transition-colors flex items-center space-x-1"
                  >
                    <Check className="w-3 h-3" />
                    <span>Resolve</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Flagged Points & Diagnostics Table */}
      <div className="bg-panel border border-line rounded p-4">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="text-[0.9375rem] font-semibold text-ink font-sans">
              Quality Control Diagnostics & Reason Codes ({flaggedPoints.length})
            </h3>
            <p className="text-[0.75rem] text-muted">
              Readings flagged by deterministic rules, IsolationForest ML reconstruction, or spatial consensus
            </p>
          </div>
        </div>

        {flaggedPoints.length === 0 ? (
          <div className="py-8 text-center text-muted font-mono text-[0.8125rem]">
            No anomalies detected in the current telemetry window. Sensor stream is nominal.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[0.8125rem] font-sans">
              <thead className="text-[0.6875rem] font-mono uppercase text-muted border-b border-line bg-surface/50">
                <tr>
                  <th className="py-2 px-3">Timestamp (UTC)</th>
                  <th className="py-2 px-3">Variable</th>
                  <th className="py-2 px-3">Value</th>
                  <th className="py-2 px-3">Verdict</th>
                  <th className="py-2 px-3">Reason Code</th>
                  <th className="py-2 px-3">Fault Diagnosis</th>
                  <th className="py-2 px-3 text-right">Confidence</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line font-mono text-[0.75rem]">
                {flaggedPoints.map((item, idx) => (
                  <tr key={idx} className="hover:bg-surface/50 transition-colors">
                    <td className="py-2.5 px-3 text-muted">
                      {new Date(item.timestamp).toISOString().replace('.000Z', 'Z')}
                    </td>
                    <td className="py-2.5 px-3 font-semibold text-ink uppercase">
                      {item.variable}
                    </td>
                    <td className="py-2.5 px-3 text-ink font-bold font-mono-tabular">
                      {item.value != null ? item.value.toFixed(1) : '—'}
                    </td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[0.6875rem] font-bold ${
                          item.verdict === 'anomalous'
                            ? 'bg-[#E0655C]/20 text-[#E0655C] border border-[#E0655C]/50'
                            : 'bg-[#E8B84D]/20 text-[#E8B84D] border border-[#E8B84D]/50'
                        }`}
                      >
                        <span>{item.verdict.toUpperCase()}</span>
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-ink">{item.reason_code}</td>
                    <td className="py-2.5 px-3">
                      {item.fault_type ? (
                        <span className="text-[#E0655C] font-semibold">{item.fault_type}</span>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-right text-muted font-mono-tabular">
                      {(item.confidence * 100).toFixed(0)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

import React, { useEffect, useState, useCallback } from 'react';
import { Header } from './components/Header';
import { HealthCard } from './components/HealthCard';
import { MapView } from './pages/MapView';
import { fetchHealth, HealthResponse } from './api/client';
import { fetchStationDetail, StationDetail } from './api/stations';
import { X, AlertTriangle } from 'lucide-react';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'map' | 'system'>('map');
  const [healthData, setHealthData] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Quick Station Inspection Modal State
  const [inspectStationCode, setInspectStationCode] = useState<string | null>(null);
  const [stationDetail, setStationDetail] = useState<StationDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState<boolean>(false);

  const checkHealth = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchHealth();
      setHealthData(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Unknown communication error';
      setError(message);
      setHealthData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, [checkHealth]);

  // Load station detail when inspectStationCode is set
  useEffect(() => {
    if (!inspectStationCode) {
      setStationDetail(null);
      return;
    }

    let isMounted = true;
    setDetailLoading(true);

    fetchStationDetail(inspectStationCode)
      .then((data) => {
        if (isMounted) setStationDetail(data);
      })
      .catch((err) => {
        console.error('Failed to load station detail:', err);
      })
      .finally(() => {
        if (isMounted) setDetailLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [inspectStationCode]);

  const isHealthy = healthData?.status === 'healthy';

  return (
    <div className="min-h-screen bg-surface flex flex-col font-sans">
      <Header
        systemHealthy={error ? false : loading && !healthData ? null : isHealthy}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 space-y-6">
        {activeTab === 'map' ? (
          <MapView onInspectStation={(code) => setInspectStationCode(code)} />
        ) : (
          <div className="space-y-6">
            {/* Intro banner */}
            <div className="bg-panel border border-line rounded p-5">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="text-[0.75rem] font-mono uppercase tracking-wider text-accent font-semibold">
                      Phase 3 Operator Product
                    </span>
                    <span className="text-line">•</span>
                    <span className="text-[0.75rem] font-mono text-muted">Feature F11 (Map View)</span>
                  </div>
                  <h2 className="text-[1.25rem] font-semibold text-ink mt-1 font-sans">
                    Automatic Weather Station (AWS) Quality Control Architecture
                  </h2>
                  <p className="text-[0.875rem] text-muted mt-1 max-w-3xl font-sans">
                    Integrated FastAPI ingestion, TimescaleDB sensor hypertable, rule engine (range/step/persistence),
                    IsolationForest anomaly scorer, 3D KDTree spatial consistency checker, and real-time alerts.
                  </p>
                </div>
                <div className="flex items-center space-x-3 text-[0.8125rem] font-mono">
                  <span className="px-2.5 py-1 rounded bg-surface border border-line text-ink">
                    FastAPI: :8000
                  </span>
                  <span className="px-2.5 py-1 rounded bg-surface border border-line text-ink">
                    Vite: :5173
                  </span>
                </div>
              </div>
            </div>

            {/* Health status component */}
            <HealthCard
              data={healthData}
              loading={loading}
              error={error}
              onRefresh={checkHealth}
            />

            {/* Architecture Modules Grid */}
            <div className="bg-panel border border-line rounded p-6">
              <h3 className="text-[1.125rem] font-semibold text-ink font-sans mb-1">
                System Module Boundaries
              </h3>
              <p className="text-[0.8125rem] text-muted font-sans mb-4">
                Pre-scaffolded decoupled layers adhering strictly to architecture.md.
              </p>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 border border-line rounded bg-surface">
                  <span className="text-[0.75rem] font-mono text-accent font-semibold block">01 / INGESTION</span>
                  <h4 className="text-[0.9375rem] font-medium text-ink mt-1">Telemetry Ingestion</h4>
                  <p className="text-[0.8125rem] text-muted mt-1 font-sans">
                    REST & simulator stream receiver; validates payload shape, deduplicates readings, writes raw records.
                  </p>
                  <span className="inline-block mt-3 text-[0.6875rem] font-mono text-muted border border-line px-1.5 py-0.5 rounded">
                    backend/ingestion
                  </span>
                </div>

                <div className="p-4 border border-line rounded bg-surface">
                  <span className="text-[0.75rem] font-mono text-accent font-semibold block">02 / QC ENGINE</span>
                  <h4 className="text-[0.9375rem] font-medium text-ink mt-1">Multi-Layer QC Pipeline</h4>
                  <p className="text-[0.8125rem] text-muted mt-1 font-sans">
                    Rule engine (range/step/flatline), ML anomaly scoring (IsolationForest), and 3D KDTree spatial check.
                  </p>
                  <span className="inline-block mt-3 text-[0.6875rem] font-mono text-muted border border-line px-1.5 py-0.5 rounded">
                    backend/qc
                  </span>
                </div>

                <div className="p-4 border border-line rounded bg-surface">
                  <span className="text-[0.75rem] font-mono text-accent font-semibold block">03 / ALERTS & OPS</span>
                  <h4 className="text-[0.9375rem] font-medium text-ink mt-1">Alerting & Feedback Loop</h4>
                  <p className="text-[0.8125rem] text-muted mt-1 font-sans">
                    Severity thresholding, WebSocket real-time dispatch, operator feedback capture, and retrain pipeline.
                  </p>
                  <span className="inline-block mt-3 text-[0.6875rem] font-mono text-muted border border-line px-1.5 py-0.5 rounded">
                    backend/alerts & retrain
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Quick Station Inspection Modal / Slide-out */}
      {inspectStationCode && (
        <div className="fixed inset-0 z-[1000] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-panel border border-line rounded-lg max-w-2xl w-full p-6 shadow-2xl relative animate-fadeIn max-h-[90vh] overflow-y-auto">
            <button
              onClick={() => setInspectStationCode(null)}
              className="absolute top-4 right-4 p-1.5 rounded text-muted hover:text-ink hover:bg-surface transition-colors"
            >
              <X className="w-5 h-5" />
            </button>

            {detailLoading ? (
              <div className="py-16 text-center text-muted font-mono text-[0.875rem]">
                Loading telemetry for {inspectStationCode}...
              </div>
            ) : stationDetail ? (
              <div className="space-y-5">
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="text-[0.75rem] font-mono text-accent font-semibold">
                      {stationDetail.station_code}
                    </span>
                    <span className="text-line">•</span>
                    <span className="text-[0.75rem] text-muted">
                      {stationDetail.district}, {stationDetail.state}
                    </span>
                  </div>
                  <h3 className="text-[1.25rem] font-bold text-ink mt-0.5 font-sans">
                    {stationDetail.name}
                  </h3>
                  <div className="flex items-center space-x-2 mt-2">
                    <span
                      className={`inline-flex items-center space-x-1 px-2.5 py-0.5 rounded text-[0.75rem] font-semibold font-mono ${
                        stationDetail.health_status === 'healthy'
                          ? 'bg-[#3FB876]/15 text-[#3FB876] border border-[#3FB876]/40'
                          : stationDetail.health_status === 'suspect'
                          ? 'bg-[#E8B84D]/15 text-[#E8B84D] border border-[#E8B84D]/40'
                          : stationDetail.health_status === 'anomalous'
                          ? 'bg-[#E0655C]/20 text-[#E0655C] border border-[#E0655C]/60 pulse-anomalous'
                          : 'bg-muted/15 text-muted border border-line'
                      }`}
                    >
                      <span className="w-1.5 h-1.5 rounded-full bg-current" />
                      <span>{stationDetail.health_status.toUpperCase()}</span>
                    </span>
                    <span className="text-[0.75rem] font-mono text-muted">
                      Elev: {stationDetail.elevation_m ? `${stationDetail.elevation_m}m` : '—'} · Lat: {stationDetail.latitude.toFixed(4)}, Lon: {stationDetail.longitude.toFixed(4)}
                    </span>
                  </div>
                </div>

                {/* Active Alerts if any */}
                {stationDetail.active_alerts.length > 0 && (
                  <div className="bg-[#E0655C]/10 border border-[#E0655C]/50 rounded p-3.5 space-y-2">
                    <div className="flex items-center space-x-2 text-[#E0655C] font-semibold text-[0.8125rem]">
                      <AlertTriangle className="w-4 h-4" />
                      <span>Active Operational Alerts ({stationDetail.active_alerts.length})</span>
                    </div>
                    {stationDetail.active_alerts.map((al) => (
                      <div key={al.id} className="text-[0.75rem] text-ink font-mono bg-panel/60 p-2 rounded border border-[#E0655C]/30 flex justify-between items-center">
                        <span>{al.message}</span>
                        <span className="text-[0.6875rem] uppercase text-[#E0655C] font-bold px-1.5 py-0.5 rounded bg-[#E0655C]/15">
                          {al.severity}
                        </span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Latest Telemetry Grid */}
                <div>
                  <h4 className="text-[0.875rem] font-semibold text-ink mb-2">Latest Observation</h4>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    <div className="p-2.5 bg-surface border border-line rounded">
                      <span className="text-[0.6875rem] text-muted block font-mono">Temperature</span>
                      <span className="text-[1.125rem] font-mono font-semibold text-ink">
                        {stationDetail.latest_reading?.temperature != null ? `${stationDetail.latest_reading.temperature.toFixed(1)} °C` : '—'}
                      </span>
                    </div>
                    <div className="p-2.5 bg-surface border border-line rounded">
                      <span className="text-[0.6875rem] text-muted block font-mono">Relative Humidity</span>
                      <span className="text-[1.125rem] font-mono font-semibold text-ink">
                        {stationDetail.latest_reading?.humidity != null ? `${stationDetail.latest_reading.humidity.toFixed(1)} %` : '—'}
                      </span>
                    </div>
                    <div className="p-2.5 bg-surface border border-line rounded">
                      <span className="text-[0.6875rem] text-muted block font-mono">Pressure</span>
                      <span className="text-[1.125rem] font-mono font-semibold text-ink">
                        {stationDetail.latest_reading?.pressure != null ? `${stationDetail.latest_reading.pressure.toFixed(1)} hPa` : '—'}
                      </span>
                    </div>
                    <div className="p-2.5 bg-surface border border-line rounded">
                      <span className="text-[0.6875rem] text-muted block font-mono">Wind Speed</span>
                      <span className="text-[1.125rem] font-mono font-semibold text-ink">
                        {stationDetail.latest_reading?.wind_speed != null ? `${stationDetail.latest_reading.wind_speed.toFixed(1)} m/s` : '—'}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Recent Telemetry Stream table */}
                <div>
                  <h4 className="text-[0.875rem] font-semibold text-ink mb-2">Recent Stream History ({stationDetail.recent_readings.length})</h4>
                  <div className="max-h-48 overflow-y-auto border border-line rounded">
                    <table className="w-full text-left text-[0.75rem] font-mono">
                      <thead className="bg-surface sticky top-0 border-b border-line text-muted">
                        <tr>
                          <th className="p-2">Timestamp (UTC)</th>
                          <th className="p-2">Temp</th>
                          <th className="p-2">Humidity</th>
                          <th className="p-2">Pressure</th>
                          <th className="p-2">Wind</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-line">
                        {stationDetail.recent_readings.map((r, i) => (
                          <tr key={i} className="hover:bg-surface/50">
                            <td className="p-2 text-muted">{new Date(r.timestamp).toISOString().replace('.000Z', 'Z')}</td>
                            <td className="p-2 text-ink">{r.temperature != null ? `${r.temperature.toFixed(1)}°C` : '—'}</td>
                            <td className="p-2 text-ink">{r.humidity != null ? `${r.humidity.toFixed(1)}%` : '—'}</td>
                            <td className="p-2 text-ink">{r.pressure != null ? `${r.pressure.toFixed(1)}` : '—'}</td>
                            <td className="p-2 text-ink">{r.wind_speed != null ? `${r.wind_speed.toFixed(1)}` : '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            ) : (
              <div className="py-8 text-center text-muted">Station details unavailable.</div>
            )}
          </div>
        </div>
      )}

      <footer className="w-full border-t border-line py-4 px-6 text-center text-[0.75rem] font-mono text-muted bg-panel">
        AeroSentinel · MoES / IMD Disaster Management · Smart India Hackathon (SIH26073)
      </footer>
    </div>
  );
};
